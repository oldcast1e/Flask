from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os  # 환경 변수 사용

# Flask 앱 설정
app = Flask(__name__)
CORS(app)  # 모든 도메인에서 요청 허용

client = MongoClient(
    "mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click",
    tls=True,
    tlsAllowInvalidCertificates=True
)

db = client.OurTime
user_collection = db.User
timetable_collection = db.timetable  # 클러스터 이름 주의(timetable로 수정)
friend_collection = db.friend

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        user_id = data.get("id")
        user_pw = data.get("pw")

        user = user_collection.find_one({"_id": user_id})

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
        
        # MongoDB 조회
        timetable = timetable_collection.find_one({"_id": user_id})
        if not timetable:
            return jsonify({"status": "error", "message": f"시간표를 찾을 수 없습니다. ID: {user_id}"})

        # Debugging: 반환된 데이터 출력
        # print("DEBUG: Retrieved Timetable:", timetable)

        schedule = []
        for entry in timetable.get("schedule", []):
            class_name = entry.get("class_name", "")
            start_time = entry.get("start_time", "")
            end_time = entry.get("end_time", "")
            location = entry.get("location", "")

            if not class_name or not start_time or not end_time or not entry.get("class_days"):
                continue

            for day in entry.get("class_days", []):
                day_int = int(day.get("$numberInt", -1))
                if day_int == -1:
                    continue
                schedule.append({
                    "day": day_int,
                    "start_time": start_time,
                    "end_time": end_time,
                    "class_name": class_name,
                    "location": location
                })

        # 최종 응답 JSON
        return jsonify({
            "status": "success",
            "timetable": {"schedule": schedule}
        })
    except Exception as e:
        # 디버깅 메시지 출력
        print(f"ERROR: {str(e)}")
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})


@app.route('/get_friends', methods=['POST'])
def get_friends():
    try:
        data = request.json
        user_id = data.get("id")
        user_friends = friend_collection.find_one({"_id": user_id})

        if not user_friends:
            return jsonify({"status": "error", "message": "친구 목록을 찾을 수 없습니다."})

        return jsonify({"status": "success", "friends": user_friends.get("friends", [])})
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
