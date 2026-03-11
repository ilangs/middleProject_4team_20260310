let currentAnswer = "";
let currentQuestionText = "";

// ⭐ [모달 전용 TTS 상태 관리 변수]
let currentModalAudio = null;
let currentModalTtsState = "idle"; // 상태: idle, loading, playing, paused

// ⭐ [모달 전용 TTS 토글 함수]
async function toggleModalTTS(text, btnEl) {
  // 1. 전역에 다른 TTS 중지 함수가 있다면 호출
  if (typeof stopOtherTTS === "function") stopOtherTTS();

  // 2. 재생 중 -> 일시정지
  if (currentModalTtsState === "playing") {
    if (currentModalAudio) currentModalAudio.pause();
    currentModalTtsState = "paused";
    btnEl.innerHTML = "🔊 음성 듣기";
    return;
  }

  // 3. 일시정지 -> 이어서 재생
  if (currentModalTtsState === "paused") {
    if (currentModalAudio) currentModalAudio.play();
    currentModalTtsState = "playing";
    btnEl.innerHTML = "⏸️ 음성 중지";
    return;
  }

  if (currentModalTtsState === "loading") return;

  currentModalTtsState = "loading";
  btnEl.innerHTML = "⏳ 생성 중...";
  btnEl.disabled = true;

  try {
    const res = await apiFetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    });

    if (!res.ok) throw new Error("TTS API 오류");
    const data = await res.json();
    const audioData = typeof data === "string" ? data : data.audio_b64;

    if (audioData) {
      currentModalAudio = new Audio(`data:audio/mp3;base64,${audioData}`);
      
      currentModalAudio.onended = () => {
        currentModalTtsState = "idle";
        btnEl.innerHTML = "🔊 음성 듣기";
        currentModalAudio = null;
      };

      currentModalAudio.play();
      currentModalTtsState = "playing";
      btnEl.innerHTML = "⏸️ 음성 중지";
    } else {
      throw new Error("오디오 데이터가 비어있습니다.");
    }
  } catch (err) {
    console.error("TTS 재생 실패:", err);
    alert("음성을 불러오지 못했습니다.");
    currentModalTtsState = "idle";
    btnEl.innerHTML = "🔊 음성 듣기";
  } finally {
    btnEl.disabled = false;
  }
}

//───────────────────────────────────────
// 수식/문자열 표시 유틸
//───────────────────────────────────────
function prepareMathDisplayText(text) {
  const raw = String(text || "");
  if (/[\\$]/.test(raw)) return raw;
  return raw.replace(/(\d+)\s*\/\s*(\d+)/g, "\\(\\frac{$1}{$2}\\)");
}

function formatMathForConsole(text) {
  return String(text || "")
    .replace(/\\\(/g, "")
    .replace(/\\\)/g, "")
    .replace(/\$/g, "")
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1/$2")
    .replace(/\\times/g, "×")
    .replace(/\\div/g, "÷")
    .replace(/\\cdot/g, "·")
    .replace(/\\left/g, "")
    .replace(/\\right/g, "")
    .replace(/\\mathrm\{([^}]+)\}/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function setMathText(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerText = prepareMathDisplayText(text);
  try {
    if (typeof renderMath === "function") renderMath(targetId);
  } catch (e) {
    console.error("수식 렌더링 중 오류 발생:", e);
  }
}

function logMathText(label, text) {
  console.log(`${label}:`, formatMathForConsole(text));
}

//───────────────────────────────────────
// 문제 입력 모달 공통
//───────────────────────────────────────

// ⭐ [중요: 모달이 닫힐 때 오디오를 완전히 끄는 함수]
function stopAllModalAudio() {
  if (currentModalAudio) {
    currentModalAudio.pause();
    currentModalAudio.currentTime = 0;
    currentModalAudio = null;
  }
  currentModalTtsState = "idle";
}

function resetModal() {
  // 모달 데이터 초기화 시 오디오 정지 호출
  stopAllModalAudio();

  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");
  const solEl = document.getElementById("solutionText");
  const solBox = document.querySelector("#resultModal .solution-box");
  const ttsBtn = document.getElementById("ttsBtn");
  const actionBtn = document.getElementById("resultActionBtn");

  if (titleEl) titleEl.innerText = "";
  if (msgEl) {
    msgEl.innerHTML = "";
    msgEl.style.display = "block";
  }
  if (solEl) {
    solEl.innerText = "";
    solEl.style.display = "none";
  }
  if (solBox) solBox.style.display = "none";
  if (ttsBtn) {
    ttsBtn.style.display = "none";
    ttsBtn.innerHTML = "🔊 음성 듣기";
  }

  if (actionBtn) {
    actionBtn.style.display = "none"; 
    actionBtn.onclick = null; // 이벤트 초기화
    actionBtn.innerText = "다음";
  }
}

function setResultAction(handler, label) {
  const oldBtn = document.getElementById("resultActionBtn");
  if (!oldBtn) return;

  const newBtn = oldBtn.cloneNode(true);
  newBtn.innerText = label || "다음";
  newBtn.style.display = "inline-block";
  newBtn.onclick = () => {
    closeResultModal();
    if (handler) handler();
  };

  oldBtn.parentNode.replaceChild(newBtn, oldBtn);
}

function showSolutionModal(title, content, buttonText, onNext, showTts = false) {
  resetModal();

  const titleEl = document.getElementById("resultTitle");
  const solBox = document.querySelector("#resultModal .solution-box");
  const solEl = document.getElementById("solutionText");
  const ttsBtn = document.getElementById("ttsBtn");

  if (titleEl) titleEl.innerText = title;

  if (solBox) {
    solBox.style.display = "block";

    // ⭐ [핵심 수정] '풀이 설명' 제목 부분에 캐릭터 이미지를 함께 넣도록 HTML 구조 변경
    // assets/images/main_rumi.png 경로를 사용합니다.
    solBox.innerHTML = `
      <div style="display: flex; align-items: center; 
              margin-top: -40px;    /* ⭐ 1. 이 값을 더 작은 마이너스(예: -20px)로 할수록 위로 붙습니다 */
              margin-bottom: 15px; 
              border-bottom: 2px solid #e0e0e0; 
              padding-bottom: 10px;">
    <img src="assets/images/main_rumi.png" alt="루미 선생님" 
         style="width: 160px; height: auto; 
                margin-top: 0;       /* ⭐ 2. 이미지 자체의 상단 여백도 0으로 확인 */
                margin-right: 15px; 
    <h3 style="margin: 0; font-size: 2rem; color: #333;">💡 루미 선생님의 풀이 설명</h3>
  </div>
  <div id="solutionText" style="font-size: 1.1rem; line-height: 1.6; color: #444; white-space: pre-wrap;"></div>
    `;
  }

  // ⭐ HTML 구조가 바뀌었으므로, 새로운 solutionText 요소를 다시 잡아야 합니다.
  const newSolEl = document.getElementById("solutionText");
  if (newSolEl) {
    newSolEl.style.display = "block";
    // 수식 렌더링을 위해 prepareMathDisplayText 함수 사용
    newSolEl.innerText = prepareMathDisplayText(content);
    
    // ⭐ MathJax 수식 렌더링 함수 호출 (화면에 HTML이 그려진 후 실행)
    if (typeof renderMath === "function") {
      // 잠깐의 시간을 두어 HTML이 완전히 그려진 후 렌더링하도록 유도
      setTimeout(() => renderMath("solutionText"), 50); 
    }
  }  

  // if (solEl) {
  //   solEl.style.display = "block";
  //   solEl.innerText = prepareMathDisplayText(content);
  //   if (typeof renderMath === "function") renderMath("solutionText");
  // }

  if (ttsBtn) {
    if (showTts) {
      ttsBtn.style.display = "inline-block";
      ttsBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleModalTTS(content, ttsBtn);
      };
    } else {
      ttsBtn.style.display = "none";
    }
  }

  setResultAction(onNext, buttonText);
  openResultModal();
}

function showInputModal(title, placeholder, buttonText, onSubmit) {
  resetModal();
  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");
  if (titleEl) titleEl.innerText = title;
  if (msgEl) {
    msgEl.innerHTML = `
      <textarea id="modal-student-text" rows="6" placeholder="${placeholder}" style="width:100%;padding:10px;box-sizing:border-box;"></textarea>
      <button id="modal-student-submit" type="button" style="margin-top:12px;">${buttonText}</button>
    `;
  }
  openResultModal();

  const submitBtn = document.getElementById("modal-student-submit");
  if (submitBtn) {
    submitBtn.onclick = (e) => {
      e.preventDefault();
      const value = document.getElementById("modal-student-text")?.value || "";
      onSubmit(value);
    };
  }
}

function showQuestionModal(prob, imageB64 = "") {
  resetModal();
  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");

  if (titleEl) titleEl.innerText = `📝 퀴즈 (${prob["단원"] ?? "-"})`;
  if (msgEl) {
    msgEl.innerHTML = `
      <div id="modal-problem-text"></div>
      ${imageB64 ? `<img src="data:image/png;base64,${imageB64}" style="max-width:100%;margin-top:12px;">` : ""}
      <textarea id="modal-answer-input" rows="5" placeholder="정답과 풀이를 적어주세요." style="width:100%;padding:10px;margin-top:12px;box-sizing:border-box;"></textarea>
      <button id="modal-submit-btn" type="button" style="margin-top:12px;">제출하기</button>
    `;
    const p = document.getElementById("modal-problem-text");
    if (p) {
      p.innerText = prepareMathDisplayText(prob["문제"] ?? "문제를 불러올 수 없어요.");
      if (typeof renderMath === "function") renderMath("modal-problem-text");
    }
  }
  openResultModal();

  const submitBtn = document.getElementById("modal-submit-btn");
  if (submitBtn) {
    submitBtn.onclick = async (e) => {
      e.preventDefault();
      const answer = document.getElementById("modal-answer-input")?.value || "";
      await submitCurrentAnswer(answer);
    };
  }
}



//───────────────────────────────────────
// 오늘 학습 화면 초기화 및 X 버튼 이벤트
//───────────────────────────────────────
function renderToday() {
  const selectUnit = document.getElementById("step-select_unit");
  if (selectUnit) selectUnit.style.display = "block";

  // ⭐ [X 버튼 이벤트 강제 바인딩]
  // 모달 외부에서 정의된 X 버튼을 찾아서 클릭 시 오디오를 정지시킵니다.
  const closeBtn = document.querySelector("#resultModal .close-btn") || 
                   document.querySelector("#resultModal .modal-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      stopAllModalAudio(); // X 버튼 누르면 음성 즉각 정지
    });
  }

  const btnStart = document.getElementById("btn-start");
  if (btnStart && !btnStart.dataset.bound) {
    btnStart.dataset.bound = "1";
    btnStart.addEventListener("click", async () => {
      document.getElementById("loading-overlay").style.display = "flex";
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const unit = document.getElementById("unit-select")?.value;
      if (!unit) {
        document.getElementById("loading-overlay").style.display = "none";
        alert("단원을 선택하세요");
        return;
      }

      localStorage.setItem("selected_unit", unit);

      try {
        const res = await apiFetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ unit_name: unit }),
        });
        const data = await res.json();
        document.getElementById("loading-overlay").style.display = "none";

        const explanation = data.explanation || "설명이 없습니다.";
        showSolutionModal(`📖 ${unit} 개념 익히기`, explanation, "내용 이해 완료! 내가 설명해보기 🗣️", () => {
          showStudentExplainModal(unit);
        }, true);
      } catch {
        document.getElementById("loading-overlay").style.display = "none";
        showSolutionModal("오류", "설명을 불러오는 데 실패했어요.", "확인", () => {}, false);
      }
    });
  }
}

function showStudentExplainModal(unit) {
  showInputModal(`🗣️ ${unit} 직접 설명하기`, "어떻게 이해했는지 적어줘", "설명 완료! ✨", async (studentText) => {
    if (!studentText.trim()) return alert("설명을 적어줘");
    try {
      const res = await apiFetch("/api/explain/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concept: unit, student_explanation: studentText }),
      });
      const data = await res.json();
      const feedback = data.feedback || "평가 결과가 없습니다.";

      if (data.is_passed) {
        showSolutionModal("👨‍🏫 이해도 검토 결과", feedback, "이제 문제 풀기 📝", async () => { await loadProblem(); }, false);
      } else {
        showSolutionModal("👨‍🏫 이해도 검토 결과", feedback, "더 쉬운 보충 설명 듣기 ➡️", async () => {
          showSolutionModal("📖 보충 학습 (더 쉬운 설명)", "루미 선생님이 보충 설명을 준비 중... ⏳", "기다리는 중...", () => {}, false);
          try {
            const res2 = await apiFetch("/api/reexplain", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ unit_name: unit }),
            });
            const re_data = await res2.json();
            showSolutionModal("📖 보충 학습", re_data.explanation || "설명이 없습니다.", "이제 문제 풀기 📝", async () => { await loadProblem(); }, true);
          } catch (e) { alert("보충 설명 로드 실패"); }
        }, false);
      }
    } catch { alert("평가 실패"); }
  });
}

// (이하 loadUnits, loadProblem, submitCurrentAnswer 등 기존 로직 동일)
async function loadUnits() {
  const select = document.getElementById("unit-select");
  if (!select) return;
  try {
    const res = await apiFetch("/api/units");
    const data = await res.json();
    select.innerHTML = `<option value="">단원 선택</option>`;
    (data.units || []).forEach(u => {
      const opt = document.createElement("option");
      opt.value = u; opt.text = u; select.add(opt);
    });
  } catch (e) { console.error("단원 목록 로드 실패"); }
}

async function loadProblem() {
  const unit = localStorage.getItem("selected_unit");
  try {
    const res = await apiFetch(`/api/problem?unit=${encodeURIComponent(unit)}`);
    const data = await res.json();
    const prob = data.problem;
    if (!prob) throw new Error("문제가 없습니다.");

    localStorage.setItem("current_problem", JSON.stringify(prob));

    currentAnswer = prob.answer || prob["정답"] || prob["답"] || "";
    currentQuestionText = prob["문제"] || "";

    showQuestionModal(prob, data.image_b64 || "");
  } catch (e) {
    console.error("문제 로드 중 상세 오류:", e);
    alert("문제를 불러오지 못했습니다.");
  }
}

async function submitCurrentAnswer(answerText = null) {
  const studentAnswer = answerText ?? "";
  
  // 1. 저장된 문제 데이터 가져오기
  const savedData = localStorage.getItem("current_problem");
  if (!savedData) {
    alert("문제 데이터가 사라졌습니다. 다시 시도해 주세요.");
    return;
  }
  
  const problemObj = JSON.parse(savedData);

  try {
    // 2. 서버로 채점 요청
    const res = await apiFetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem: problemObj,        // 백엔드가 기대하는 키 'problem'
        student_answer: studentAnswer
      }),
    });

    // 3. 응답 확인
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      console.error("서버 채점 에러:", data); // 위에서 이미 읽은 data 사용
      throw new Error(data.detail || "채점 실패");
    }
    
    closeResultModal();
    showFinalFeedbackModal(data.feedback, data.is_correct);

  } catch (err) {
    console.error("제출 프로세스 중 오류:", err);
    alert("채점 중 오류가 발생했습니다."+ err.message);
    
    // 오류 시 제출 버튼 다시 활성화
    const submitBtn = document.getElementById("modal-submit-btn");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = "제출하기";
    }
  }
}

// ───────────────────────────────────────
// 최종 피드백 모달 (파일 맨 하단에 추가)
// ───────────────────────────────────────
function showFinalFeedbackModal(feedback, isCorrect) {
  // 에러 방지를 위해 요소가 있는지 하나씩 체크하며 진행합니다.
  const feedbackText = document.getElementById("feedbackText");
  const retryBtn = document.getElementById("feedbackRetryBtn");
  const nextUnitBtn = document.getElementById("feedbackNextUnitBtn");
  const closeBtn = document.getElementById("closeFeedbackModalBtn");

  if (feedbackText) {
    // prepareMathDisplayText 함수가 있는지 확인 후 사용
    const processedText = (typeof prepareMathDisplayText === "function") 
                          ? prepareMathDisplayText(feedback) 
                          : feedback;
    feedbackText.innerText = processedText;
    
    if (typeof renderMath === "function") {
      renderMath("feedbackText");
    }
  }

  if (retryBtn) {
    retryBtn.style.display = "inline-block";
    retryBtn.disabled = true;
    retryBtn.onclick = async (e) => {
      if(e) e.preventDefault();
      if (typeof closeFeedbackModal === "function") closeFeedbackModal();
      if (typeof loadProblem === "function") await loadProblem();
    };
  }

  if (nextUnitBtn) {
    nextUnitBtn.style.display = "inline-block";
    nextUnitBtn.disabled = true;
    nextUnitBtn.onclick = (e) => {
      if(e) e.preventDefault();
      if (typeof closeFeedbackModal === "function") closeFeedbackModal();
      localStorage.setItem("step", "select_unit");
      if (typeof goPage === "function") goPage("today");
    };
  }

  // 모달 열기 함수 호출
  if (typeof openFeedbackModal === "function") {
    openFeedbackModal();
  } else {
    console.error("openFeedbackModal 함수가 정의되지 않았습니다.");
  }

  setTimeout(() => {
    if (retryBtn) retryBtn.disabled = false;
    if (nextUnitBtn) nextUnitBtn.disabled = false;
    if (closeBtn) closeBtn.disabled = false;
  }, 500);
}