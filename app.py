from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

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

        timetable = timetable_collection.find_one({"_id": user_id})

        if not timetable:
            return jsonify({"status": "error", "message": "시간표를 찾을 수 없습니다."})

        # 시간표 데이터 가공
        schedule = []
        for entry in timetable.get("schedule", []):
            class_name = entry.get("class_name", "")
            start_time = entry.get("start_time", "")
            end_time = entry.get("end_time", "")
            location = entry.get("location", "")

            # class_days에서 $numberInt 값을 추출하여 처리
            class_days = []
            for day in entry.get("class_days", []):
                if isinstance(day, dict) and "$numberInt" in day:
                    class_days.append(int(day["$numberInt"]))
                else:
                    # day가 정수형으로 저장된 경우
                    class_days.append(int(day))

            # 요일별 시간표 추가
            for day in class_days:
                schedule.append({
                    "day": day,
                    "time": f"{start_time}-{end_time}",
                    "class_name": f"{class_name} ({location})"
                })

        return jsonify({"status": "success", "timetable": schedule})
    except Exception as e:
        print(f"ERROR: {str(e)}")  # 디버깅 출력
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})


@app.route('/get_friends', methods=['POST'])
def get_friends():
    try:
        data = request.json
        user_id = data.get("id")
        print(f"DEBUG: Received user ID: {user_id}")  # 디버깅 출력

        # MongoDB에서 친구 데이터 조회
        user_friends = friend_collection.find_one({"_id": user_id})

        if not user_friends:
            print("DEBUG: No friends found for user ID:", user_id)  # 디버깅 출력
            return jsonify({"status": "error", "message": "친구 목록을 찾을 수 없습니다."})

        print("DEBUG: Retrieved friends:", user_friends.get("friends"))  # 디버깅 출력
        return jsonify({"status": "success", "friends": user_friends.get("friends", [])})
    except Exception as e:
        print(f"ERROR: {str(e)}")  # 디버깅 출력
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
