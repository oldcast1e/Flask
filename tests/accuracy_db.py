from pymongo import MongoClient
import json
from fuzzywuzzy import fuzz

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


# MongoDB URI와 JSON 파일 경로 설정
MONGODB_URI = "mongodb+srv://kwohyo:LHF1sXlKiAoLbriT@cluster0.tlsd6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "OurTime"
COLLECTION_NAME = "realtable"
JSON_PATH = "Web/asset/json/22011925_권효정.json"

# 함수 실행
update_schedule_with_mongodb(JSON_PATH, MONGODB_URI, DB_NAME, COLLECTION_NAME)
