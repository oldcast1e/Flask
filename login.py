from flask import Flask, request, render_template
from pymongo import MongoClient

app = Flask(__name__)

# MongoDB 클라이언트 설정
client = MongoClient("mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click")
db = client.OurTime  # OurTime 데이터베이스
collection = db.User  # User 컬렉션

@app.route('/')
def home():
    # 로그인 페이지 렌더링
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    # 사용자가 입력한 ID와 PW 가져오기
    user_id = request.form['id']
    user_pw = request.form['pw']

    # MongoDB에서 ID 검색
    user = collection.find_one({"_id": user_id})

    if not user:
        # ID가 존재하지 않는 경우
        return render_template('login.html', message="아이디가 올바르지 않습니다.")
    elif user["info"]["pw"] != user_pw:
        # PW가 일치하지 않는 경우
        return render_template('login.html', message="비밀번호를 확인해주세요.")
    else:
        # ID와 PW가 일치하는 경우
        return render_template('login.html', message=f"로그인 성공. 환영합니다, {user['info']['name']}님!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)  # 포트를 5001로 변경
