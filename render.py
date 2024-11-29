# 최종 수정 1

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
# print(f"[DEBUG] CLOVA_API_URL: {CLOVA_API_URL}")
# print(f"[DEBUG] CLOVA_SECRET_KEY: {CLOVA_SECRET_KEY}")
# print(f"[DEBUG] OPENAI_API_KEY: {openai.api_key}")


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
            print("[ERROR] 사용자 정보가 누락되었습니다.")
            return jsonify({"status": "error", "message": "사용자 정보가 누락되었습니다."})

        # 사용자 정보 확인
        user = collection_user.find_one({"_id": user_id})
        if not user:
            print("[ERROR] 사용자 정보가 존재하지 않습니다.")
            return jsonify({"status": "error", "message": "사용자 정보가 존재하지 않습니다."})

        # 이미지 파일 처리
        if "image" not in request.files:
            print("[ERROR] 이미지 파일이 요청에 포함되지 않았습니다.")
            return jsonify({"status": "error", "message": "이미지 파일이 필요합니다."})

        file = request.files["image"]
        file_path = f"/tmp/{uuid.uuid4()}.png"
        file.save(file_path)
        print(f"[DEBUG] 업로드된 파일이 저장되었습니다: {file_path}")

        # 이미지 전처리
        processed_image_path = process_image(file_path)
        print(f"[DEBUG] 전처리된 이미지 경로: {processed_image_path}")

        # 클로바 OCR 처리
        ocr_data = extract_text_with_clova(processed_image_path)
        if not ocr_data:
            print("[ERROR] 클로바 OCR 처리 실패.")
            return jsonify({"status": "error", "message": "OCR 처리 중 오류 발생."})

        # JSON 기반 시간표 분석
        analyzed_data = analyze_timetable_with_json(ocr_data)
        if not analyzed_data:
            print("[ERROR] JSON 데이터 분석 실패.")
            return jsonify({"status": "error", "message": "JSON 데이터 분석 실패."})

        # OpenAI GPT API로 시간표 문서화
        ocr_text = extract_ocr_text(ocr_data)
        if not ocr_text:
            print("[ERROR] OCR 데이터에서 텍스트를 추출하지 못했습니다.")
            return jsonify({"status": "error", "message": "OCR 데이터에서 텍스트 추출 실패."})

        # GPT API를 사용한 시간표 생성
        final_data = analyze_schedule_with_openai(ocr_text, student_name=user_name, student_id=user_id)
        if not final_data:
            print("[ERROR] OpenAI GPT API 처리 실패.")
            return jsonify({"status": "error", "message": "OpenAI API 처리 중 오류 발생."})

        # MongoDB에 데이터 저장
        try:
            # print("[DEBUG] MongoDB 저장 전 데이터:", json.dumps(final_data, indent=2, ensure_ascii=False))
            result = collection_timetable.replace_one({"_id": user_id}, final_data, upsert=True)
            # print("[INFO] MongoDB 저장 성공. 결과:", result.raw_result)
        except Exception as db_error:
            print(f"[ERROR] MongoDB 저장 중 오류: {db_error}")
            return jsonify({"status": "error", "message": "MongoDB 저장 실패."})

        # 성공 응답 반환
        print("[INFO] 업로드 및 분석 성공.")
        return jsonify({"status": "success", "message": "업로드 및 분석 완료."})

    except Exception as e:
        print(f"[ERROR] 서버 처리 중 오류 발생: {e}")
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})



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
    """클로바 OCR API를 사용해 텍스트 데이터를 추출하는 함수 (표 추출 기능 포함)."""
    try:
        # 파일 열기 및 설정
        files = [('file', open(file_path, 'rb'))]
        headers = {'X-OCR-SECRET': CLOVA_SECRET_KEY}
        payload = {
            'message': json.dumps({
                'version': 'V2',
                'requestId': str(uuid.uuid4()),
                'timestamp': int(round(time.time() * 1000)),
                'images': [{
                    'format': os.path.splitext(file_path)[-1][1:],  # 파일 확장자를 동적으로 설정
                    'name': os.path.basename(file_path),
                    'type': 'table'  # 표 추출 타입 활성화
                }]
            })
        }

        # 클로바 OCR API 호출
        response = requests.post(CLOVA_API_URL, headers=headers, data=payload, files=files)

        # 성공적인 응답일 경우 JSON 데이터 반환
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] 클로바 OCR API 응답 오류. 상태 코드: {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] 클로바 OCR 호출 오류: {str(e)}")
        return None


def extract_ocr_text(ocr_data):
    """OCR 데이터에서 텍스트를 추출하는 함수."""
    try:
        if not ocr_data.get('images') or not isinstance(ocr_data['images'], list):
            print("[ERROR] OCR 데이터에서 'images' 키가 없거나 유효하지 않습니다. 공백 데이터로 처리합니다.")
            return ""
        
        image_data = ocr_data['images'][0]
        fields = image_data.get('fields', [])
        if not fields:
            print("[ERROR] OCR 데이터에서 'fields' 키가 없거나 데이터가 비어 있습니다. 공백 데이터로 처리합니다.")
            return ""
        
        extracted_texts = []
        for field in fields:
            if "inferText" in field:
                extracted_texts.append(field["inferText"])
        
        if not extracted_texts:
            print("[ERROR] OCR 데이터에서 텍스트를 추출할 수 없습니다. 공백 데이터로 처리합니다.")
            return ""
        
        return " ".join(extracted_texts)

    except Exception as e:
        print(f"[ERROR] OCR 텍스트 추출 중 예기치 못한 오류 발생: {str(e)}")
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
    - Each class must not exceed three sessions per week if the class name is the same.
    - Define class duration as `end_time - start_time`, which must be fixed to 1.5 hours or 3 hours.
    - If the extracted duration is not a multiple of 1.5 hours, round it to the nearest valid value (e.g., 1 hour → 1.5 hours).
    - Ensure no two classes have overlapping times.

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

def analyze_timetable_with_json(ocr_data):
    """클로바 OCR JSON 데이터를 기반으로 시간표를 분석하는 함수."""
    try:
        # 'images' 키와 'tables' 키 검증
        if not ocr_data.get('images') or not isinstance(ocr_data['images'], list):
            print("[ERROR] 'images' 키가 없거나 유효하지 않습니다. 공백 데이터로 처리합니다.")
            return [{"row": -1, "column": -1, "text": ""}]
        
        image_data = ocr_data['images'][0]
        if not image_data.get('tables') or not isinstance(image_data['tables'], list) or not image_data['tables']:
            print("[ERROR] 'tables' 키가 존재하지 않거나 데이터가 비어 있습니다. 공백 데이터로 처리합니다.")
            return [{"row": -1, "column": -1, "text": ""}]
        
        # 'tables' 데이터 분석
        tables = image_data['tables'][0].get('cells', [])
        if not tables:
            print("[ERROR] 'tables'의 'cells' 데이터가 비어 있습니다. 공백 데이터로 처리합니다.")
            return [{"row": -1, "column": -1, "text": ""}]

        schedule_data = []
        for cell in tables:
            # 빈 셀 건너뛰기
            if not cell.get('cellTextLines'):
                print("[DEBUG] 빈 셀 데이터를 건너뜁니다.")
                continue

            cell_text = []
            for line in cell['cellTextLines']:
                line_text = " ".join(word["inferText"] for word in line.get("cellWords", []) if "inferText" in word)
                if line_text.strip():  # 공백만 있는 텍스트는 무시
                    cell_text.append(line_text)
            
            if not cell_text:  # 셀 텍스트가 비어 있으면 건너뜀
                print("[DEBUG] 유효한 텍스트가 없는 셀을 건너뜁니다.")
                continue
            
            schedule_data.append({
                "row": cell.get("rowIndex", -1),  # 기본값 -1로 설정
                "column": cell.get("columnIndex", -1),  # 기본값 -1로 설정
                "text": " ".join(cell_text).strip()
            })

        if not schedule_data:
            print("[ERROR] 유효한 데이터가 없는 'tables'입니다. 공백 데이터로 처리합니다.")
            return [{"row": -1, "column": -1, "text": ""}]

        print("[INFO] 'tables' 데이터 분석 완료.")
        return schedule_data

    except KeyError as e:
        print(f"[ERROR] JSON 데이터 분석 중 KeyError 발생: {str(e)}. 공백 데이터로 처리합니다.")
        return [{"row": -1, "column": -1, "text": ""}]
    except Exception as e:
        print(f"[ERROR] JSON 데이터 분석 중 예기치 못한 오류 발생: {str(e)}. 공백 데이터로 처리합니다.")
        return [{"row": -1, "column": -1, "text": ""}]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render의 PORT 환경 변수 사용
    app.run(host="0.0.0.0", port=port)
