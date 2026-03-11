let currentAnswer = "";
let currentQuestionText = "";

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
    if (typeof renderMath === "function") {
      renderMath(targetId);
    } else {
      console.warn("renderMath 함수가 정의되지 않았습니다. 수식 렌더링을 건너뜁니다.");
    }
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
function resetModal() {
  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");
  const solEl = document.getElementById("solutionText");
  const solBox = document.querySelector("#resultModal .solution-box");
  const ttsBtn = document.getElementById("ttsBtn");
  const oldBtn = document.getElementById("resultActionBtn");

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
  if (ttsBtn) ttsBtn.style.display = "none";

  if (oldBtn) {
    const newBtn = oldBtn.cloneNode(true);
    newBtn.innerText = "다음";
    newBtn.style.display = "inline-block";
    oldBtn.parentNode.replaceChild(newBtn, oldBtn);
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
  if (solBox) solBox.style.display = "block";

  if (solEl) {
    solEl.style.display = "block";
    solEl.innerText = prepareMathDisplayText(content);
    renderMath("solutionText");
  }

  if (ttsBtn) ttsBtn.style.display = showTts ? "inline-block" : "none";

  setResultAction(onNext, buttonText);
  openResultModal();
}

function showInputModal(title, placeholder, buttonText, onSubmit) {
  resetModal();

  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");
  const actionBtn = document.getElementById("resultActionBtn");

  if (titleEl) titleEl.innerText = title;
  if (actionBtn) actionBtn.style.display = "none";

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
  const solBox = document.querySelector("#resultModal .solution-box");
  const solEl = document.getElementById("solutionText");
  const ttsBtn = document.getElementById("ttsBtn");
  const actionBtn = document.getElementById("resultActionBtn");

  if (titleEl) titleEl.innerText = `📝 퀴즈 (${prob["단원"] ?? "-"})`;
  if (solBox) solBox.style.display = "none";

  if (solEl) {
    solEl.innerText = "";
    solEl.style.display = "none";
  }

  if (ttsBtn) ttsBtn.style.display = "none";
  if (actionBtn) actionBtn.style.display = "none";

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
      renderMath("modal-problem-text");
    }
  }

  openResultModal();

  const submitBtn = document.getElementById("modal-submit-btn");
  if (submitBtn) {
    submitBtn.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      submitBtn.disabled = true;
      submitBtn.blur();

      const answer = document.getElementById("modal-answer-input")?.value || "";
      await submitCurrentAnswer(answer);
    };
  }
}

//───────────────────────────────────────
// 최종 피드백 모달
//───────────────────────────────────────
function showFinalFeedbackModal(feedback, isCorrect) {
  const feedbackText = document.getElementById("feedbackText");
  const retryBtn = document.getElementById("feedbackRetryBtn");
  const nextUnitBtn = document.getElementById("feedbackNextUnitBtn");
  const closeBtn = document.getElementById("closeFeedbackModalBtn");

  if (feedbackText) {
    feedbackText.innerText = prepareMathDisplayText(feedback);
    renderMath("feedbackText");
  }

  if (retryBtn) {
    retryBtn.style.display = "inline-block";
    retryBtn.disabled = true;
    retryBtn.onclick = async () => {
      closeFeedbackModal();
      await loadProblem();
    };
  }

  if (nextUnitBtn) {
    nextUnitBtn.style.display = "inline-block";
    nextUnitBtn.disabled = true;
    nextUnitBtn.onclick = () => {
      closeFeedbackModal();
      localStorage.setItem("step", "select_unit");
      goPage("today");
    };
  }

  if (closeBtn) {
    closeBtn.disabled = true;
  }

  openFeedbackModal();

  setTimeout(() => {
    if (retryBtn && retryBtn.style.display !== "none") retryBtn.disabled = false;
    if (nextUnitBtn && nextUnitBtn.style.display !== "none") nextUnitBtn.disabled = false;
    if (closeBtn) closeBtn.disabled = false;
  }, 500);
}

//───────────────────────────────────────
// 오늘 학습 화면
//───────────────────────────────────────
function renderToday() {
  const selectUnit = document.getElementById("step-select_unit");
  const explain = document.getElementById("step-explain");
  const studentExplain = document.getElementById("step-student_explain");
  const explainFeedback = document.getElementById("step-explain_feedback");
  const reExplain = document.getElementById("step-re_explain");
  const askQuestion = document.getElementById("step-ask_question");
  const evaluation = document.getElementById("step-evaluation");

  if (selectUnit) selectUnit.style.display = "block";
  if (explain) explain.style.display = "none";
  if (studentExplain) studentExplain.style.display = "none";
  if (explainFeedback) explainFeedback.style.display = "none";
  if (reExplain) reExplain.style.display = "none";
  if (askQuestion) askQuestion.style.display = "none";
  if (evaluation) evaluation.style.display = "none";

  const btnStart = document.getElementById("btn-start");
  if (btnStart && !btnStart.dataset.bound) {
    btnStart.dataset.bound = "1";
    btnStart.addEventListener("click", async () => {
      // 추가: 로딩 오버레이 표시
      document.getElementById("loading-overlay").style.display = "flex";

      // 추가: 로딩 화면이 잠깐이라도 보이도록 0.1초 대기
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const unit = document.getElementById("unit-select")?.value;

      if (!unit) {
        // 추가: 단원 미선택 시 로딩 오버레이 숨김
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
        const explanation = data.explanation || "설명이 없습니다.";

        // 추가: 설명 데이터 받은 뒤 로딩 오버레이 숨김
        document.getElementById("loading-overlay").style.display = "none";

        localStorage.setItem("current_explanation", explanation);
        logMathText("설명", explanation);

        showSolutionModal(
          `📖 ${unit} 개념 익히기`,
          explanation,
          "내용 이해 완료! 내가 설명해보기 🗣️",
          () => {
            showStudentExplainModal(unit);
          },
          true
        );
      } catch {
        // 추가: 오류 발생 시에도 로딩 오버레이 숨김
        document.getElementById("loading-overlay").style.display = "none";

        showSolutionModal(
          "오류",
          "설명을 불러오는 데 실패했어요.",
          "확인",
          () => {},
          false
        );
      }
    });
  }
}

function showStudentExplainModal(unit) {
  showInputModal(
    `🗣️ ${unit} 직접 설명하기`,
    "어떻게 이해했는지 적어줘",
    "설명 완료! ✨",
    async (studentText) => {
      if (!studentText.trim()) {
        alert("설명을 적어줘");
        return;
      }

      try {
        const res = await apiFetch("/api/explain/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            concept: unit,
            student_explanation: studentText,
          }),
        });

        const data = await res.json();
        const feedback = data.feedback || "평가 결과가 없습니다.";
        logMathText("이해도 피드백", feedback);

        if (data.is_passed) {
          showSolutionModal(
            "👨‍🏫 이해도 검토 결과",
            feedback,
            "이제 문제 풀기 📝",
            async () => {
              await loadProblem();
            },
            false
          );
        } else {
          // ⭐ 실패 시: 더 쉬운 보충 설명 호출 로직 (수정된 부분)
          showSolutionModal(
            "👨‍🏫 이해도 검토 결과",
            feedback,
            "더 쉬운 보충 설명 듣기 ➡️",
            async () => {
              // 1. 로딩 모달 띄우기
              showSolutionModal(
                "📖 보충 학습 (더 쉬운 설명)",
                "루미 선생님이 더 쉬운 설명을 생각하고 있어요... ⏳\n잠시만 기다려주세요!",
                "기다리는 중...",
                () => {},
                false
              );

              try {
                // 2. 새로운 보충 설명 API 호출
                const res = await apiFetch("/api/reexplain", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ unit_name: unit }),
                });

                const re_data = await res.json();
                const re_explanation = re_data.explanation || "설명이 없습니다.";
                logMathText("보충 설명", re_explanation);

                // 3. 로딩이 끝나면 새로운 설명으로 업데이트
                showSolutionModal(
                  "📖 보충 학습",
                  re_explanation,
                  "이제 정말 준비 완료! 문제 풀기 📝",
                  async () => {
                    await loadProblem();
                  },
                  true
                );
              } catch (e) {
                console.error("보충 설명 로드 실패:", e);
                alert("보충 설명을 불러오는 데 실패했습니다.");
              }
            },
            false
          );
        }
      } catch {
        showSolutionModal(
          "오류",
          "평가를 불러오는 데 실패했어요.",
          "확인",
          () => {},
          false
        );
      }
    }
  );
}

//───────────────────────────────────────
// 단원 목록 로드
//───────────────────────────────────────
async function loadUnits() {
  const select = document.getElementById("unit-select");
  if (!select) return;

  try {
    const res = await apiFetch("/api/units");
    const data = await res.json();

    select.innerHTML = `<option value="">단원 선택</option>`;

    (data.units || []).forEach((unit) => {
      const opt = document.createElement("option");
      opt.value = unit;
      opt.text = unit;
      select.add(opt);
    });
  } catch {
    console.error("단원 목록 로드 실패");
  }
}

//───────────────────────────────────────
// 문제 로드
//───────────────────────────────────────
async function loadProblem() {
  const unit = localStorage.getItem("selected_unit");

  try {
    const res = await apiFetch(`/api/problem?unit=${encodeURIComponent(unit)}`);
    const data = await res.json();
    const prob = data.problem;

    localStorage.setItem("current_problem", JSON.stringify(prob));
    currentAnswer = prob.answer || prob["정답"] || prob["답"] || prob["풀이및정답"] || "";
    currentQuestionText = prob["문제"] || "";

    logMathText("문제", currentQuestionText);
    logMathText("정답", currentAnswer);

    showQuestionModal(prob, data.image_b64 || "");
  } catch {
    showSolutionModal(
      "오류",
      "문제를 불러오는 데 실패했어요.",
      "확인",
      () => {},
      false
    );
  }
}

//───────────────────────────────────────
// 답 제출 → 최종 피드백 모달
//───────────────────────────────────────
async function submitCurrentAnswer(answerText = null) {
  const studentAnswer = answerText ?? "";
  const problem = JSON.parse(localStorage.getItem("current_problem") || "{}");

  if (!studentAnswer.trim()) {
    alert("정답과 풀이를 적어줘");
    return;
  }

  try {
    const res = await apiFetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem,
        student_answer: studentAnswer,
      }),
    });

    if (!res.ok) {
      console.error("evaluate 실패:", res.status, res.statusText);
      alert("채점 요청이 실패했어요.");
      return;
    }

    const data = await res.json();
    console.log("evaluate 응답:", data);

    const feedback = data.feedback || "피드백이 없습니다.";

    closeResultModal();
    showFinalFeedbackModal(feedback, data.is_correct);

    // history 저장은 일단 나중에 확인
    // await apiFetch("/api/history", {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify({
    //     problem_id: String(problem.ID || ""),
    //     unit: problem["단원"] || "",
    //     is_correct: data.is_correct,
    //   }),
    // });
  } catch (err) {
    console.error("제출 중 오류:", err);
    alert("채점 중 오류가 발생했어요.");
  }
}