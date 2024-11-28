import os
import time
import json
import uuid
import numpy as np
import cv2
import requests
import openai
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import re

# Flask 설정
app = Flask(__name__)
CORS(app)

# MongoDB 클라이언트 설정
client = MongoClient(
    "mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click",
    tls=True,
    tlsAllowInvalidCertificates=True
)
db = client.OurTime
collection_timetable = db.timetable
collection_user = db.User

# Render 환경 변수에서 API 키 로드
CLOVA_API_URL = os.environ.get("CLOVA_API_URL")
CLOVA_SECRET_KEY = os.environ.get("CLOVA_SECRET_KEY")
openai.api_key = os.environ.get("OPENAI_API_KEY")

# 환경 변수 디버깅 출력
print(f"[DEBUG] CLOVA_API_URL: {CLOVA_API_URL}")
print(f"[DEBUG] CLOVA_SECRET_KEY: {CLOVA_SECRET_KEY}")
print(f"[DEBUG] OPENAI_API_KEY: {openai.api_key}")


# 환경 변수 검증
if not CLOVA_API_URL or not CLOVA_SECRET_KEY or not openai.api_key:
    raise ValueError("환경 변수가 설정되지 않았습니다. Render 대시보드에서 확인하세요.")


@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        # 사용자 정보 가져오기
        user_id = request.form.get("userId")
        user_name = request.form.get("userName")
        print(f"[DEBUG] userId: {user_id}, userName: {user_name}")

        if not user_id or not user_name:
            return jsonify({"status": "error", "message": "사용자 정보가 누락되었습니다."})

        # 사용자 정보 확인
        user = collection_user.find_one({"_id": user_id})
        if not user:
            return jsonify({"status": "error", "message": "사용자 정보가 존재하지 않습니다."})

        # 이미지 파일 처리
        if "image" not in request.files:
            print("[DEBUG] 이미지 파일이 요청에 포함되지 않았습니다.")
            return jsonify({"status": "error", "message": "이미지 파일이 필요합니다."})
        file = request.files["image"]
        print(f"[DEBUG] 업로드된 파일: {file.filename}")
        file_path = f"/tmp/{uuid.uuid4()}.png"
        file.save(file_path)
        print(f"[DEBUG] 파일이 저장된 경로: {file_path}")

        # 이미지 전처리
        processed_image_path = process_image(file_path)
        print(f"[DEBUG] 전처리된 이미지 경로: {processed_image_path}")

        # 클로바 OCR 처리
        ocr_data = extract_text_with_clova(processed_image_path)
        if not ocr_data:
            print("[ERROR] 클로바 OCR 처리 실패.")
            return jsonify({"status": "error", "message": "OCR 처리 중 오류 발생."})

        # OpenAI GPT API로 시간표 문서화
        ocr_text = extract_ocr_text(ocr_data)
        if not ocr_text:
            print("[ERROR] OCR 데이터에서 텍스트를 추출하지 못했습니다.")
            return jsonify({"status": "error", "message": "OCR 데이터에서 텍스트 추출 실패."})

        final_data = analyze_schedule_with_openai(ocr_text, student_name=user_name, student_id=user_id)
        if not final_data:
            print("[ERROR] OpenAI GPT API 처리 실패.")
            return jsonify({"status": "error", "message": "OpenAI API 처리 중 오류 발생."})

        # MongoDB에 데이터 저장
        collection_timetable.replace_one({"_id": user_id}, final_data, upsert=True)
        print("[INFO] 데이터가 MongoDB에 저장되었습니다.")

        # 성공 응답 반환
        return jsonify({"status": "success", "message": "업로드 및 분석 완료."})

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": "서버 오류 발생."})


def process_image(image_path):
    output_path = f"/tmp/{uuid.uuid4()}_processed.png"  # 임시 경로
    image = cv2.imread(image_path)
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_image, threshold1=1, threshold2=50)
    kernel = np.ones((3, 3), np.uint8)
    thick_edges = cv2.dilate(edges, kernel, iterations=1)
    gray_image_with_edges = gray_image.copy()
    gray_image_with_edges[edges == 255] = 0
    inverted_image = np.where(gray_image_with_edges == 0, 255, 0).astype(np.uint8)
    re_inverted_image = cv2.bitwise_not(inverted_image)
    cv2.imwrite(output_path, re_inverted_image)
    return output_path


def extract_text_with_clova(file_path):
    try:
        files = [('file', open(file_path, 'rb'))]
        headers = {'X-OCR-SECRET': CLOVA_SECRET_KEY}
        payload = {
            'message': json.dumps({
                'version': 'V2',
                'requestId': str(uuid.uuid4()),
                'timestamp': int(round(time.time() * 1000)),
                'images': [{'format': 'jpg', 'name': os.path.basename(file_path)}]
            })
        }
        response = requests.post(CLOVA_API_URL, headers=headers, data=payload, files=files)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] OCR API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] OCR 호출 중 오류 발생: {e}")
        return None


def extract_ocr_text(ocr_data):
    try:
        if "images" not in ocr_data:
            print("[ERROR] OCR JSON에 'images' 필드가 없습니다.")
            return ""

        extracted_texts = []
        for image in ocr_data.get("images", []):
            if "fields" in image:
                for field in image["fields"]:
                    extracted_texts.append(field.get("inferText", ""))
        return " ".join(extracted_texts)
    except Exception as e:
        print(f"[ERROR] OCR 텍스트 추출 중 오류 발생: {e}")
        return ""


def analyze_schedule_with_openai(ocr_text, student_name, student_id):
    prompt = f"""
    Analyze the following OCR data and organize it as a class schedule. Each schedule entry should contain:
    - class_name: Class name (without spaces),
    - class_days: List of integers (1 for Monday to 5 for Friday),
    - start_time: Start time (formatted as HH:MM, 24-hour time),
    - end_time: End time (formatted as HH:MM, 24-hour time),
    - location: Location (classroom or hall).

    Ensure the output is a valid JSON array containing the entries.
    OCR data: {ocr_text}
    """
    try:
        # OpenAI ChatCompletion 호출
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in OCR data processing and JSON structuring."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.2,
        )
        response_text = response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

        if not response_text:
            return None

        # JSON 응답 추출
        json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        else:
            print("[ERROR] OpenAI 응답에서 JSON 데이터를 찾을 수 없습니다.")
            return None

        # JSON 데이터 로드
        schedule_data = json.loads(response_text)

        # 데이터 형식 변환
        formatted_schedule = []
        for entry in schedule_data:
            formatted_entry = {
                "class_name": entry.get("class_name", "").strip(),
                "class_days": [{"$numberInt": str(day)} for day in entry.get("class_days", [])],
                "start_time": entry.get("start_time", "").strip(),
                "end_time": entry.get("end_time", "").strip(),
                "location": entry.get("location", "").strip()
            }
            formatted_schedule.append(formatted_entry)

        # 최종 데이터 반환
        return {
            "_id": student_id,
            "info": {"name": student_name, "number": student_id},
            "schedule": formatted_schedule
        }
    except Exception as e:
        print(f"[ERROR] OpenAI API 호출 오류: {e}")
        return None



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render의 PORT 환경 변수 사용
    app.run(host="0.0.0.0", port=port)
