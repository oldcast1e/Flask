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

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_id = data['_id']
        info = data['info']

        if user_collection.find_one({"_id": user_id}):
            return jsonify({"success": False, "message": "이미 존재하는 사용자입니다."})

        user_collection.insert_one({"_id": user_id, "info": info})
        friend_collection.insert_one({"_id": user_id, "info": info, "friends":[]})
        return jsonify({"success": True, "message": "회원가입 성공"})
    except Exception as e:
        return jsonify({"success": False, "message": f"오류 발생: {str(e)}"})

@app.route('/get_timetable', methods=['POST'])
def get_timetable():
    try:
        data = request.json
        user_id = data.get("id")

        timetable = timetable_collection.find_one({"_id": user_id})

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

@app.route('/add_friend', methods=['POST'])
def add_friend():
    try:
        data = request.json
        user_id = data.get("user_id")
        friend_id = data.get("friend_id")
        friend_name = data.get("friend_name")

        # 입력값 검증
        if not user_id or not friend_id or not friend_name:
            return jsonify({"status": "error", "message": "모든 필드를 입력해주세요."})

        # 사용자 확인
        user = friend_collection.find_one({"_id": user_id})
        if not user:
            return jsonify({"status": "error", "message": "사용자를 찾을 수 없습니다."})

        # 친구 확인
        friend = user_collection.find_one({"_id": friend_id})
        if not friend:
            return jsonify({"status": "error", "message": "존재하지 않는 친구 ID입니다."})

        # 이미 친구인지 확인
        if any(f["friend_id"] == friend_id for f in user.get("friends", [])):
            return jsonify({"status": "error", "message": "이미 친구로 추가된 사용자입니다."})

        # 친구 추가
        friend_entry = {
            "friend_id": friend_id,
            "friend_name": friend_name
        }
        friend_collection.update_one(
            {"_id": user_id},
            {"$push": {"friends": friend_entry}}
        )

        return jsonify({"status": "success", "message": f"{friend_name}님이 친구로 추가되었습니다."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

@app.route('/check_user', methods=['POST'])
def check_user():
    try:
        data = request.json
        user_id = data.get("id")

        if not user_id:
            return jsonify({"status": "error", "message": "사용자 ID가 제공되지 않았습니다."})

        # User 클러스터에서 사용자 확인
        user = user_collection.find_one({"_id": user_id})
        if not user:
            return jsonify({"status": "error", "message": "존재하지 않는 사용자입니다."})

        return jsonify({"status": "success", "message": "사용자가 존재합니다."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

@app.route('/remove_friend', methods=['POST'])
def remove_friend():
    try:
        data = request.json
        user_id = data.get("user_id")
        friend_id = data.get("friend_id")

        if not user_id or not friend_id:
            return jsonify({"status": "error", "message": "필수 정보가 누락되었습니다."})

        result = friend_collection.update_one(
            {"_id": user_id},
            {"$pull": {"friends": {"friend_id": friend_id}}}
        )

        if result.modified_count == 0:
            return jsonify({"status": "error", "message": "친구 목록에서 삭제되지 않았습니다."})

        return jsonify({"status": "success", "message": "친구가 성공적으로 삭제되었습니다."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
