import os
import json
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

# Flask 설정
app = Flask(__name__)
CORS(app)

# MongoDB 설정
client = MongoClient(
    "mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click",
    tls=True,
    tlsAllowInvalidCertificates=True
)
db = client.OurTime
collection_timetable = db.timetable


def extract_schedule_from_json(ocr_json):
    """
    JSON 데이터에서 시간표를 추출하여 MongoDB 형식에 맞게 변환합니다.
    """
    try:
        tables = ocr_json.get("images", [])[0].get("tables", [])
        day_mapping = {"월": 1, "화": 2, "수": 3, "목": 4, "금": 5}
        schedule = []

        for table in tables:
            for cell in table.get("cells", []):
                row_index = cell.get("rowIndex", -1)
                col_index = cell.get("columnIndex", -1)
                cell_text_lines = cell.get("cellTextLines", [])
                cell_text = " ".join(
                    word["inferText"].strip() for line in cell_text_lines for word in line.get("cellWords", [])
                ).strip()

                # 요일 확인
                if row_index == 0 and cell_text in day_mapping:
                    current_day = day_mapping[cell_text]

                # 시간 확인
                elif col_index == 0 and cell_text.isdigit():
                    current_time = cell_text

                # 강의 정보 확인
                elif cell_text:
                    schedule_entry = {
                        "class_name": cell_text,
                        "class_days": [{"$numberInt": str(current_day)}],
                        "start_time": f"{current_time}:00",
                        "end_time": f"{int(current_time) + 1}:00",
                        "location": "Unknown"  # 기본 위치는 Unknown
                    }
                    schedule.append(schedule_entry)

        return schedule

    except Exception as e:
        print(f"[ERROR] 시간표 추출 중 오류 발생: {e}")
        return []

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

@app.route('/upload-timetable', methods=['POST'])
def upload_timetable():
    """
    클라이언트에서 업로드된 JSON 파일을 분석하고 시간표 데이터를 MongoDB에 저장합니다.
    """
    try:
        # 사용자 정보 확인
        user_id = request.form.get("userId")
        user_name = request.form.get("userName")

        if not user_id or not user_name:
            return jsonify({"status": "error", "message": "사용자 정보가 누락되었습니다."})

        # JSON 파일 처리
        file = request.files.get("ocr_json")
        if not file:
            return jsonify({"status": "error", "message": "OCR JSON 파일이 필요합니다."})

        ocr_json = json.load(file)

        # 시간표 추출
        schedule = extract_schedule_from_json(ocr_json)
        if not schedule:
            return jsonify({"status": "error", "message": "시간표 데이터 추출 실패."})

        # MongoDB 저장 형식으로 데이터 구성
        timetable_data = {
            "_id": user_id,
            "info": {"name": user_name, "number": user_id},
            "schedule": schedule
        }

        # MongoDB에 저장
        collection_timetable.replace_one({"_id": user_id}, timetable_data, upsert=True)
        return jsonify({"status": "success", "message": "시간표 저장 완료.", "timetable": timetable_data})

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
