/**
 * ============================================================
 * app.js  -  앱 전역 공통 모듈
 * ============================================================
 *
 * [역할]
 *   이 파일은 프로젝트의 모든 페이지에서 공유되는 핵심 함수들을
 *   모아 놓은 전역 공통 모듈입니다.
 *
 * [사용 페이지]
 *   - frontend/app.html   (메인 앱 화면)
 *   - frontend/login.html (로그인 화면)
 *
 * [주요 담당 기능]
 *   1. JWT 토큰 관리     : sessionStorage에서 토큰을 읽고 저장
 *   2. API 호출 헬퍼     : apiFetch() - 모든 API 요청에 인증 헤더 자동 추가
 *   3. 앱 초기화         : initApp() - 로그인 여부 확인 후 메인 화면 진입
 *   4. 페이지 라우팅     : goPage() - SPA(단일 페이지 앱) 방식의 화면 전환
 *   5. 로그인/로그아웃   : login(), logout()
 *   6. 수식 렌더링       : renderMath() - MathJax 라이브러리 연동
 *   7. 모달 관리         : 문제 풀이 결과 모달, 최종 피드백 모달
 *
 * [학습 포인트 - 3주차 AI 에이전트 과정]
 *   - sessionStorage vs localStorage 의 차이
 *     · sessionStorage: 브라우저 탭을 닫으면 자동 삭제 (보안상 토큰 저장에 적합)
 *     · localStorage:   브라우저를 꺼도 유지됨 (닉네임, 캐릭터 등 비민감 정보)
 *   - JWT Bearer Token 인증 패턴
 *     · 로그인 성공 시 서버가 발급한 access_token을 클라이언트에 저장
 *     · 이후 모든 API 요청 헤더에 "Authorization: Bearer <토큰>" 을 포함
 *   - SPA(Single Page Application) 라우팅
 *     · 페이지 전환 시 실제 URL 이동 없이 특정 div를 보이거나 숨기는 방식
 * ============================================================
 */

// ─────────────────────────────────────────────────────────────
// API 기본 URL 설정
// 빈 문자열("")이면 현재 서버의 같은 도메인으로 요청 (상대 경로)
// 예: apiFetch("/api/units") → http://현재서버/api/units
// ─────────────────────────────────────────────────────────────
const API = ""

//───────────────────────────────────────
// 인증 및 초기화
//───────────────────────────────────────

/**
 * getToken()
 * ─────────────────────────────────────
 * [역할] sessionStorage에 저장된 JWT 토큰을 꺼내 반환합니다.
 *
 * [JWT란?]
 *   JSON Web Token의 약자. 서버가 로그인 성공 시 발급하는 인증 증표.
 *   "나 로그인한 사람이야"를 증명할 때 사용합니다.
 *
 * [sessionStorage 선택 이유]
 *   · 브라우저 탭을 닫으면 자동으로 삭제 → 보안에 유리
 *   · localStorage는 브라우저를 꺼도 남아있어 탈취 위험이 있음
 *
 * @returns {string|null} 저장된 토큰 문자열, 없으면 null
 */
function getToken() {
  return sessionStorage.getItem("token");
}

/**
 * apiFetch(path, options)
 * ─────────────────────────────────────
 * [역할] 서버 API를 호출하는 헬퍼 함수입니다.
 *        모든 요청에 JWT 인증 헤더를 자동으로 추가해 줍니다.
 *
 * [사용법]
 *   const res = await apiFetch("/api/units");
 *   const res = await apiFetch("/api/explain", { method: "POST", ... });
 *
 * [Bearer Token 패턴]
 *   HTTP 요청 헤더에 아래 형식으로 토큰을 포함합니다:
 *   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
 *   서버는 이 토큰을 검증해 "누가 요청했는지"를 확인합니다.
 *
 * [스프레드 연산자 ...]
 *   ...options.headers 는 기존 헤더를 유지하면서 Authorization을 추가합니다.
 *   예: { "Content-Type": "application/json", Authorization: "Bearer ..." }
 *
 * @param {string} path    - API 경로 (예: "/api/units", "/auth/me")
 * @param {object} options - fetch 옵션 (method, headers, body 등)
 * @returns {Promise<Response>} fetch 응답 객체
 */
async function apiFetch(path, options = {}) {
  // 현재 저장된 JWT 토큰 읽기
  const token = getToken();

  // fetch() 호출: API_URL + 경로, 기존 옵션에 인증 헤더를 추가
  return fetch(`${API}${path}`, {
    ...options,                          // 기존 method, body 등 그대로 유지
    headers: {
      ...(options.headers || {}),        // 기존 헤더 유지 (예: Content-Type)
      // 토큰이 있으면 Authorization 헤더 추가, 없으면 빈 객체 {}
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  });
}

// ⭐ 앱 시작 시 실행될 로직 추가
/**
 * DOMContentLoaded 이벤트 핸들러 (첫 번째)
 * ─────────────────────────────────────────
 * [역할] HTML 문서 파싱이 완료되면 자동으로 실행되는 초기화 코드입니다.
 *
 * [DOMContentLoaded란?]
 *   HTML 파일을 다 읽어서 DOM 트리를 만든 직후 발생하는 이벤트.
 *   이미지나 스타일시트 로딩을 기다리지 않아서 빠르게 실행됩니다.
 *
 * [조건부 initApp 실행]
 *   "sidebar-title" 요소가 있는 페이지(app.html)에서만 initApp()을 호출합니다.
 *   login.html에는 "sidebar-title"이 없으므로 initApp()이 실행되지 않습니다.
 */
document.addEventListener("DOMContentLoaded", () => {
  // 현재 페이지가 메인 앱 페이지(app.html)인 경우에만 initApp 실행
  if (document.getElementById("sidebar-title")) {
    initApp();
  }

  // 기존 캐릭터 선택 이벤트 유지
  // 회원가입 페이지에서 캐릭터 버튼 클릭 시 "selected" 클래스를 토글하는 이벤트
  const characterButtons = document.querySelectorAll(".character-btn");
  characterButtons.forEach(button => {
    button.addEventListener("click", () => {
      // 다른 모든 버튼에서 "selected" 클래스 제거
      characterButtons.forEach(btn => btn.classList.remove("selected"));
      // 클릭한 버튼에만 "selected" 클래스 추가 (강조 표시)
      button.classList.add("selected");
    });
  });
});

//───────────────────────────────────────
// 로그인 (login.html 내 스크립트에서 호출하거나 연결됨)
//───────────────────────────────────────

/**
 * login()
 * ─────────────────────────────────────
 * [역할] 로그인 폼의 아이디/비밀번호를 서버에 전송하고,
 *        성공 시 JWT 토큰을 sessionStorage에 저장합니다.
 *
 * [사용 페이지] login.html의 "로그인" 버튼 onclick 이벤트
 *
 * [API 호출]
 *   엔드포인트: POST /auth/login
 *   전송 형식:  application/x-www-form-urlencoded (HTML 폼 방식)
 *   전송 데이터: { username: "학생아이디", password: "비밀번호" }
 *   응답 예시:  { access_token: "eyJ...", username: "홍길동", nickname: "길동이", character: "rumi" }
 *
 * [URLSearchParams 사용 이유]
 *   OAuth2 표준의 로그인 엔드포인트는 JSON이 아닌
 *   application/x-www-form-urlencoded 형식을 요구합니다.
 *   URLSearchParams는 "username=admin&password=1234" 형태로 자동 변환해줍니다.
 *
 * [로그인 성공 후 저장 데이터]
 *   · sessionStorage["token"]    - JWT 액세스 토큰 (API 인증용)
 *   · sessionStorage["username"] - 로그인한 사용자 아이디
 *   · localStorage["nickname"]   - 닉네임 (탭 닫아도 유지)
 *   · localStorage["character"]  - 선택한 캐릭터 이름 (탭 닫아도 유지)
 */
async function login() {
  // 입력 필드에서 값 가져오기 (trim()으로 앞뒤 공백 제거)
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  // 빈 칸 입력 방지
  if (!username || !password) {
    alert("모든 항목을 입력해줘.");
    return;
  }

  try {
    // POST /auth/login 요청 (OAuth2 표준 폼 형식)
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password })
    });

    // JSON 응답 파싱
    const data = await response.json();

    // 토큰이 있으면 로그인 성공
    if (data.access_token) {
      // JWT 토큰을 sessionStorage에 저장 (탭 닫으면 자동 삭제)
      sessionStorage.setItem("token", data.access_token);
      // 사용자명 저장 (서버 응답 우선, 없으면 입력한 username 사용)
      sessionStorage.setItem("username", data.username || username);

      // 닉네임과 캐릭터는 localStorage에 저장 (브라우저 재시작 후에도 유지)
      if (data.nickname) localStorage.setItem("nickname", data.nickname);
      if (data.character) localStorage.setItem("character", data.character);

      // 메인 앱 화면으로 이동 (/main 경로 → server.py에서 app.html 렌더링)
      window.location.href = "/main";
    } else {
      // 서버가 토큰을 주지 않으면 인증 실패
      alert("아이디 또는 비밀번호가 일치하지 않습니다.");
    }
  } catch (error) {
    // 네트워크 오류 등 예외 처리
    alert("로그인 중 오류가 발생했습니다.");
    console.error(error);
  }
}

//───────────────────────────────────────
// 앱 초기화
//───────────────────────────────────────

/**
 * initApp()
 * ─────────────────────────────────────
 * [역할] app.html 로드 시 가장 먼저 실행되는 초기화 함수입니다.
 *        현재 사용자가 로그인 상태인지 서버에 확인하고,
 *        인증된 사용자라면 사이드바에 이름/캐릭터를 표시합니다.
 *
 * [호출 시점] DOMContentLoaded 이벤트 발생 시 (페이지 로드 완료 후)
 *
 * [인증 흐름]
 *   1. sessionStorage에서 토큰 확인 → 없으면 로그인 페이지로 이동
 *   2. GET /auth/me 요청으로 서버에서 현재 사용자 정보 조회
 *   3. 응답이 실패(401 등)이면 토큰이 만료된 것 → 로그인 페이지로 이동
 *   4. 성공이면 사이드바 제목, 캐릭터 이미지 업데이트 후 홈 화면 표시
 *
 * [API 호출]
 *   엔드포인트: GET /auth/me
 *   응답 예시:  { username: "admin", nickname: "길동이", character: "rumi" }
 */
async function initApp() {
  console.log("🚀 initApp 실행: 유저 인증 확인 중...");

  // sessionStorage에서 JWT 토큰 확인
  const token = getToken();

  // 토큰이 없으면 → 로그인 화면으로 즉시 이동
  if (!token) {
    window.location.href = "/"; // ⭐ login.html 대신 루트 경로로 이동
    return;
  }

  try {
    // GET /auth/me : 현재 토큰이 유효한지, 누구의 토큰인지 서버에 확인
    const res = await apiFetch("/auth/me");

    // 서버가 오류 응답(401 Unauthorized 등)을 돌려주면 토큰이 무효
    if (!res.ok) {
      sessionStorage.clear();           // 잘못된 토큰 삭제
      window.location.href = "/"; // ⭐ 인증 실패 시 루트로
      return;
    }

    // 사용자 정보 JSON 파싱
    const user = await res.json();
    // username을 sessionStorage에 저장 (다른 함수에서 사용)
    sessionStorage.setItem("username", user.username);

    // 사이드바 제목 업데이트: "닉네임의 math class🎓"
    const title = document.getElementById("sidebar-title");
    if (title) {
      title.innerText = ` ${user.nickname || user.username}의 math class🎓`;
    }

    // 사이드바 캐릭터 이미지 업데이트
    // 예: user.character = "rumi" → /assets/images/rumi.png
    const img = document.getElementById("user-character");
    if (img && user.character) {
      // ⭐ 경로 앞에 / 추가하여 절대 경로 보장
      img.src = `/assets/images/${user.character}.png`;
    }

    // 홈 화면으로 이동 (기본 진입 화면)
    goPage("home");
    // 모달 닫기 버튼 등 공통 이벤트 바인딩
    bindAppEvents();
  } catch (error) {
    // 네트워크 오류 등 예외 시 로그인 화면으로 이동
    console.error(error);
    window.location.href = "/";
  }
}

//───────────────────────────────────────
// 페이지 이동
//───────────────────────────────────────

/**
 * goPage(pageName)
 * ─────────────────────────────────────
 * [역할] SPA(Single Page Application) 방식의 페이지 전환 함수입니다.
 *        실제 URL을 바꾸지 않고 특정 div를 보이거나 숨겨서
 *        마치 페이지가 바뀐 것처럼 보이게 합니다.
 *
 * [SPA 라우팅 원리]
 *   app.html에는 page-home, page-today, page-free 등의 id를 가진
 *   여러 div들이 있고, 기본적으로 모두 display:none 입니다.
 *   goPage("today")를 호출하면:
 *   1. 모든 .page div를 display:none으로 숨김
 *   2. id="page-today"인 div만 display:block으로 표시
 *
 * [페이지별 초기화 함수 연결]
 *   각 페이지로 이동할 때 해당 섹션의 초기화 함수를 호출합니다:
 *   · "today" → loadUnits(), renderToday()   (section1.js)
 *   · "free"  → initFreeChat()               (section2.js)
 *   · "exam"  → initExam()                   (section3.js)
 *   · "score" → loadScoreLog()               (section4.js)
 *   · "token" → renderTokenPage()            (section5.js)
 *
 * @param {string} pageName - 이동할 페이지 이름 (예: "home", "today", "free")
 */
function goPage(pageName) {

  // 1단계: 모든 .page 클래스 요소를 화면에서 숨김
  const pages = document.querySelectorAll(".page");
  pages.forEach(p => (p.style.display = "none"));

  // 2단계: 이동하려는 페이지 div만 보이게 설정
  // 예: pageName = "today" → id="page-today" 인 div를 block으로
  const target = document.getElementById(`page-${pageName}`);
  if (target) target.style.display = "block";

  // 현재 페이지 이름을 전역 변수에 저장 (다른 함수에서 참조용)
  currentPage = pageName;

  //ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ
  // 홈 화면 전환 시 배경 동영상 재생/일시정지 처리
  //ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ
  //app.js에서 페이지 이동 시마다 홈 비디오 재생/멈춤 처리 추가
  const homeVideo = document.getElementById("homeVideo");

  if (homeVideo) {
    if (pageName === "home") {
      // 홈 화면일 때만 비디오 재생 (에러가 나도 무시: .catch(() => {}))
      homeVideo.play().catch(() => {});
    } else {
      // 다른 화면으로 이동하면 비디오 정지 및 처음으로 되감기
      homeVideo.pause();
      homeVideo.currentTime = 0;
    }
  }
  // ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ

  // 오늘 학습 페이지(section1.js) 초기화
  if (pageName === "today") {
    // localStorage의 학습 단계를 초기 단계("단원 선택")로 리셋
    localStorage.setItem("step", "select_unit");
    renderToday();   // 오늘 학습 화면 렌더링 (section1.js)
    loadUnits();     // 서버에서 단원 목록 가져오기 (section1.js)
  }

  // AI 자유학습 페이지(section2.js) 초기화
  if (pageName === "free") {
    // initFreeChat 함수가 존재하는지 확인 후 호출 (section2.js에 정의됨)
    if (typeof initFreeChat === "function") {
      initFreeChat();
    }
  }

  // 시험 페이지(section3.js) 초기화
  if (pageName === "exam") {
    // initExam 함수가 존재하는지 확인 후 호출 (section3.js에 정의됨)
    if (typeof initExam === "function") {
      initExam();
    }
  }

  // 성적 로그 페이지(section4.js) 초기화
  if (pageName === "score") {
    // loadScoreLog 함수가 존재하는지 확인 후 호출 (section4.js에 정의됨)
    if (typeof loadScoreLog === "function") {
      loadScoreLog();
    }
  }

  // ⭐ 지수 토큰 페이지(section5.js) 초기화
  if (pageName === "token") {
    // renderTokenPage 함수가 존재하는지 확인 후 호출 (section5.js에 정의됨)
    if (typeof renderTokenPage === "function") {
      renderTokenPage();
    }
  }
}

/**
 * goHome()
 * ─────────────────────────────────────
 * [역할] 사이드바의 "홈" 또는 "오늘 학습" 버튼 클릭 시 호출됩니다.
 *        학습 단계를 초기화하고 "today" 페이지로 이동합니다.
 */
function goHome() {
  // 학습 단계를 '단원 선택' 단계로 초기화 (처음부터 다시 시작)
  localStorage.setItem("step", "select_unit");
  goPage("today");
}

//───────────────────────────────────────
// 로그아웃
//───────────────────────────────────────

/**
 * logout()
 * ─────────────────────────────────────
 * [역할] 현재 사용자를 로그아웃 처리합니다.
 *
 * [동작]
 *   1. sessionStorage 전체 삭제 → JWT 토큰이 사라져 더 이상 API 호출 불가
 *   2. 루트 경로(/)로 이동 → login.html 화면으로 돌아감
 *
 * [주의] localStorage는 삭제하지 않습니다.
 *   닉네임, 캐릭터 등의 정보는 다음 로그인 시에도 남아있어야 하기 때문입니다.
 */
function logout() {
  // sessionStorage 전체 삭제 (토큰, username 등 인증 정보 모두 제거)
  sessionStorage.clear();
  // 로그인 페이지로 리다이렉트
  window.location.href = "/";
}

//───────────────────────────────────────
// MathJax 렌더
//───────────────────────────────────────

/**
 * renderMath(targetId)
 * ─────────────────────────────────────
 * [역할] MathJax 라이브러리를 사용해 수식 텍스트를 아름다운
 *        수학 기호로 변환합니다.
 *
 * [MathJax란?]
 *   LaTeX 수식 표기법을 HTML에서 예쁘게 렌더링해주는 JavaScript 라이브러리.
 *   예: \(\frac{1}{2}\) → 화면에 분수 형태로 표시
 *
 * [사용 예시]
 *   renderMath("solutionText");  → id="solutionText" 요소 내부의 수식만 렌더링
 *   renderMath();                → 전체 페이지의 수식 렌더링
 *
 * @param {string|undefined} targetId - 렌더링할 요소의 id (없으면 전체 페이지)
 */
function renderMath(targetId) {

  // MathJax 라이브러리가 로드되지 않았으면 실행 안 함
  if (!window.MathJax) return;

  if (targetId) {
    // 특정 요소만 렌더링 (성능 최적화: 전체 대신 일부만 처리)
    const el = document.getElementById(targetId);
    if (!el) return;

    // typesetPromise: MathJax 3.x 비동기 렌더링 함수
    MathJax.typesetPromise([el]).catch(err => {
      console.error("MathJax 렌더링 오류:", err);
    });

    return;
  }

  // targetId 없으면 전체 페이지 수식 렌더링
  MathJax.typesetPromise().catch(err => {
    console.error("MathJax 렌더링 오류:", err);
  });
}

//───────────────────────────────────────
// 문제 입력 모달
//───────────────────────────────────────

/**
 * openResultModal()
 * ─────────────────────────────────────
 * [역할] id="resultModal" 인 모달 창을 화면에 표시합니다.
 *
 * [모달이란?]
 *   현재 화면 위에 겹쳐서 팝업처럼 뜨는 UI 요소.
 *   배경을 반투명하게 어둡게 하고 중앙에 내용을 보여줍니다.
 *
 * [hidden 클래스와 display 스타일 병행 사용 이유]
 *   CSS에서 .hidden { display: none } 으로 정의되어 있을 수 있고,
 *   JS에서도 style.display를 제어해 두 방식 모두 호환합니다.
 */
function openResultModal() {

  const modal = document.getElementById("resultModal");
  if (!modal) return;

  // hidden 클래스 제거 (CSS에서 숨겨둔 것 해제)
  modal.classList.remove("hidden");
  // flex 레이아웃으로 표시 (모달 내용을 가운데 정렬하기 위해 flex 사용)
  modal.style.display = "flex";
}

/**
 * closeResultModal()
 * ─────────────────────────────────────
 * [역할] id="resultModal" 인 모달 창을 닫습니다.
 *        닫기 전에 재생 중인 음성(TTS)을 먼저 정지합니다.
 */
function closeResultModal() {
  // 1. 음성 즉시 중지 및 상태 초기화
  // 모달을 닫을 때 TTS 음성이 계속 재생되는 버그를 방지
  stopAllModalAudio();

  // 2. 모달 닫기 로직
  const modal = document.getElementById("resultModal");
  if (modal) {
    modal.classList.add("hidden");    // hidden 클래스 추가 (CSS로 숨김)
    modal.style.display = "none";    // 직접 숨김 처리
  }
}

//───────────────────────────────────────
// 최종 피드백 모달
//───────────────────────────────────────

/**
 * openFeedbackModal()
 * ─────────────────────────────────────
 * [역할] 문제 채점 후 최종 피드백을 보여주는 모달을 열어줍니다.
 *        id="feedbackModal" 인 요소를 화면에 표시합니다.
 *
 * [언제 호출되나?]
 *   submitCurrentAnswer() 에서 채점 결과를 받은 후 → showFinalFeedbackModal() 호출 →
 *   그 안에서 openFeedbackModal() 을 호출합니다. (section1.js)
 */
function openFeedbackModal() {

  const modal = document.getElementById("feedbackModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";
}

/**
 * closeFeedbackModal()
 * ─────────────────────────────────────
 * [역할] 최종 피드백 모달을 닫습니다.
 *        "다시 풀기" 또는 "다른 단원 선택" 버튼 클릭 시 자동 호출됩니다.
 */
function closeFeedbackModal() {

  const modal = document.getElementById("feedbackModal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.style.display = "none";
}

//───────────────────────────────────────
// 앱 공통 이벤트
//───────────────────────────────────────

/**
 * bindAppEvents()
 * ─────────────────────────────────────
 * [역할] 앱 전체에서 공통으로 사용하는 이벤트 리스너를 등록합니다.
 *        initApp() 완료 후 한 번 호출됩니다.
 *
 * [dataset.bound 패턴]
 *   버튼에 "data-bound=1" 속성을 추가해
 *   이벤트가 이미 등록된 버튼에 중복 등록되는 것을 방지합니다.
 *   goPage() 가 여러 번 호출돼도 이벤트가 여러 번 걸리지 않습니다.
 */
function bindAppEvents() {

  // 문제 풀이 결과 모달의 닫기(X) 버튼
  const closeBtn = document.getElementById("closeModalBtn");
  // 최종 피드백 모달의 닫기(X) 버튼
  const closeFeedbackBtn = document.getElementById("closeFeedbackModalBtn");

  // data-bound 속성이 없으면 이벤트 등록 (중복 방지)
  if (closeBtn && !closeBtn.dataset.bound) {
    closeBtn.dataset.bound = "1";
    closeBtn.addEventListener("click", closeResultModal);
  }

  if (closeFeedbackBtn && !closeFeedbackBtn.dataset.bound) {
    closeFeedbackBtn.dataset.bound = "1";
    closeFeedbackBtn.addEventListener("click", closeFeedbackModal);
  }
}

//───────────────────────────────────────
// 캐릭터 선택
//───────────────────────────────────────

/**
 * DOMContentLoaded 이벤트 핸들러 (두 번째)
 * ─────────────────────────────────────────
 * [역할] 캐릭터 선택 버튼들의 클릭 이벤트를 등록합니다.
 *        회원가입 페이지에서 사용합니다.
 *
 * [동작]
 *   .character-btn 클래스를 가진 모든 버튼에 클릭 이벤트를 등록하여,
 *   클릭된 버튼에만 "selected" 클래스를 추가합니다.
 *   나머지 버튼에서는 "selected" 클래스를 제거해 단일 선택을 보장합니다.
 *
 * [참고] 이 이벤트 핸들러는 위의 첫 번째 DOMContentLoaded 핸들러와
 *        별도로 등록됩니다. 두 핸들러 모두 DOM 로드 후 실행됩니다.
 */
document.addEventListener("DOMContentLoaded", () => {

  // 캐릭터 선택 버튼 목록 가져오기
  const characterButtons = document.querySelectorAll(".character-btn");

  characterButtons.forEach(button => {

    button.addEventListener("click", () => {

      // 모든 버튼에서 "selected" 강조 효과 제거
      characterButtons.forEach(btn => btn.classList.remove("selected"));
      // 클릭한 버튼에만 "selected" 효과 추가 (CSS에서 테두리 강조 등 처리)
      button.classList.add("selected");

    });

  });

});
