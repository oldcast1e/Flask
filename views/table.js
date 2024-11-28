document.addEventListener("DOMContentLoaded", function () {
    const userInfoDiv = document.getElementById("userInfo");
    const timetableBody = document.getElementById("timetableBody");
    const loadingMessage = document.getElementById("loadingMessage");
    const errorMessage = document.getElementById("errorMessage");

    // 요일 매핑 (숫자 -> 요일 인덱스)
    const dayMapping = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5 };

    // 오전 9시 ~ 오후 9시 시간 배열 생성
    const hours = Array.from({ length: 13 }, (_, i) => `${9 + i}:00`);

    // localStorage에서 사용자 ID 가져오기
    const userId = localStorage.getItem("userId");
    if (!userId) {
        errorMessage.style.display = "block";
        errorMessage.textContent = "사용자 정보를 찾을 수 없습니다.";
        return;
    }

    // 시간표 데이터 로드
    async function loadTimetable() {
        loadingMessage.style.display = "block";
        try {
            const response = await fetch("https://login-juko.onrender.com/get_timetable", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ id: userId }),
            });

            const data = await response.json();
            loadingMessage.style.display = "none";

            if (data.status === "error") {
                // 시간표가 없으면 imageUpload.html로 이동
                window.location.href = "imageUpload.html";
                return;
            }

            // 사용자 정보 표시
            const userInfo = data.user_info;
            userInfoDiv.textContent = `${userInfo.name} (${userInfo.number})님의 시간표`;

            // 시간표 데이터 처리
            const schedule = data.timetable.schedule;
            if (schedule.length === 0) {
                // 시간표가 비어있으면 imageUpload.html로 이동
                window.location.href = "imageUpload.html";
                return;
            }

            const tableData = {};
            schedule.forEach((entry) => {
                const { day, start_time, end_time, class_name, location } = entry;

                if (!tableData[start_time]) {
                    tableData[start_time] = {};
                }
                tableData[start_time][dayMapping[day]] = {
                    class_name,
                    end_time,
                    location,
                };
            });

            // 테이블 생성
            generateTable(tableData);
        } 
        catch (error) {
            loadingMessage.style.display = "none";
            errorMessage.style.display = "block";
            errorMessage.textContent = `시간표를 불러오는 데 실패했습니다: ${error.message}`;
        }
    }

    function generateTable(data) {
        timetableBody.innerHTML = ""; // 초기화

        hours.forEach((hour) => {
            const tr = document.createElement("tr");

            // 시간 열
            const timeCell = document.createElement("td");
            timeCell.textContent = hour;
            tr.appendChild(timeCell);

            // 각 요일 열
            for (let i = 1; i <= 5; i++) {
                const cell = document.createElement("td");
                if (data[hour] && data[hour][i]) {
                    const entry = data[hour][i];
                    cell.innerHTML = `${entry.class_name}<br>${entry.location}<br>${hour} - ${entry.end_time}`;
                }
                tr.appendChild(cell);
            }

            timetableBody.appendChild(tr);
        });
    }

    // 시간표 로드 실행
    loadTimetable();
});
