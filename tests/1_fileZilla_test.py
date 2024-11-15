from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
import os
from supabase import create_client, Client

app = Flask(__name__, template_folder='../templates')  # templates 폴더의 상대 경로 설정
CORS(app)

# Supabase URL과 Key 읽기
SUPABASE_URL = open(os.path.join(os.path.dirname(__file__), '../key/SUPABASE_URL.txt')).read().strip()
SUPABASE_KEY = open(os.path.join(os.path.dirname(__file__), '../key/SUPABASE_KEY.txt')).read().strip()

# Supabase 클라이언트 생성
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 이미지 업로드 폴더 설정 (로컬 저장용)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../asset/image')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 최대 업로드 파일 크기 설정 (16MB)

# 홈 페이지로 upload.html 렌더링
@app.route('/')
def home():
    return render_template('upload.html')  # templates 폴더 내 upload.html 파일을 불러옴

# 이미지 파일 업로드 엔드포인트
@app.route('/input/image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({
            "error": "No image file in the request.",
            "suggestion": "Please include an image file using 'image' as the key in the form data."
        }), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({
            "error": "No file selected.",
            "suggestion": "Please select an image file before uploading."
        }), 400

    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        try:
            file_data = file.read()
            file_name = file.filename

            # Supabase에 파일 업로드
            response = supabase.storage.from_("image-files").upload(file_name, file_data)

            # 응답 상태 확인
            print(f"Supabase Response Status: {response.status_code}")
            print(f"Supabase Response Body: {response.json()}")

            if response.status_code == 200:
                return jsonify({
                    "message": "File uploaded successfully to Supabase.",
                    "file_url": response.data["Key"]
                }), 200
            else:
                return jsonify({
                    "error": "Failed to upload to Supabase.",
                    "response_status": response.status_code,
                    "response_message": response.json()  # 응답 메시지 출력
                }), 500
        except Exception as e:
            return jsonify({
                "error": "Error during file upload.",
                "message": str(e)
            }), 500
    else:
        return jsonify({
            "error": "Invalid file format.",
            "suggestion": "Please upload a file in PNG, JPG, JPEG, or GIF format."
        }), 400




if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
