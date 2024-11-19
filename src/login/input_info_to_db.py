from pymongo import MongoClient

# MongoDB 클라이언트 연결
client = MongoClient("mongodb+srv://kylhs0705:smtI18Nl4WqtRUXX@team-click.s8hg5.mongodb.net/?retryWrites=true&w=majority&appName=Team-Click")

# OurTime 데이터베이스와 User 컬렉션 선택
db = client.OurTime
collection = db.User

# 로그인 정보 예시 데이터
user1 = {
    "_id": "21011898",
    "info": {
        "name": "이헌성",
        "pw": "sjulhs"
    }
}
user2 = {
    "_id": "21011890",
    "info": {
        "name": "홍길동",
        "pw": "sjuhgd"
    }
}
user3 = {
    "_id": "21011891",
    "info": {
        "name": "전우치",
        "pw": "sjujuc"
    }
}

# 데이터 리스트 생성
user_list = [user1, user2, user3]

# 데이터 삽입
collection.insert_many(user_list)

print("User 컬렉션에 로그인 정보가 성공적으로 저장되었습니다.")
