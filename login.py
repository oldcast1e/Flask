from flask import Flask, request, jsonify
from flask_cors import CORS  # CORS 추가
from pymongo import MongoClient  # MongoDB 연결을 위해 추가

app = Flask(__name__)
CORS(app)  # 모든 출처에서의 요청을 허용하도록 설정

# MongoDB 클라이언트 설정
from pymongo import MongoClient

# MongoDB 클라이언트 설정 (tls, ssl_cert_reqs=none 명시)
client = MongoClient(
    "mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click",
    tls=True,  # TLS 연결 활성화
    tlsAllowInvalidCertificates=True  # SSL 인증서 무시
)

db = client.OurTime  # OurTime 데이터베이스
collection = db.User  # User 컬렉션

@app.route('/login', methods=['POST'])
def login():
    """
    로그인 요청을 처리하는 API.
    사용자로부터 받은 ID와 PW를 MongoDB에서 확인하고 상태를 반환합니다.
    """
    try:
        data = request.json  # 클라이언트로부터 JSON 데이터를 받음
        user_id = data.get("id")
        user_pw = data.get("pw")

        # ID 확인
        user = collection.find_one({"_id": user_id})

        if not user:
            return jsonify({"status": "error", "message": "아이디가 올바르지 않습니다."})
        elif user["info"]["pw"] != user_pw:
            return jsonify({"status": "error", "message": "비밀번호를 확인해주세요."})
        else:
            return jsonify({"status": "success", "message": f"로그인 성공. 환영합니다, {user['info']['name']}님!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"서버 오류 발생: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
