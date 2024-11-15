const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const multer = require('multer');
const Datastore = require('nedb');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(bodyParser.json());
app.set('view engine', 'ejs'); // EJS 템플릿 엔진 설정
app.set('views', path.join(__dirname, 'views')); // EJS 템플릿 디렉토리 설정

// 경로 설정
const dbPath = path.join(__dirname, 'DB', 'data.db');
const uploadDir = path.join(__dirname, 'DB', 'json');

// NeDB 데이터베이스 설정
const db = new Datastore({ filename: dbPath, autoload: true });

// 파일 업로드를 위한 multer 설정
const upload = multer({ dest: uploadDir });

// 홈 페이지 렌더링
app.get('/', (req, res) => {
  res.render('upload'); // views 폴더 내 upload.ejs 템플릿을 렌더링
});

// JSON 파일 업로드 및 DB 저장 라우트
app.post('/upload/json', upload.single('jsonFile'), (req, res) => {
  const file = req.file;

  if (!file) {
    return res.status(400).json({ error: "No file uploaded" });
  }

  // 업로드된 파일이 JSON 형식인지 확인
  if (!file.originalname.toLowerCase().endsWith('.json')) {
    return res.status(400).json({ error: "Please upload a JSON file." });
  }

  // 파일을 읽어서 JSON 데이터 파싱
  const filePath = path.join(uploadDir, file.filename);
  fs.readFile(filePath, 'utf8', (err, data) => {
    if (err) {
      return res.status(500).json({ error: "Failed to read uploaded file." });
    }

    try {
      const jsonData = JSON.parse(data); // JSON 데이터로 파싱

      // NeDB에 JSON 데이터 삽입
      db.insert(jsonData, (err, newDoc) => {
        if (err) {
          return res.status(500).json({ error: "Failed to save data to database." });
        }

        // 성공 응답 및 업로드 파일 삭제
        fs.unlinkSync(filePath);
        res.status(200).json({
          message: "JSON file uploaded and data saved successfully.",
          data: newDoc
        });
      });
    } catch (parseError) {
      return res.status(400).json({ error: "Invalid JSON format in the uploaded file." });
    }
  });
});

// 서버 시작
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
