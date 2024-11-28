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
from fuzzywuzzy import fuzz

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
collection_realtable = db.realtable

# API 키 로드 함수
def load_api_key(file_path):
    with open(file_path, "r") as file:
        return file.read().strip()

# API 키 로드
BASE_DIR = os.path.dirname(__file__)
CLOVA_API_URL = load_api_key(os.path.join(BASE_DIR, "key", "CLOVA_API_URL.txt"))
CLOVA_SECRET_KEY = load_api_key(os.path.join(BASE_DIR, "key", "CLOVA_SECRET_KEY.txt"))
openai.api_key = load_api_key(os.path.join(BASE_DIR, "key", "openai_api_key.txt"))


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
        # print(f"[DEBUG] OCR 데이터: {ocr_data}")

        # OpenAI GPT API로 시간표 문서화
        ocr_text = extract_ocr_text(ocr_data)
        if not ocr_text:
            print("[ERROR] OCR 데이터에서 텍스트를 추출하지 못했습니다.")
            return jsonify({"status": "error", "message": "OCR 데이터에서 텍스트 추출 실패."})
        # print(f"[DEBUG] OCR 텍스트: {ocr_text}")

        final_data = analyze_schedule_with_openai(ocr_text, student_name=user_name, student_id=user_id)
        if not final_data:
            print("[ERROR] OpenAI GPT API 처리 실패.")
            return jsonify({"status": "error", "message": "OpenAI API 처리 중 오류 발생."})

        # <- DB에 있는 시간표랑 비교해서 json 수정
        #
        #
        final_data = update_schedule_with_mongodb(final_data, client, db, collection_realtable)


        # MongoDB에 데이터 저장
        collection_timetable.replace_one({"_id": user_id}, final_data, upsert=True)
        print("[INFO] 데이터가 MongoDB에 저장되었습니다.")

        # 성공 응답 반환
        return jsonify({"status": "success", "message": "업로드 및 분석 완료."})

    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()
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
    - Class name (without spaces),
    - Class days (represented as 1 for Monday to 5 for Friday),
    - Class start and end times (formatted as HH:MM, 24-hour time),
    - Location (classroom or hall).

    OCR data: {ocr_text}
    """
    try:
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

        json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        else:
            return None

        schedule_data = json.loads(response_text)
        return {
            "_id": student_id,
            "info": {"name": student_name, "number": student_id},
            "schedule": schedule_data
        }
    except Exception as e:
        print(f"[ERROR] OpenAI API 호출 오류: {e}")
        return None

def update_schedule_with_mongodb(json_path, mongodb_uri, db_name, collection_name):
    # 1. JSON 파일 불러오기
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        print(f"JSON 파일 불러오기 성공: {json_path}")
    except FileNotFoundError:
        print(f"JSON 파일을 찾을 수 없습니다: {json_path}")
        return
    except json.JSONDecodeError:
        print(f"JSON 파일이 올바른 형식이 아닙니다: {json_path}")
        return

    # 2. MongoDB 연결 및 데이터 가져오기
    try:
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        collection = db[collection_name]
        
        # MongoDB에서 데이터 가져오기, "_id"와 "location" 필드 제외
        mongodb_data = list(collection.find({}, {"_id": 0, "location": 0}))
        print(f"MongoDB에서 가져온 데이터:\n{mongodb_data}")
    except Exception as e:
        print(f"MongoDB 연결 또는 데이터 가져오기 오류: {e}")
        return

    if not mongodb_data:
        print("MongoDB에서 데이터를 가져오지 못했습니다. 데이터베이스와 컬렉션 이름을 확인하세요.")
        return

    # 3. JSON 데이터 업데이트
    schedule = json_data.get("schedule", [])
    if not schedule:
        print("JSON 파일에서 'schedule' 키를 찾을 수 없습니다.")
        return

    for item in schedule:
        ocr_name = item["class_name"]
        ocr_start_time = item.get("start_time", "")  # JSON에서 시작 시간
        ocr_end_time = item.get("end_time", "")  # JSON에서 종료 시간

        best_match = None
        best_score = 0

        for data in mongodb_data:
            # MongoDB 필드 값 가져오기
            db_name = data.get("class_name", "")
            db_start_time = data.get("start_time", "")
            db_end_time = data.get("end_time", "")
            db_days = data.get("class_days", [])

            # 과목 이름 비교 (가중치 50%)
            name_score = fuzz.token_sort_ratio(ocr_name, db_name) * 0.5

            # 시작 시간 비교 (가중치 25%)
            start_time_score = (
                fuzz.ratio(str(ocr_start_time), str(db_start_time)) * 0.25
                if db_start_time
                else 0
            )

            # 종료 시간 비교 (가중치 25%)
            end_time_score = (
                fuzz.ratio(str(ocr_end_time), str(db_end_time)) * 0.25
                if db_end_time
                else 0
            )

            # 총 점수 계산
            total_score = name_score + start_time_score + end_time_score

            # 가장 높은 점수를 가진 매칭 데이터 저장
            if total_score > best_score:
                best_match = data
                best_score = total_score

        # 매칭 결과 출력
        print(f"OCR 데이터: {ocr_name}, 매칭 점수: {best_score}, 매칭 데이터: {best_match}")

        # 유사도가 80% 이상일 경우 데이터 업데이트
        if best_match and best_score >= 80:
            item["class_name"] = best_match["class_name"]
            item["class_days"] = best_match.get("class_days", [])  # 그대로 업데이트
            item["start_time"] = best_match.get("start_time", "")
            item["end_time"] = best_match.get("end_time", "")

    # 4. 업데이트된 JSON 데이터 저장
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        print(f"업데이트된 JSON 파일 저장 완료: {json_path}")
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")


if __name__ == "__main__":
    app.run(host="192.168.0.43", port=5002)
