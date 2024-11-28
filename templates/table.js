class Timetable {
    constructor(userId, userName) {
        this.userId = userId;
        this.userName = userName;
        // this.apiUrl = 'https://flask-xrjv.onrender.com/get_timetable'; // Render 서버 URL
        this.apiUrl = 'http://127.0.0.1:5001/get_timetable'; // Render 서버 URL
        this.tableBody = document.getElementById('timetableBody');
        this.container = document.getElementById('timetableContainer');
        this.userInfoDiv = document.getElementById('userInfo');
    }

    displayUserInfo() {
        this.userInfoDiv.textContent = `현재 사용자: ID - ${this.userId}, 이름 - ${this.userName}`;
    }

    fetchTimetable() {
        fetch(this.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: this.userId }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.renderTimetable(data.timetable.schedule); // JSON 데이터의 schedule 사용
                } else {
                    this.displayNoTimetableMessage();
                }
            })
            .catch(error => console.error('Error:', error));
    }

    renderTimetable(schedule) {
        this.tableBody.innerHTML = ''; // 초기화
        const timeSlots = Array.from({ length: 18 }, (_, i) => {
            const hours = 9 + Math.floor(i);
            return `${hours}:00`;
        });

        timeSlots.forEach(slot => {
            const row = document.createElement('tr');
            const timeCell = document.createElement('td');
            timeCell.textContent = slot;
            row.appendChild(timeCell);

            for (let day = 1; day <= 5; day++) {
                const cell = document.createElement('td');
                const classes = schedule.filter(item =>
                    item.Class_days.some(d => d.$numberInt == day) &&
                    item.Class_start_time === slot
                );
                if (classes.length > 0) {
                    cell.textContent = `${classes[0].Class_name} (${classes[0].Location})`;
                    cell.rowSpan = parseInt(classes[0].Class_end_time.split(':')[0]) - parseInt(classes[0].Class_start_time.split(':')[0]);
                    timeCell.style.verticalAlign = "middle"; // 중간 정렬
                }
                row.appendChild(cell);
            }

            this.tableBody.appendChild(row);
        });
    }

    displayNoTimetableMessage() {
        this.container.innerHTML = ''; // 기존 콘텐츠 초기화

        const message = document.createElement('p');
        message.textContent = "시간표가 없습니다!";
        message.style.fontSize = '18px';
        message.style.color = 'red';
        message.style.textAlign = 'center';
        this.container.appendChild(message);

        const uploadButton = document.createElement('button');
        uploadButton.textContent = '이미지 업로드 페이지로 이동';
        uploadButton.style.marginTop = '20px';
        uploadButton.style.padding = '10px 20px';
        uploadButton.style.backgroundColor = '#b93234';
        uploadButton.style.color = 'white';
        uploadButton.style.border = 'none';
        uploadButton.style.borderRadius = '5px';
        uploadButton.style.cursor = 'pointer';

        uploadButton.addEventListener('click', () => {
            window.location.href = 'imageUpload.html';
        });

        this.container.appendChild(uploadButton);
    }
}

// 사용자 정보 가져오기
document.addEventListener('DOMContentLoaded', () => {
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');

    if (userId && userName) {
        const timetable = new Timetable(userId, userName);
        timetable.displayUserInfo();
        timetable.fetchTimetable();
    } else {
        alert('로그인 정보가 없습니다. 로그인 페이지로 이동합니다.');
        window.location.href = 'main.html';
    }
});

        