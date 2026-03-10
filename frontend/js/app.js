const API = "http://localhost:8000";
let currentPage = null;

window.addEventListener("beforeunload", () => { // 페이지 새로고침 시 로그 출력
  console.log("페이지 새로고침 발생");
});

//───────────────────────────────────────
// 인증
//───────────────────────────────────────
function getToken() {
  return sessionStorage.getItem("token");
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  return fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  });
}

//───────────────────────────────────────
// 로그인
//───────────────────────────────────────
async function login() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    alert("모든 항목을 입력해줘.");
    return;
  }

  try {
    const response = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password })
    });

    const data = await response.json();

    if (data.access_token) {
      sessionStorage.setItem("token", data.access_token);
      sessionStorage.setItem("username", data.username || username);

      if (data.nickname) {
        localStorage.setItem("nickname", data.nickname);
      }

      if (data.character) {
        localStorage.setItem("character", data.character);
      }

      window.location.href = "app.html";
      return;
    } else {
      alert("아이디 또는 비밀번호가 일치하지 않습니다.");
    }
  } catch (error) {
    alert("로그인 중 오류가 발생했습니다.");
    console.log(error);
  }
}

//───────────────────────────────────────
// 앱 초기화
//───────────────────────────────────────
async function initApp() {  
  console.log("initApp 다시 실행됨"); // 페이지 새로고침 시 initApp이 다시 실행되는지 확인하기 위한 로그
  
  const token = getToken();

  if (!token) {
    window.location.href = "login.html";
    return;
  }

  try {
    const res = await apiFetch("/auth/me");

    if (!res.ok) {
      sessionStorage.clear();
      window.location.href = "login.html";
      return;
    }

    const user = await res.json();
    sessionStorage.setItem("username", user.username);

    const title = document.getElementById("sidebar-title");
    if (title) {
      title.innerText = ` ${user.nickname || user.username}의 math class🎓`;
    }

    const img = document.getElementById("user-character");
    if (img && user.character) {
      img.src = `assets/images/${user.character}.png`;
    }

    goPage("home");
    bindAppEvents();
  } catch (error) {
    console.log(error);
    window.location.href = "login.html";
  }
}

//───────────────────────────────────────
// 페이지 이동
//───────────────────────────────────────
function goPage(pageName) {

  const pages = document.querySelectorAll(".page");
  pages.forEach(p => (p.style.display = "none"));

  const target = document.getElementById(`page-${pageName}`);
  if (target) target.style.display = "block";

  currentPage = pageName;

  if (pageName === "today") {
    localStorage.setItem("step", "select_unit");
    renderToday();
    loadUnits();
  }

  // AI 자유학습 페이지
  if (pageName === "free") {
    if (typeof initFreeChat === "function") {
      initFreeChat();
    }
  }

  // 시험 페이지
  if (pageName === "exam") {
    if (typeof initExam === "function") {
      initExam();
    }
  }

  // 성적 로그
  if (pageName === "score") {
    if (typeof loadScoreLog === "function") {
      loadScoreLog();
    }
  }

  // ⭐ 지수 토큰 페이지 유지
  if (pageName === "token") {
    if (typeof renderTokenPage === "function") {
      renderTokenPage();
    }
  }
}

function goHome() {
  localStorage.setItem("step", "select_unit");
  goPage("today");
}

//───────────────────────────────────────
// 로그아웃
//───────────────────────────────────────
function logout() {
  sessionStorage.clear();
  window.location.href = "login.html";
}

//───────────────────────────────────────
// MathJax 렌더
//───────────────────────────────────────
function renderMath(targetId) {

  if (!window.MathJax) return;

  if (targetId) {

    const el = document.getElementById(targetId);
    if (!el) return;

    MathJax.typesetPromise([el]).catch(err => {
      console.error("MathJax 렌더링 오류:", err);
    });

    return;
  }

  MathJax.typesetPromise().catch(err => {
    console.error("MathJax 렌더링 오류:", err);
  });
}

//───────────────────────────────────────
// 문제 입력 모달
//───────────────────────────────────────
function openResultModal() {

  const modal = document.getElementById("resultModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";
}

function closeResultModal() {

  const modal = document.getElementById("resultModal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.style.display = "none";
}

//───────────────────────────────────────
// 최종 피드백 모달
//───────────────────────────────────────
function openFeedbackModal() {

  const modal = document.getElementById("feedbackModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";
}

function closeFeedbackModal() {

  const modal = document.getElementById("feedbackModal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.style.display = "none";
}

//───────────────────────────────────────
// 앱 공통 이벤트
//───────────────────────────────────────
function bindAppEvents() {

  const closeBtn = document.getElementById("closeModalBtn");
  const closeFeedbackBtn = document.getElementById("closeFeedbackModalBtn");

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
document.addEventListener("DOMContentLoaded", () => {

  const characterButtons = document.querySelectorAll(".character-btn");

  characterButtons.forEach(button => {

    button.addEventListener("click", () => {

      characterButtons.forEach(btn => btn.classList.remove("selected"));
      button.classList.add("selected");

    });

  });

});