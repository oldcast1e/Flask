# 플라스크 기반 정확도 향상 알고리즘 추가


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

# API 키 로드 함수
def load_api_key(file_path):
    with open(file_path, "r") as file:
        return file.read().strip()

# API 키 로드
BASE_DIR = os.path.dirname(__file__)
CLOVA_API_URL = load_api_key(os.path.join(BASE_DIR, "key", "CLOVA_API_URL.txt"))
CLOVA_SECRET_KEY = load_api_key(os.path.join(BASE_DIR, "key", "CLOVA_SECRET_KEY.txt"))
openai.api_key = load_api_key(os.path.join(BASE_DIR, "key", "openai_api_key.txt"))

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        user_id = data.get("id")
        user_pw = data.get("pw")

        # 기존 user_collection 대신 collection_user 사용
        user = collection_user.find_one({"_id": user_id})

        if not user:
            return jsonify({"status": "error", "message": "아이디가 올바르지 않습니다."})
        elif user["info"]["pw"] != user_pw:
            return jsonify({"status": "error", "message": "비밀번호를 확인해주세요."})
        else:
            return jsonify({
                "status": "success",
                "message": f"로그인 성공. 환영합니다, {user['info']['name']}님!",
                "id": user_id,
                "name": user["info"]["name"]
            })
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

@app.route('/get_timetable', methods=['POST'])
def get_timetable():
    try:
        data = request.json
        user_id = data.get("id")

        # timetable_collection을 collection_timetable로 수정
        timetable = collection_timetable.find_one({"_id": user_id})

        if not timetable:
            return jsonify({"status": "error", "message": "시간표를 찾을 수 없습니다."})

        # 사용자 정보
        user_info = timetable.get("info", {})

        # 시간표 데이터 가공
        schedule = []
        for entry in timetable.get("schedule", []):
            class_name = entry.get("class_name", "")
            start_time = entry.get("start_time", "")
            end_time = entry.get("end_time", "")
            location = entry.get("location", "")

            # 빈 데이터 무시
            if not class_name or not start_time or not end_time or not entry.get("class_days"):
                continue

            for day in entry.get("class_days", []):
                day_int = int(day.get("$numberInt", -1))
                if day_int == -1:
                    continue
                schedule.append({
                    "day": day_int,  # 요일 (숫자)
                    "start_time": start_time,  # 시작 시간
                    "end_time": end_time,  # 종료 시간
                    "class_name": class_name,  # 강의명
                    "location": location  # 장소
                })

        # JSON 응답
        return jsonify({
            "status": "success",
            "user_info": user_info,
            "timetable": {"schedule": schedule}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})



@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        # 사용자 정보 가져오기
        user_id = request.form.get("userId")
        user_name = request.form.get("userName")
        print(f"[DEBUG] userId: {user_id}, userName: {user_name}")

        if not user_id or not user_name:
            return jsonify({"status": "error", "message": "사용자 정보가 누락되었습니다."})

        #1. 사용자 정보 확인
        user = collection_user.find_one({"_id": user_id})
        if not user:
            return jsonify({"status": "error", "message": "사용자 정보가 존재하지 않습니다."})

        #2. 이미지 파일 처리
        if "image" not in request.files:
            print("[DEBUG] 이미지 파일이 요청에 포함되지 않았습니다.")
            return jsonify({"status": "error", "message": "이미지 파일이 필요합니다."})
        file = request.files["image"]
        print(f"[DEBUG] 업로드된 파일: {file.filename}")
        file_path = f"/tmp/{uuid.uuid4()}.png"
        file.save(file_path)
        print(f"[DEBUG] 파일이 저장된 경로: {file_path}")

        #3. 이미지 전처리
        processed_image_path = process_image(file_path)
        print(f"[DEBUG] 전처리된 이미지 경로: {processed_image_path}")

        #4. 클로바 OCR 처리
        ocr_data = extract_text_with_clova(processed_image_path)
        if not ocr_data:
            print("[ERROR] 클로바 OCR 처리 실패.")
            return jsonify({"status": "error", "message": "OCR 처리 중 오류 발생."})

        #5. OCR 텍스트 추출
        ocr_text = extract_ocr_text(ocr_data)
        if not ocr_text:
            print("[ERROR] OCR 데이터에서 텍스트를 추출하지 못했습니다.")
            return jsonify({"status": "error", "message": "OCR 데이터에서 텍스트 추출 실패."})

        #6. OpenAI GPT API로 시간표 분석
        final_data = analyze_schedule_with_openai(ocr_text, student_name=user_name, student_id=user_id)
        if not final_data:
            print("[ERROR] OpenAI GPT API 처리 실패.")
            return jsonify({"status": "error", "message": "OpenAI API 처리 중 오류 발생."})

        #7. 실제 시간표와 비교하여 업데이트
        updated_data = update_schedule_with_mongodb(final_data, client)
        if not updated_data:
            return jsonify({"status": "error", "message": "시간표 업데이트 중 오류 발생."})

        #8. MongoDB에 데이터 저장
        collection_timetable.replace_one({"_id": user_id}, updated_data, upsert=True)
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
    Analyze the following OCR data and organize it into a class schedule in JSON format. Adhere to these precise instructions:

    1. **Separate each class into distinct entries**:
    - Each class must be represented as a unique entry in the schedule.
    - If multiple class names appear on the same line or across adjacent lines, create separate entries for each.
    - Remove irrelevant suffixes or words such as "스터디", "연구", or "과제" unless they are integral to the class name.

    2. **Handle incomplete or ambiguous data**:
    - For class names that appear fragmented or merged with other text, infer the correct name based on layout, context, or spacing.
    - If fields like class days, times, or locations are missing, leave those fields empty (e.g., `[]` for `class_days`, or empty strings for time and location).

    3. **Extract and structure the following fields**:
    - `"class_name"`: The exact class name in Korean, cleaned of unnecessary text.
    - `"class_days"`: Represent class days numerically (1 = Monday, ..., 5 = Friday). Leave as an empty list `[]` if not specified.
    - `"start_time"` and `"end_time"`: Times must follow the `hh:mm` 24-hour format, rounded to the nearest 30 minutes (e.g., 13:45 → 13:30, 13:55 → 14:00). Leave as an empty string `""` if missing.
    - `"location"`: Use the location provided in the OCR data. If no location is specified, use `"Unknown"`.

    4. **Resolve inconsistencies in time and format**:
    - Ensure start times are earlier than end times. If the data is unclear, infer logical time ranges based on context (e.g., morning or afternoon).
    - Verify all numeric values, such as days and times, are correctly parsed from the OCR data.

    5. **Preserve data integrity**:
    - Do not assume or add data beyond what is available in the OCR text.
    - Ensure the JSON strictly follows the format below, with each class entry as a separate object:

        {{
            "class_name": "Exact Class Name in Korean",
            "class_days": [1, 3, 5],
            "start_time": "09:30",
            "end_time": "10:30",
            "location": "Classroom A"
        }}

    6. **Output considerations**:
    - If the OCR data contains irrelevant text or non-class-related entries, exclude them from the final schedule.
    - For incomplete data, structure the entry with the available information, leaving missing fields empty.

    Here is the OCR data extracted from the timetable image: {ocr_text}
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

def update_schedule_with_mongodb(final_data, mongodb_client, db_name="OurTime", collection_name="realtable"):
    try:
        # MongoDB 연결 및 컬렉션 설정
        db = mongodb_client[db_name]
        realtable_collection = db[collection_name]

        # MongoDB에서 실제 시간표 데이터 가져오기
        actual_schedules = list(realtable_collection.find({}))
        print(f"[INFO] 실제 시간표 데이터 로드 완료: {len(actual_schedules)}개 항목")

        # 업데이트 대상 시간표 가져오기
        user_schedule = final_data.get("schedule", [])
        if not user_schedule:
            print("[ERROR] 업데이트할 시간표 데이터가 비어 있습니다.")
            return None

        # 시간표 업데이트 로직
        for item in user_schedule:
            ocr_name = item.get("class_name", "")
            ocr_start_time = item.get("start_time", "")
            ocr_end_time = item.get("end_time", "")

            best_match = None
            best_score = 0

            for actual in actual_schedules:
                actual_name = actual.get("class_name", "")
                actual_start_time = actual.get("start_time", "")
                actual_end_time = actual.get("end_time", "")
                actual_days = actual.get("class_days", [])

                # 유사도 계산 (Fuzzy Matching)
                name_score = fuzz.token_sort_ratio(ocr_name, actual_name) * 0.5
                start_time_score = fuzz.ratio(ocr_start_time, actual_start_time) * 0.25 if actual_start_time else 0
                end_time_score = fuzz.ratio(ocr_end_time, actual_end_time) * 0.25 if actual_end_time else 0
                total_score = name_score + start_time_score + end_time_score

                # 최고 유사도 갱신
                if total_score > best_score:
                    best_match = actual
                    best_score = total_score

            # 유사도가 80% 이상일 경우 업데이트
            if best_match and best_score >= 80:
                item["class_name"] = best_match["class_name"]
                item["class_days"] = best_match.get("class_days", [])
                item["start_time"] = best_match.get("start_time", "")
                item["end_time"] = best_match.get("end_time", "")
                item["location"] = best_match.get("location", "Unknown")

                print(f"[INFO] 업데이트된 항목: {item}")

        # 업데이트된 시간표 반환
        final_data["schedule"] = user_schedule
        print("[INFO] 시간표 업데이트 완료")
        return final_data

    except Exception as e:
        print(f"[ERROR] 시간표 업데이트 중 오류 발생: {e}")
        return None



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
