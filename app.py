from flask import Flask, jsonify, request, redirect, url_for
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# 이미지 저장 경로 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../asset/image')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 폴더가 없을 경우 생성

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 최대 업로드 파일 크기 설정 (16MB)

@app.route('/input/image', methods=['POST'])
def upload_image():
    # 이미지 파일이 요청에 포함되어 있는지 확인
    if 'image' not in request.files:
        return jsonify({
            "error": "No image file in the request.",
            "suggestion": "Please include an image file using 'image' as the key in the form data."
        }), 400

    file = request.files['image']

    # 파일이 선택되지 않았을 경우
    if file.filename == '':
        return jsonify({
            "error": "No file selected.",
            "suggestion": "Please select an image file before uploading."
        }), 400

    # 파일이 이미지 파일인지 확인
    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        # 파일을 지정한 경로에 저장
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        return jsonify({
            "message": "File uploaded successfully.",
            "file_path": file_path
        }), 200
    else:
        return jsonify({
            "error": "Invalid file format.",
            "suggestion": "Please upload a file in PNG, JPG, JPEG, or GIF format."
        }), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
