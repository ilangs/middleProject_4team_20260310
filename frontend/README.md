
# Frontend 구조 안내

프론트엔드 UI는 기능 단위로 JS 파일을 분리해 구성했습니다.  
백엔드 기능 연결 시 각 section 파일에서 API를 호출하여 화면에 데이터를 표시하면 됩니다.


## 폴더 구조

frontend/
assets/          → 이미지, 아이콘, 폰트 등 정적 리소스
css/             → 전체 스타일 관리  
  app.css        → 모든 화면 공통 UI 스타일
js/              → 기능별 스크립트
  app.js         → 로그인 처리 / 페이지 이동 / 공통 함수
  section1.js    → 오늘의 학습 화면 (학습 흐름 UI)
  section2.js    → AI 자유 학습 화면 (UI 샘플)
  section3.js    → 시험 화면 + 시험 결과 모달 UI
  section4.js    → 성적 로그 대시보드 (그래프 + 시험 기록 UI)
  section5.js    → 토큰 사용 로그 화면 (UI 자리)
app.html         → 메인 애플리케이션 화면
login.html       → 로그인 / 회원가입 화면


## 백엔드 연결 방식

현재 대부분 화면은 **UI 샘플 형태**로 구성되어 있습니다.

백엔드 API 연결 시  
각 section 파일에서 데이터를 받아 화면에 표시하도록 연결하면 됩니다.

예시
```javascript
fetch("/api/exam/result")


