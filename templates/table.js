class Timetable {
    constructor(userId, userName) {
        this.userId = userId;
        this.userName = userName;
    }

    // 사용자 정보 표시
    displayUserInfo() {
        const userInfoDiv = document.getElementById('userInfo');
        userInfoDiv.textContent = `사용자: ${this.userName} (${this.userId})`;
    }

    // 시간표 데이터를 가져와 테이블에 렌더링
    async fetchTimetable() {
        try {
            const response = await fetch('http://127.0.0.1:5001/get_timetable', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ id: this.userId }),
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.renderTimetable(data.timetable);
            } else {
                console.error('시간표 데이터를 가져오지 못했습니다:', data.message);
                alert(data.message);
            }
        } catch (error) {
            console.error('서버와 통신 중 오류가 발생했습니다:', error);
            alert('서버와 통신 중 오류가 발생했습니다.');
        }
    }

    // 시간표 데이터 렌더링
    renderTimetable(timetable) {
        const timetableBody = document.getElementById('timetableBody');
        const days = ['월요일', '화요일', '수요일', '목요일', '금요일'];

        // 시간표 초기화
        const rows = {};

        timetable.forEach((entry) => {
            const { day, time, class_name } = entry;

            if (!rows[time]) {
                rows[time] = Array(5).fill(''); // 월~금 빈 셀 초기화
            }

            // 요일에 해당하는 셀 채우기
            rows[time][day - 1] = class_name;
        });

        // 테이블 렌더링
        Object.entries(rows).forEach(([time, classes]) => {
            const row = document.createElement('tr');
            const timeCell = document.createElement('td');
            timeCell.textContent = time;
            row.appendChild(timeCell);

            classes.forEach((classInfo) => {
                const cell = document.createElement('td');
                cell.textContent = classInfo || '';
                row.appendChild(cell);
            });

            timetableBody.appendChild(row);
        });
    }
}
