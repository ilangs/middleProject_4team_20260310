// ─────────────────────────────────────────────────────────
// section3.js  ─  시험 (📝 exam) 섹션
// ─────────────────────────────────────────────────────────

let examProblems = [];
let examTimer = null;
let examTimeLeft = 2400;
let examStarted = false;
let examSubmitting = false;
let examModalClosable = false;
let examPendingSaveData = null;

function initExam() {
  if (examStarted && !examSubmitting) return;

  resetExamState();
  bindExamModalEvents();
  loadExamUnits();
}

function resetExamState() {
  examProblems = [];
  examStarted = false;
  examSubmitting = false;
  examTimeLeft = 2400;
  examModalClosable = false;
  examPendingSaveData = null;

  if (examTimer) {
    clearInterval(examTimer);
    examTimer = null;
  }

  const timerBox = document.getElementById("exam-timer-box");
  const questionsBox = document.getElementById("exam-questions-container");
  const submitArea = document.getElementById("exam-submit-area");
  const startBtn = document.getElementById("exam-start-btn");
  const timerDisplay = document.getElementById("exam-timer-display");
  const modal = document.getElementById("examResultModal");
  const body = document.getElementById("examResultBody");
  const confirmBtn = document.getElementById("examResultConfirmBtn");
  const unitSel = document.getElementById("exam-unit-select");
  const makeBtn = document.getElementById("exam-make-btn");
  const submitBtn = document.getElementById("exam-submit-btn");
 
  if (timerBox) timerBox.style.display = "none";

  if (questionsBox) {
    questionsBox.classList.remove("exam-locked", "exam-unlocked"); // 클래스 초기화
    questionsBox.style.display = "none";
    questionsBox.innerHTML = "";
  }

  if (submitArea) submitArea.style.display = "none";
  if (startBtn) startBtn.disabled = true;

  if (timerDisplay) {
    timerDisplay.textContent = "40:00";
    timerDisplay.style.color = "";
    timerDisplay.style.fontWeight = "";
  }

  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }

  if (body) body.innerHTML = "";

  if (confirmBtn) {
    confirmBtn.textContent = "확인";
    confirmBtn.style.display = "inline-block";
    confirmBtn.disabled = false;
  }

  if (unitSel) unitSel.disabled = false;
  if (makeBtn) makeBtn.disabled = false;

  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.textContent = "답안지 제출";
  }
}

async function loadExamUnits() {
  const select = document.getElementById("exam-unit-select");
  if (!select) return;

  try {
    const res = await apiFetch("/api/units");
    const data = await res.json();

    select.innerHTML = '<option value="">단원 선택</option>';
    (data.units || []).forEach(unit => {
      const opt = document.createElement("option");
      opt.value = unit;
      opt.text = unit;
      select.add(opt);
    });
  } catch (e) {
    console.error("단원 목록 로드 실패", e);
  }

  const makeBtn = document.getElementById("exam-make-btn");
  const startBtn = document.getElementById("exam-start-btn");
  const submitBtn = document.getElementById("exam-submit-btn");

  if (makeBtn && !makeBtn.dataset.examBound) {
    makeBtn.dataset.examBound = "1";
    makeBtn.addEventListener("click", makeExamPaper);
  }

  if (startBtn && !startBtn.dataset.examBound) {
    startBtn.dataset.examBound = "1";
    startBtn.addEventListener("click", startExamTimer);
  }

  if (submitBtn && !submitBtn.dataset.examBound) {
    submitBtn.dataset.examBound = "1";
    submitBtn.addEventListener("click", submitExam);
  }
}

async function makeExamPaper() {
  const unit = document.getElementById("exam-unit-select")?.value;

  if (!unit) {
    alert("단원을 선택하세요.");
    return;
  }

  if (examStarted) {
    alert("시험이 이미 진행 중입니다.");
    return;
  }

  const makeBtn = document.getElementById("exam-make-btn");
  if (makeBtn) {
    makeBtn.disabled = true;
    makeBtn.textContent = "문제 생성 중...";
  }

  try {
    const res = await apiFetch("/api/exam/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ unit_name: unit })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || "문제를 불러오는데 실패했습니다.");
      return;
    }

    const data = await res.json();
    examProblems = data.problems || [];

    console.log("시험 정답 목록");
    examProblems.forEach((prob, idx) => {
      console.log(`${idx + 1}번 정답:`, prob.answer || prob["정답"] || prob["답"] || "");
    });

    if (examProblems.length === 0) {
      alert("해당 단원에 문제가 없습니다.");
      return;
    }

    renderExamQuestions(examProblems);

    const startBtn = document.getElementById("exam-start-btn");
    const timerBox = document.getElementById("exam-timer-box");
    const submitArea = document.getElementById("exam-submit-area");

    if (startBtn) startBtn.disabled = false;
    if (timerBox) timerBox.style.display = "block";
    if (submitArea) submitArea.style.display = "block";

    alert(`${examProblems.length}개 문제가 생성되었습니다.\n"시험 시작" 버튼을 눌러 타이머를 시작하세요.`);
  } catch (e) {
    console.error("시험지 생성 오류", e);
    alert("시험지 생성 중 오류가 발생했습니다.");
  } finally {
    if (makeBtn) {
      makeBtn.disabled = false;
      makeBtn.textContent = "시험지 만들기";
    }
  }
}

function renderExamQuestions(problems) {
  const container = document.getElementById("exam-questions-container");
  if (!container) return;

  container.innerHTML = "";
  container.style.display = "block";

  // ⭐ [추가] 문제를 생성하자마자 흐리게 처리합니다.
  container.classList.add("exam-locked");
  container.classList.remove("exam-unlocked");

  problems.forEach((prob, idx) => {
    const num = idx + 1;
    const probText = prob["문제"] || "(문제 없음)";

    const card = document.createElement("div");
    card.className = "card";
    card.style.marginBottom = "12px";
    card.innerHTML = `
      <p style="font-size:18px; font-weight:bold; margin:0 0 10px 0;" id="exam-q-text-${num}">
        ${num}번. ${escapeHtml(probText)}
      </p>
      <input
        type="text"
        id="exam-answer-${num}"
        class="exam-answer-input"
        placeholder="답 입력"
        autocomplete="off"
        style="width:100%; padding:10px; font-size:17px; border:1px solid #ccc; box-sizing:border-box;"
      >
    `;
    container.appendChild(card);
  });

  if (typeof renderMath === "function") {
    setTimeout(() => {
      try {
        renderMath();
      } catch (e) {}
    }, 100);
  }
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function startExamTimer() {
  if (examStarted) {
    alert("이미 시험이 시작되었습니다.");
    return;
  }

  if (examProblems.length === 0) {
    alert("먼저 시험지를 만들어주세요.");
    return;
  }

  examStarted = true;

  const startBtn = document.getElementById("exam-start-btn");
  const makeBtn = document.getElementById("exam-make-btn");
  const unitSel = document.getElementById("exam-unit-select");
  // ⭐ [추가] 문제 컨테이너의 흐림 효과를 제거하고 선명하게 만듭니다.
  const container = document.getElementById("exam-questions-container");

  if (startBtn) startBtn.disabled = true;
  if (makeBtn) makeBtn.disabled = true;
  if (unitSel) unitSel.disabled = true;
  if (container) {
    container.classList.remove("exam-locked");
    container.classList.add("exam-unlocked");
  }

  updateTimerDisplay();

  examTimer = setInterval(() => {
    examTimeLeft--;
    updateTimerDisplay();

    if (examTimeLeft <= 0) {
      clearInterval(examTimer);
      examTimer = null;
      handleTimerExpired();
    }
  }, 1000);
}

function updateTimerDisplay() {
  const display = document.getElementById("exam-timer-display");
  if (!display) return;

  const min = Math.floor(examTimeLeft / 60);
  const sec = examTimeLeft % 60;
  display.textContent = `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;

  if (examTimeLeft <= 300) {
    display.style.color = "#d32f2f";
    display.style.fontWeight = "bold";
  }
}

function handleTimerExpired() {
  const display = document.getElementById("exam-timer-display");

  if (display) {
    display.textContent = "00:00";
    display.style.color = "#d32f2f";
  }

  alert("시험 시간이 완료 되었습니다.\n답안지가 자동으로 제출됩니다.");
  submitExam();
}

async function submitExam() {
  if (examSubmitting) return;

  if (examProblems.length === 0) {
    alert("시험지가 없습니다.");
    return;
  }

  if (examTimer) {
    clearInterval(examTimer);
    examTimer = null;
  }

  examSubmitting = true;

  const submitBtn = document.getElementById("exam-submit-btn");
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "채점 중...";
  }

  const answers = examProblems.map((_, idx) => {
    const input = document.getElementById(`exam-answer-${idx + 1}`);
    return input ? (input.value || "") : "";
  });

  const unit = document.getElementById("exam-unit-select")?.value || "";

  try {
    const res = await apiFetch("/api/exam/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ unit, problems: examProblems, answers })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showExamResultError(err.detail || "채점 오류가 발생했습니다.");
      return;
    }

    const result = await res.json();

    examPendingSaveData = {
      unit,
      score: result.score,
      total_questions: result.total,
      wrong_numbers: result.wrong_numbers || [],
      feedbacks: result.feedbacks || {}
    };

    fillExamResultBody(result);
    openExamResultModal();
  } catch (e) {
    console.error("채점 오류", e);
    showExamResultError("서버 연결 오류가 발생했습니다.");
  } finally {
    examSubmitting = false;

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "답안지 제출";
    }
  }
}

function openExamResultModal() {
  const modal = document.getElementById("examResultModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";
}

function fillExamResultBody(result) {
  const body = document.getElementById("examResultBody");
  if (!body) return;

  const correct = result.correct ?? 0;
  const wrongNums = result.wrong_numbers || [];
  const feedbacks = result.feedbacks || {};

  const displayScore = correct * 10;

  let levelText = "";
  if (displayScore <= 50) {
    levelText = "노력해야겠어요!";
  } else if (displayScore <= 70) {
    levelText = "조금만 더 열심히 해보도록 해요!";
  } else if (displayScore <= 90) {
    levelText = "정말 훌륭하네요!";
  } else {
    levelText = "당신은 수학천재!";
  }

  let feedbackHtml = "";

  if (wrongNums.length === 0) {
    feedbackHtml = `
      <div class="solution-box" style="background:#f4fff6; border-color:#b9e3c1;">
        모든 문제를 맞혔어! 정말 잘했어!
      </div>
    `;
  } else {
    wrongNums.forEach(num => {
      const fb = feedbacks[String(num)] || "풀이 설명이 없습니다.";

      // ⭐ 1. 텍스트를 수식용으로 1차 가공 (분수 등을 LaTeX로 변환)
      let processedFb = fb;
      if (typeof prepareMathDisplayText === "function") {
        processedFb = prepareMathDisplayText(fb);
      }

      feedbackHtml += `
        <div style="margin-bottom:18px; padding-bottom:14px; border-bottom:1px solid #eee;">
          <p style="font-weight:bold; color:#d32f2f; font-size:17px; margin:0 0 6px 0;">
            ${num}번 풀이
          </p>
          <div class="solution-box">${escapeHtml(processedFb)}</div>
        </div>
      `;
    });
  }

  body.innerHTML = `
    <p style="font-size:24px; font-weight:bold; margin-bottom:10px;">
      시험 점수 : ${displayScore}점 / 100점
    </p>
    <p style="font-size:18px; margin-bottom:20px;">
      평가 : ${levelText}
    </p>
    <h3 style="margin:0 0 12px 0; font-size:20px;">틀린 문제 풀이</h3>
    ${feedbackHtml}
  `;

  // ⭐ 2. HTML이 화면에 추가된 직후 수식 렌더링 함수 실행!
  if (typeof renderMath === "function") {
    setTimeout(() => {
      try {
        renderMath("examResultBody"); // 모달 영역 내의 수식을 예쁘게 그림
      } catch (e) {
        console.error("수식 렌더링 실패:", e);
      }
    }, 100);
  }

  examTtsText = `시험 점수는 ${displayScore}점입니다. ${levelText}`;
  examModalClosable = true;

  const confirmBtn = document.getElementById("examResultConfirmBtn");

  if (confirmBtn) {
    confirmBtn.textContent = "확인";
    confirmBtn.style.display = "inline-block";
    confirmBtn.disabled = false;
  }

}

function showExamResultError(message) {
  const body = document.getElementById("examResultBody");
  if (!body) return;

  body.innerHTML = `
    <p style="color:#c00; padding:20px; font-size:16px;">
      ${message}
    </p>
  `;

  examModalClosable = true;

  const confirmBtn = document.getElementById("examResultConfirmBtn");

  if (confirmBtn) {
    confirmBtn.textContent = "확인";
    confirmBtn.style.display = "inline-block";
    confirmBtn.disabled = false;
  }

  openExamResultModal();
}

function closeExamResultModal() {
  if (!examModalClosable) return;

  const modal = document.getElementById("examResultModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }

  // ⭐ 이 줄이 범인일 확률이 높습니다. 일단 주석 처리합니다.
  // resetExamState(); 

  // 대신, 시험 섹션의 메인 상태로 부드럽게 복귀시킵니다.
  goPage("exam"); 
}

async function saveExamResultAfterConfirm(data) {
  try {
    await apiFetch("/api/exam/save-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
  } catch (e) {
    console.error("시험 결과 저장 실패", e);
  }
}


function bindExamModalEvents() {
  const confirmBtn = document.getElementById("examResultConfirmBtn");

  if (confirmBtn) {
    // ⭐ [수정] 확인 버튼 클릭 시 초기 화면으로 복구하는 로직
    confirmBtn.onclick = async function(e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }

      console.log("✅ 시험 결과 확인 - 초기 화면으로 복귀합니다.");

      // 1. 모달창 즉시 닫기
      const modal = document.getElementById("examResultModal");
      if (modal) {
        modal.classList.add("hidden");
        modal.style.display = "none";
      }

      // 2. 시험 데이터 저장 (비동기)
      if (examPendingSaveData) {
        saveExamResultAfterConfirm(examPendingSaveData).catch(err => console.error(err));
      }

      // 3. ⭐ 핵심: 시험 섹션의 모든 상태를 초기화하고 첫 화면으로 되돌림
      // resetExamState() 함수가 위에서 정의한 대로 모든 UI 요소를 숨기고 버튼을 복구합니다.
      resetExamState(); 

      // 4. 만약 별도의 페이지 이동 함수가 있다면 호출 (없어도 resetExamState가 처리함)
      if (typeof goPage === "function") {
        goPage("exam"); 
      }

      return false; 
    };
  }
}