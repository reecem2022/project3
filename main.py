import os
import json
import traceback
from flask import Flask, redirect, request, send_file, Response
from google.cloud import storage
import google.generativeai as genai
import re

os.makedirs('files', exist_ok = True)

app = Flask(__name__)

genai.configure(api_key=os.environ['GEMINI_KEY'])

generation_config={
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_nune_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
)

image_html = ""

PROMPT = "Give me a JSON response with a 'title' and 'description' for this image. Do not include any extra text or formatting. Example: {\"title\": \"Your title here\", \"description\": \"Your description here\"}"

BUCKET_NAME = "markreece-project2-bucket"

@app.route('/')
def index():
  #f"https://storage.googleapis.com/{bucket_name}/{request.form['file']}"
  global image_html
  index_html=f"""
    <form method="post" enctype="multipart/form-data" action="/upload" method="post">
    <link rel="stylesheet" type="text/css" href="/static/styles.css">
      <div>
        <label for="file">Choose file to upload</label>
        <input type="file" id="file" name="form_file" accept="image/jpeg"/>
      </div>
      <div>
        <button>Submit</button>
      </div>
      <div>
      </div>
    </form>
    """    
  for file in list_files(BUCKET_NAME):
    if not file.endswith('.json'):
      index_html += f"""
      <form method="post" action="/display-image">
      <input type="hidden" name="file" value="{file}">
        <li>
          <button type="submit">{file}</button>
        </li>
      </form>
      """
  index_html += image_html
  return index_html

def list_files(bucket_name):
  blob_names = []
  blobs=storage.Client().bucket(bucket_name).list_blobs()

  for blob in blobs:
    if blob.name.lower().endswith('.jpg') or blob.name.lower().endswith('.jpeg') or blob.name.lower().endswith('.json'):
      print("ADDED JPG AND JSON")
      blob_names.append(blob.name)
    else:
      blob.delete()
      
  return blob_names

@app.route('/get-image/<filename>')
def get_image(filename):
  blob = storage.Client().bucket(BUCKET_NAME).blob(filename)
  try:
    image=blob.download_as_bytes()
    return Response(image,mimetype="image/jpeg")
  except Exception as e:
    return f"Error: {str(e)}, with the get_image(filename) function", 404

@app.route('/display-image', methods=["POST"])
def displayImage():
  global image_html
  t,d = get_json_data(BUCKET_NAME, request.form['file'].rsplit(".",1)[0]+".json")

  image_html=f"""
  <div class="displayed-image">
    <h3 class="aiText">{t}</h3>
    <img class="selectedImage" src="/get-image/{request.form['file']}" />
    <h4 class="aiText">{d}</h3>
  </div>
  """
  return redirect('/')

def get_json_data(bucket_name, json_filename):
  try:
    blob = storage.Client().bucket(bucket_name).blob(json_filename)
    json_data = blob.download_as_text()

    data = json.loads(json_data)
    title=data.get("title", "No Title Generated")
    description = data.get("description", "No Description Generated")
    return title, description
    
  except Exception as e:
    return "No Title Found", "No Description Found"

@app.route('/files/<filename>')
def get_file(filename):
  return send_file('./files/'+filename)

def fix_response(response):
    try:
        text = response.text
        print(text)
        text = text.replace("```json", "").replace("```", "").strip()
        json_data = json.loads(text)
        return json_data
    except json.JSONDecodeError:
        print("JSON INVALID")
        return {"title": "No Title Found", "description": "No Description Found"}

def upload_to_gemini(path, mime_type=None):
    return genai.upload_file(path, mime_type=mime_type)

@app.route('/upload', methods=["POST"])
def upload():
  file = request.files['form_file']

  image_local_path = f'./{file.filename}'
  json_local_path = f'./{file.filename.split(".")[0]}.json'

  file.save(image_local_path)

  data = [upload_to_gemini(image_local_path, mime_type="image/jpeg"), "\n\n", PROMPT]
  response = model.generate_content(data)

  json_data = fix_response(response)

  with open(json_local_path, "w") as json_file:
    json.dump(json_data, json_file, indent=4)

  if not os.path.exists(json_local_path):
    return
 
  upload_file(image_local_path)
  upload_file(json_local_path)

  os.remove(image_local_path)
  os.remove(json_local_path)

  return redirect("/")

def upload_file(file_path):
  blob = storage.Client().bucket(BUCKET_NAME).blob(os.path.basename(file_path))
  
  try:
    if file_path.endswith(".json"):
      print(f"Uploading JSON to bucket! File at: {file_path}")
      with open(file_path, "r") as f:
        json_data = f.read()
      blob.upload_from_string(json_data, content_type="application/json")
      print("Finished uploading JSON to bucket")
    else:
      print(f"Uploading Image to bucket!  File at: {file_path}")
      blob.upload_from_filename(file_path)
      print("Finished uploading Image to bucket")
  except:
    print("Error with upload_file")

#runs
if __name__ == '__main__':
    app.run(debug=True, port=5005)