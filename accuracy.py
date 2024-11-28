import os
import time
import json
import uuid
import re
from datetime import datetime
import numpy as np
import cv2
from PIL import Image  # Pillow 사용
import requests
import openai

# 기본 경로 설정을 실행 파일의 위치를 기준으로 상대 경로로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "asset", "images", "input")
OUTPUT_IMAGE_DIR = os.path.join(BASE_DIR, "asset", "images", "output")
TEMP_JSON_DIR = os.path.join(BASE_DIR, "asset", "temp")
OUTPUT_JSON_DIR = os.path.join(BASE_DIR, "asset", "json")

# 각 디렉토리가 존재하지 않을 경우 생성
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True)
os.makedirs(TEMP_JSON_DIR, exist_ok=True)
os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)

PROCESSED_FILES = set(os.listdir(INPUT_DIR))  # 초기 실행 시 input 폴더에 있는 파일을 기록하여 무시


def load_api_key(file_path):
    """API 키 파일에서 정보를 로드"""
    with open(file_path, 'r') as file:
        return file.read().strip()


# API 키 파일 경로 설정
CLOVA_API_URL_PATH = os.path.join(BASE_DIR, "lib", "CLOVA_API_URL.txt")
CLOVA_SECRET_KEY_PATH = os.path.join(BASE_DIR, "lib", "CLOVA_SECRET_KEY.txt")
OPENAI_API_KEY_PATH = os.path.join(BASE_DIR, "lib", "openai_api_key.txt")

# API 키 파일에서 정보를 로드
CLOVA_API_URL = load_api_key(CLOVA_API_URL_PATH)
CLOVA_SECRET_KEY = load_api_key(CLOVA_SECRET_KEY_PATH)
openai.api_key = load_api_key(OPENAI_API_KEY_PATH)

from PIL import Image

def process_image(image_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.basename(image_path)
    output_path = os.path.join(output_dir, file_name)

    print(f"[DEBUG] Reading image from: {image_path}")

    try:
        # Pillow로 이미지 읽기
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            image = np.array(img)

        # OpenCV로 처리
        gray_image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray_image, threshold1=1, threshold2=50)
        kernel = np.ones((3, 3), np.uint8)
        thick_edges = cv2.dilate(edges, kernel, iterations=1)
        gray_image_with_edges = gray_image.copy()
        gray_image_with_edges[edges == 255] = 0
        inverted_image = np.where(gray_image_with_edges == 0, 255, 0).astype(np.uint8)
        re_inverted_image = cv2.bitwise_not(inverted_image)

        # Pillow로 이미지 저장
        try:
            Image.fromarray(re_inverted_image).save(output_path)
            print(f"[{datetime.now()}] Final processed image saved: {output_path}")
        except Exception as e:
            print(f"[ERROR] Failed to save processed image with Pillow: {e}")
            return None

        # 저장된 파일 확인
        if not os.path.exists(output_path):
            print(f"[ERROR] File not found after save attempt: {output_path}")
            return None

        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to process image: {e}")
        return None


def extract_text_with_clova(file_path, temp_dir):
    """클로바 OCR을 사용하여 텍스트 추출"""
    os.makedirs(temp_dir, exist_ok=True)
    file_name = os.path.basename(file_path)
    temp_json_path = os.path.join(temp_dir, file_name.replace(".png", ".json").replace(".jpg", ".json"))

    files = [('file', open(file_path, 'rb'))]
    request_json = {
        'images': [{'format': 'jpg', 'name': 'demo'}],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }
    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    headers = {'X-OCR-SECRET': CLOVA_SECRET_KEY}

    response = requests.post(CLOVA_API_URL, headers=headers, data=payload, files=files)

    if response.status_code == 200:
        ocr_result = response.json()
        with open(temp_json_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result, f, ensure_ascii=False, indent=4)
        print(f"[{datetime.now()}] OCR data saved: {temp_json_path}")
        return temp_json_path
    else:
        print(f"[{datetime.now()}] OCR extraction failed with status code: {response.status_code}")
        return None


def extract_ocr_text(ocr_data):
    """OCR 데이터에서 주요 텍스트 추출"""
    fields = ocr_data.get("images", [])[0].get("fields", [])
    text_data = " ".join(field["inferText"] for field in fields)
    return text_data


def analyze_schedule_with_openai(ocr_text, output_json_path, student_name, student_id):
    """GPT-4 API를 사용하여 시간표 분석"""
    prompt = f"""
    Analyze the following OCR data and organize it into a class schedule in JSON format. Follow these strict rules:

    1. **Each class must be treated as a separate entry**:
    - Ensure no two classes are merged into a single "class_name". If multiple names appear on the same line or adjacent lines, split them into separate entries.
    - Remove irrelevant suffixes like "스터디", "연구", or "과제" unless they are essential to the class name's meaning.

    2. **Handle ambiguous or incomplete data**:
    - If a name appears ambiguous (e.g., split into parts or merged with unrelated text), infer the correct class name based on spacing, layout, or context.
    - If no days, times, or locations are specified, leave the relevant fields (`class_days`, `start_time`, `end_time`, `location`) blank.

    3. **Extract the following fields for each class**:
    - `"class_name"`: The exact class name in Korean, cleaned of irrelevant suffixes.
    - `"class_days"`: Days represented as numbers (1 = Monday, ..., 5 = Friday). Leave blank if not specified.
    - `"start_time"` and `"end_time"`: Use hh:mm format, rounded to the nearest 30 minutes. Leave blank if not specified.
    - `"location"`: Include location if available; otherwise, mark as "Unknown".

    4. **Do not assume any additional or predefined class names**:
    - Use only the text provided in the OCR data. If a name seems unfamiliar or incomplete, do not attempt to hardcode or make assumptions beyond the provided rules.

    The output must follow this JSON format:

    {{
        "class_name": "Class Name (in Korean)",
        "class_days": ["Day Numbers"],
        "start_time": "hh:mm",
        "end_time": "hh:mm",
        "location": "Class Location"
    }}

    Here is the OCR data extracted from the timetable image: {ocr_text}

    """



    retries = 3  # API 호출 재시도 횟수
    for attempt in range(retries):
        try:
            # 최신 OpenAI ChatCompletion API 호출
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in OCR data processing and JSON structuring."},
                    {"role": "user", "content": prompt}
                ]
            )

            # 응답에서 메시지 텍스트 추출
            response_text = response['choices'][0]['message']['content'].strip()

            # JSON 형식만 추출
            json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
            if json_match:
                schedule_json = json_match.group(0)
                schedule_data = json.loads(schedule_json)

                # 결과 데이터에 사용자 정보 추가
                final_data = {
                    "info": {
                        "name": student_name,
                        "number": student_id
                    },
                    "schedule": schedule_data
                }

                # JSON 파일로 저장
                with open(output_json_path, 'w', encoding='utf-8') as json_file:
                    json.dump(final_data, json_file, ensure_ascii=False, indent=4)
                print(f"[{datetime.now()}] Schedule JSON saved: {output_json_path}")
                return output_json_path
            else:
                print(f"[ERROR] Unexpected response format on attempt {attempt + 1}/{retries}. Retrying...")
                time.sleep(2)

        except openai.OpenAIError as e:
            print(f"[ERROR] OpenAI API call failed: {e}. Retrying {attempt + 1}/{retries}...")
            time.sleep(2)

    print("[ERROR] Failed to retrieve a valid response from OpenAI API after retries.")
    return None





def monitor_and_process_images():
    """폴더에서 새로운 이미지를 감지하고 처리"""
    valid_extensions = {"png", "jpg", "jpeg"}
    processed_files = PROCESSED_FILES.copy()

    while True:
        current_files = set(os.listdir(INPUT_DIR))
        new_files = current_files - processed_files

        for filename in new_files:
            file_extension = filename.split(".")[-1].lower()
            if file_extension not in valid_extensions:
                print(f"[{datetime.now()}] Error: Invalid file extension for '{filename}'. Only PNG, JPG, JPEG files are allowed.")
                continue

            match = re.match(r"^(\d{8})_([\w가-힣]+)\.(png|jpg|jpeg)$", filename, re.IGNORECASE)
            if not match:
                print(f"[{datetime.now()}] Ignored file: {filename} (does not match '학번_이름.확장자' format)")
                continue

            if filename in processed_files:
                print(f"[{datetime.now()}] Warning: Duplicate file detected: {filename}. Ignoring.")
                continue

            student_id = match.group(1)
            student_name = match.group(2)
            print(f"[{datetime.now()}] New file detected: {filename} (Student ID: {student_id}, Name: {student_name})")

            file_path = os.path.join(INPUT_DIR, filename)
            processed_image_path = process_image(file_path, OUTPUT_IMAGE_DIR)

            # 이미지가 처리되지 않은 경우
            if processed_image_path is None or not os.path.exists(processed_image_path):
                print(f"[ERROR] Processed image file missing: {processed_image_path}")
                continue

            temp_json_path = extract_text_with_clova(processed_image_path, TEMP_JSON_DIR)
            if temp_json_path is None:
                continue

            with open(temp_json_path, "r", encoding="utf-8") as f:
                ocr_data = json.load(f)
            ocr_text = extract_ocr_text(ocr_data)
            output_json_path = os.path.join(OUTPUT_JSON_DIR, filename.replace(".png", ".json").replace(".jpg", ".json"))
            analyze_schedule_with_openai(ocr_text, output_json_path, student_name, student_id)

            processed_files.add(filename)

        time.sleep(5)




if __name__ == "__main__":
    monitor_and_process_images()
