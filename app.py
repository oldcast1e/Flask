from flask import Flask, jsonify
from flask_cors import CORS  # Flask-CORS 추가
import os

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# 특정 도메인만 허용하려면 다음처럼 지정합니다.
# CORS(app, origins=["https://your-allowed-domain.com"])

@app.route('/api', methods=['GET'])
def api():
  # 어떤 경로로 들어와서 , 어떤 데이터가 서버에 들어옴 

    response_data = {
        "message": "Hello, World!",
        "status": "success",
        "data": {
            "example_key": "example_value"
        }
    }
  # 서버로 들어온 데이터를 가공해서 , json 형태로 만든 후 클라이언트에 응답으로 보냄 
    return jsonify(response_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render의 PORT 환경 변수를 사용
    app.run(host="0.0.0.0", port=port)  # Render에서 인식할 수 있도록 host와 port 지정
