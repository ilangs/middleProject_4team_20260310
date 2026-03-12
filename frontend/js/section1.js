/**
 * ============================================================
 * section1.js  -  오늘 학습 (📚 today) 섹션
 * ============================================================
 *
 * [역할]
 *   학생이 단원을 선택하면 AI 튜터 '루미'가 개념을 설명해주고,
 *   학생이 직접 설명한 내용을 AI가 평가한 뒤 문제를 제공합니다.
 *   문제를 풀고 제출하면 AI가 채점 및 피드백을 제공합니다.
 *
 * [사용 페이지] frontend/app.html (id="page-today" 섹션)
 *
 * [학습 단계 흐름]
 *   ① 단원 선택 (loadUnits로 목록 표시)
 *        ↓ [학습 시작] 버튼 클릭
 *   ② AI 개념 설명 표시 (POST /api/explain → showSolutionModal)
 *        ↓ "내용 이해 완료! 내가 설명해보기" 버튼 클릭
 *   ③ 학생 직접 설명 입력 (showStudentExplainModal)
 *        ↓ 설명 제출
 *   ④ AI 이해도 평가 (POST /api/explain/evaluate)
 *        ↓ 통과 시 → 문제 풀기
 *        ↓ 미통과 시 → 보충 설명 (POST /api/reexplain)
 *   ⑤ 문제 출제 (GET /api/problem → showQuestionModal)
 *        ↓ 답안 제출
 *   ⑥ AI 채점 (POST /api/evaluate → showFinalFeedbackModal)
 *        ↓ 다시 풀기 OR 다른 단원 선택
 *
 * [사용되는 외부 함수 - app.js에 정의]
 *   - apiFetch(path, options) : 인증 헤더가 포함된 API 호출
 *   - renderMath(targetId)    : MathJax 수식 렌더링
 *   - openResultModal()       : 문제/풀이 모달 열기
 *   - closeResultModal()      : 문제/풀이 모달 닫기
 *   - openFeedbackModal()     : 최종 피드백 모달 열기
 *   - closeFeedbackModal()    : 최종 피드백 모달 닫기
 *
 * [학습 포인트 - 3주차 AI 에이전트 과정]
 *   - localStorage를 이용한 학습 단계 및 문제 데이터 저장
 *   - 모달 UI 패턴: 재사용 가능한 모달로 다양한 내용 표시
 *   - async/await를 이용한 순차적 API 호출 처리
 * ============================================================
 */

// ─────────────────────────────────────────────────────────────
// 전역 변수
// ─────────────────────────────────────────────────────────────

// 현재 문제의 정답 (채점 시 비교용으로 저장)
let currentAnswer = "";

// 현재 문제 텍스트 (TTS 읽기 등에 활용)
let currentQuestionText = "";

// ⭐ [모달 전용 TTS 상태 관리 변수]
// 모달 내 "음성 듣기" 버튼을 위한 Audio 객체
let currentModalAudio = null;
// TTS 재생 상태: "idle"(대기), "loading"(생성중), "playing"(재생중), "paused"(일시정지)
let currentModalTtsState = "idle";

// ─────────────────────────────────────────────────────────────
// 모달 전용 TTS 제어 함수
// ─────────────────────────────────────────────────────────────

/**
 * toggleModalTTS(text, btnEl)
 * ─────────────────────────────────────
 * [역할] 풀이 설명 모달 내의 "음성 듣기" 버튼 클릭 시 호출됩니다.
 *        TTS(Text-to-Speech) 음성을 재생/일시정지/이어서재생 합니다.
 *
 * [호출 시점] showSolutionModal() 에서 생성된 TTS 버튼의 onclick 이벤트
 *
 * [상태 전환 다이어그램]
 *   idle → [버튼 클릭] → loading → playing → idle (재생 완료)
 *   playing → [버튼 클릭] → paused
 *   paused → [버튼 클릭] → playing
 *
 * [API 호출]
 *   엔드포인트: POST /api/tts
 *   전송 데이터: { text: "읽어줄 텍스트" }
 *   응답 예시:  { audio_b64: "base64인코딩된MP3데이터" }
 *   또는 응답이 문자열 자체가 base64일 수도 있음
 *
 * @param {string} text  - TTS로 읽어줄 텍스트
 * @param {HTMLElement} btnEl - 클릭된 TTS 버튼 요소 (버튼 텍스트 업데이트용)
 */
// ⭐ [모달 전용 TTS 토글 함수]
async function toggleModalTTS(text, btnEl) {
  // 1. 전역에 다른 TTS 중지 함수가 있다면 호출
  // section2.js의 자유학습 TTS가 재생 중이면 먼저 중지
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

  // 생성 중일 때는 버튼 중복 클릭 무시
  if (currentModalTtsState === "loading") return;

  // 아이들 상태일 때 → 음성 생성 시작
  currentModalTtsState = "loading";
  btnEl.innerHTML = "⏳ 생성 중...";
  btnEl.disabled = true;  // 생성 완료 전까지 버튼 비활성화

  try {
    // POST /api/tts: 서버에서 텍스트를 MP3 오디오로 변환
    const res = await apiFetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    });

    if (!res.ok) throw new Error("TTS API 오류");
    const data = await res.json();

    // 응답이 문자열이면 그 자체가 base64, 객체이면 audio_b64 키에서 추출
    const audioData = typeof data === "string" ? data : data.audio_b64;

    if (audioData) {
      // base64 인코딩된 MP3 데이터를 Audio 객체로 생성
      // data URL 형식: "data:audio/mp3;base64,AAAA..."
      currentModalAudio = new Audio(`data:audio/mp3;base64,${audioData}`);

      // 재생이 끝나면 버튼과 상태를 초기화
      currentModalAudio.onended = () => {
        currentModalTtsState = "idle";
        btnEl.innerHTML = "🔊 음성 듣기";
        currentModalAudio = null;
      };

      // 음성 재생 시작
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
    // 성공/실패 관계없이 버튼 다시 활성화
    btnEl.disabled = false;
  }
}

//───────────────────────────────────────
// 수식/문자열 표시 유틸
//───────────────────────────────────────

/**
 * prepareMathDisplayText(text)
 * ─────────────────────────────────────
 * [역할] 텍스트에 LaTeX 수식이 없는 경우, 분수 표기(3/4)를
 *        MathJax가 렌더링할 수 있는 LaTeX 형식(\frac{3}{4})으로 변환합니다.
 *
 * [변환 예시]
 *   "3/4" → "\(\frac{3}{4}\)"
 *   이미 LaTeX 형식(\ 또는 $)이 있으면 변환하지 않음
 *
 * @param {string} text - 원본 텍스트
 * @returns {string} MathJax 렌더링 준비된 텍스트
 */
function prepareMathDisplayText(text) {
  const raw = String(text || "");
  // 이미 LaTeX 기호(\ 또는 $)가 있으면 그대로 반환
  if (/[\\$]/.test(raw)) return raw;
  // "숫자/숫자" 패턴을 \(\frac{분자}{분모}\) 형식으로 변환
  return raw.replace(/(\d+)\s*\/\s*(\d+)/g, "\\(\\frac{$1}{$2}\\)");
}

/**
 * formatMathForConsole(text)
 * ─────────────────────────────────────
 * [역할] LaTeX 수식이 포함된 텍스트를 사람이 읽기 쉬운 형식으로 변환합니다.
 *        주로 console.log 디버깅용입니다.
 *
 * [변환 예시]
 *   "\(\frac{1}{2}\)" → "1/2"
 *   "\times" → "×"
 *   "\div" → "÷"
 *
 * @param {string} text - LaTeX가 포함된 텍스트
 * @returns {string} LaTeX 제거 후 일반 텍스트
 */
function formatMathForConsole(text) {
  return String(text || "")
    .replace(/\\\(/g, "")         // \( 제거 (LaTeX 인라인 수식 시작 태그)
    .replace(/\\\)/g, "")         // \) 제거 (LaTeX 인라인 수식 끝 태그)
    .replace(/\$/g, "")           // $ 제거 (LaTeX 수식 구분자)
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1/$2")  // \frac{a}{b} → a/b
    .replace(/\\times/g, "×")    // 곱셈 기호
    .replace(/\\div/g, "÷")      // 나눗셈 기호
    .replace(/\\cdot/g, "·")     // 가운뎃점
    .replace(/\\left/g, "")      // \left 괄호 제어 명령 제거
    .replace(/\\right/g, "")     // \right 괄호 제어 명령 제거
    .replace(/\\mathrm\{([^}]+)\}/g, "$1")  // \mathrm{text} → text
    .replace(/\s+/g, " ")        // 연속 공백을 단일 공백으로
    .trim();                      // 앞뒤 공백 제거
}

/**
 * setMathText(targetId, text)
 * ─────────────────────────────────────
 * [역할] 특정 DOM 요소에 수식 텍스트를 설정하고 MathJax로 렌더링합니다.
 *
 * @param {string} targetId - 텍스트를 설정할 요소의 id
 * @param {string} text     - 표시할 텍스트 (수식 포함 가능)
 */
function setMathText(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) return;
  // 수식 표시 텍스트로 변환 후 요소에 설정
  el.innerText = prepareMathDisplayText(text);
  try {
    // MathJax로 해당 요소의 수식을 렌더링
    if (typeof renderMath === "function") renderMath(targetId);
  } catch (e) {
    console.error("수식 렌더링 중 오류 발생:", e);
  }
}

/**
 * logMathText(label, text)
 * ─────────────────────────────────────
 * [역할] LaTeX 수식이 포함된 텍스트를 읽기 쉬운 형식으로 콘솔에 출력합니다.
 *        디버깅용 함수입니다.
 *
 * @param {string} label - 콘솔 출력 앞에 붙을 레이블 (예: "문제")
 * @param {string} text  - LaTeX가 포함된 수식 텍스트
 */
function logMathText(label, text) {
  console.log(`${label}:`, formatMathForConsole(text));
}

//───────────────────────────────────────
// 문제 입력 모달 공통
//───────────────────────────────────────

/**
 * stopAllModalAudio()
 * ─────────────────────────────────────
 * [역할] 모달 내에서 재생 중인 TTS 음성을 완전히 정지하고 초기화합니다.
 *
 * [호출 시점]
 *   - closeResultModal() : 모달 X 버튼 클릭 시
 *   - resetModal()       : 모달 내용 초기화 시
 *   - renderToday()      : 오늘 학습 화면 초기화 시
 *
 * [주의] Audio 객체를 null로 설정해 메모리를 해제합니다.
 */
// ⭐ [중요: 모달이 닫힐 때 오디오를 완전히 끄는 함수]
function stopAllModalAudio() {
  if (currentModalAudio) {
    currentModalAudio.pause();       // 재생 중지
    currentModalAudio.currentTime = 0; // 처음으로 되감기
    currentModalAudio = null;         // 참조 해제 (가비지 컬렉션 대상)
  }
  currentModalTtsState = "idle";    // 상태를 대기로 리셋
}

/**
 * resetModal()
 * ─────────────────────────────────────
 * [역할] 모달의 모든 내용을 초기 상태로 리셋합니다.
 *        새로운 내용을 표시하기 전에 항상 호출됩니다.
 *
 * [초기화 항목]
 *   - 재생 중인 TTS 음성 정지
 *   - 제목(resultTitle) 텍스트 비우기
 *   - 메시지(resultMessage) HTML 비우기
 *   - 풀이 설명(solutionText) 숨기기
 *   - TTS 버튼 숨기기
 *   - 다음 버튼(resultActionBtn) 숨기기 및 이벤트 초기화
 */
function resetModal() {
  // 모달 데이터 초기화 시 오디오 정지 호출
  stopAllModalAudio();

  // 각 모달 내 DOM 요소 가져오기
  const titleEl = document.getElementById("resultTitle");     // 모달 제목
  const msgEl = document.getElementById("resultMessage");     // 메시지 영역
  const solEl = document.getElementById("solutionText");      // 풀이 설명 텍스트
  const solBox = document.querySelector("#resultModal .solution-box"); // 풀이 박스
  const ttsBtn = document.getElementById("ttsBtn");           // 음성 듣기 버튼
  const actionBtn = document.getElementById("resultActionBtn"); // 다음/확인 버튼

  // 각 요소 초기화
  if (titleEl) titleEl.innerText = "";
  if (msgEl) {
    msgEl.innerHTML = "";
    msgEl.style.display = "block";
  }
  if (solEl) {
    solEl.innerText = "";
    solEl.style.display = "none";  // 풀이 텍스트 영역 숨김
  }
  if (solBox) solBox.style.display = "none";  // 풀이 박스 숨김
  if (ttsBtn) {
    ttsBtn.style.display = "none";            // TTS 버튼 숨김
    ttsBtn.innerHTML = "🔊 음성 듣기";        // 버튼 텍스트 초기화
  }

  if (actionBtn) {
    actionBtn.style.display = "none";  // 다음 버튼 숨김
    actionBtn.onclick = null;          // 이벤트 초기화 (이전 핸들러 제거)
    actionBtn.innerText = "다음";
  }
}

/**
 * setResultAction(handler, label)
 * ─────────────────────────────────────
 * [역할] 모달 하단의 "다음" 버튼을 설정합니다.
 *        버튼 클릭 시 모달을 닫고, 전달된 handler 함수를 실행합니다.
 *
 * [cloneNode 패턴 사용 이유]
 *   기존 버튼의 onclick을 직접 교체하면 이전에 등록된 이벤트 리스너가
 *   남아있을 수 있습니다. cloneNode(true)로 버튼을 복제하면
 *   기존 이벤트가 모두 제거된 깨끗한 버튼이 됩니다.
 *
 * @param {Function} handler - 버튼 클릭 후 실행할 함수 (다음 단계 처리)
 * @param {string}   label   - 버튼에 표시할 텍스트 (예: "이제 문제 풀기 📝")
 */
function setResultAction(handler, label) {
  const oldBtn = document.getElementById("resultActionBtn");
  if (!oldBtn) return;

  // 기존 버튼을 복제해 이전 이벤트 리스너를 모두 제거
  const newBtn = oldBtn.cloneNode(true);
  newBtn.innerText = label || "다음";
  newBtn.style.display = "inline-block";  // 버튼 표시

  // 클릭 시: 모달 닫기 → handler 함수 실행
  newBtn.onclick = () => {
    closeResultModal();
    if (handler) handler();
  };

  // DOM에서 이전 버튼을 새 버튼으로 교체
  oldBtn.parentNode.replaceChild(newBtn, oldBtn);
}

/**
 * showSolutionModal(title, content, buttonText, onNext, showTts)
 * ─────────────────────────────────────
 * [역할] 풀이 설명, 개념 설명, 이해도 평가 결과 등을 모달로 표시합니다.
 *        TTS 버튼 포함 여부를 선택할 수 있습니다.
 *
 * [사용 예시]
 *   showSolutionModal(
 *     "📖 분수 개념 익히기",         // 제목
 *     "분수는 전체를 나눈 부분...",    // 내용
 *     "내가 설명해보기 🗣️",          // 버튼 텍스트
 *     () => showStudentExplainModal(), // 버튼 클릭 시 실행 함수
 *     true                             // TTS 버튼 표시 여부
 *   );
 *
 * [루미 선생님 이미지 포함]
 *   풀이 박스 상단에 AI 튜터 루미의 이미지를 함께 보여줍니다.
 *
 * @param {string}   title      - 모달 제목
 * @param {string}   content    - 표시할 내용 (수식 포함 가능)
 * @param {string}   buttonText - 하단 버튼 텍스트
 * @param {Function} onNext     - 버튼 클릭 시 실행할 함수
 * @param {boolean}  showTts    - TTS 음성 버튼 표시 여부 (true/false)
 */
function showSolutionModal(title, content, buttonText, onNext, showTts = false) {
  // 먼저 모달의 이전 내용을 모두 초기화
  resetModal();

  // 필요한 모달 요소 가져오기
  const titleEl = document.getElementById("resultTitle");
  const solBox = document.querySelector("#resultModal .solution-box");
  const solEl = document.getElementById("solutionText");
  const ttsBtn = document.getElementById("ttsBtn");

  // 모달 제목 설정
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
  // solBox.innerHTML을 새로 작성했기 때문에 위에서 가져온 solEl 참조가 무효화됨
  const newSolEl = document.getElementById("solutionText");
  if (newSolEl) {
    newSolEl.style.display = "block";
    // 수식 렌더링을 위해 prepareMathDisplayText 함수로 분수 등 LaTeX 변환
    newSolEl.innerText = prepareMathDisplayText(content);

    // ⭐ MathJax 수식 렌더링 함수 호출 (화면에 HTML이 그려진 후 실행)
    if (typeof renderMath === "function") {
      // setTimeout으로 약간의 지연을 주어 DOM 업데이트 완료 후 렌더링
      setTimeout(() => renderMath("solutionText"), 50);
    }
  }

  // if (solEl) {
  //   solEl.style.display = "block";
  //   solEl.innerText = prepareMathDisplayText(content);
  //   if (typeof renderMath === "function") renderMath("solutionText");
  // }

  // TTS 버튼 설정 (showTts가 true인 경우에만 표시)
  if (ttsBtn) {
    if (showTts) {
      ttsBtn.style.display = "inline-block";  // 버튼 표시
      ttsBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        // 클릭 시 TTS 재생/일시정지 토글
        toggleModalTTS(content, ttsBtn);
      };
    } else {
      ttsBtn.style.display = "none";  // 버튼 숨김 (학생 평가 결과 등에선 불필요)
    }
  }

  // 하단 버튼(다음/확인) 설정 후 모달 열기
  setResultAction(onNext, buttonText);
  openResultModal();
}

/**
 * showInputModal(title, placeholder, buttonText, onSubmit)
 * ─────────────────────────────────────
 * [역할] 학생이 텍스트를 직접 입력할 수 있는 모달을 표시합니다.
 *        주로 "직접 설명해보기" 단계에서 사용합니다.
 *
 * [사용 시점] 학생이 개념을 자기만의 말로 설명하는 단계
 *
 * [모달 내용] 제목 + textarea(입력창) + 제출 버튼
 *
 * @param {string}   title       - 모달 제목 (예: "🗣️ 분수 직접 설명하기")
 * @param {string}   placeholder - textarea 힌트 텍스트
 * @param {string}   buttonText  - 제출 버튼 텍스트
 * @param {Function} onSubmit    - 제출 버튼 클릭 시 입력값을 받아 처리하는 함수
 */
function showInputModal(title, placeholder, buttonText, onSubmit) {
  resetModal();  // 이전 내용 초기화
  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");

  if (titleEl) titleEl.innerText = title;

  if (msgEl) {
    // textarea와 제출 버튼 동적 생성
    msgEl.innerHTML = `
      <textarea id="modal-student-text" rows="6" placeholder="${placeholder}" style="width:100%;padding:10px;box-sizing:border-box;"></textarea>
      <button id="modal-student-submit" type="button" style="margin-top:12px;">${buttonText}</button>
    `;
  }
  openResultModal();

  // 제출 버튼 클릭 이벤트 등록
  const submitBtn = document.getElementById("modal-student-submit");
  if (submitBtn) {
    submitBtn.onclick = (e) => {
      e.preventDefault();
      // textarea의 입력값을 가져와 onSubmit 콜백에 전달
      const value = document.getElementById("modal-student-text")?.value || "";
      onSubmit(value);
    };
  }
}

/**
 * showQuestionModal(prob, imageB64)
 * ─────────────────────────────────────
 * [역할] AI가 출제한 수학 문제를 모달로 표시하고,
 *        학생이 답안을 작성해 제출할 수 있게 합니다.
 *
 * [사용 시점] loadProblem()으로 문제를 받아온 후 호출
 *
 * [모달 내용]
 *   - 문제 텍스트 (수식 렌더링 포함)
 *   - 이미지 (있는 경우 base64로 표시)
 *   - 답안 입력 textarea
 *   - 제출하기 버튼
 *
 * @param {object} prob      - 문제 객체 (문제, 정답, 단원 등 포함)
 * @param {string} imageB64  - 문제 이미지 base64 문자열 (없으면 빈 문자열)
 */
function showQuestionModal(prob, imageB64 = "") {
  resetModal();
  const titleEl = document.getElementById("resultTitle");
  const msgEl = document.getElementById("resultMessage");

  // 모달 제목: "📝 퀴즈 (단원명)"
  if (titleEl) titleEl.innerText = `📝 퀴즈 (${prob["단원"] ?? "-"})`;
  if (msgEl) {
    // 문제 텍스트 + 이미지(있으면) + 답안 입력창 + 제출 버튼
    msgEl.innerHTML = `
      <div id="modal-problem-text"></div>
      ${imageB64 ? `<img src="data:image/png;base64,${imageB64}" style="max-width:100%;margin-top:12px;">` : ""}
      <textarea id="modal-answer-input" rows="5" placeholder="정답과 풀이를 적어주세요." style="width:100%;padding:10px;margin-top:12px;box-sizing:border-box;"></textarea>
      <button id="modal-submit-btn" type="button" style="margin-top:12px;">제출하기</button>
    `;
    // 문제 텍스트를 별도 div에 설정하고 MathJax 렌더링
    const p = document.getElementById("modal-problem-text");
    if (p) {
      p.innerText = prepareMathDisplayText(prob["문제"] ?? "문제를 불러올 수 없어요.");
      if (typeof renderMath === "function") renderMath("modal-problem-text");
    }
  }
  openResultModal();

  // 제출하기 버튼 클릭 이벤트 등록
  const submitBtn = document.getElementById("modal-submit-btn");
  if (submitBtn) {
    submitBtn.onclick = async (e) => {
      e.preventDefault();
      // 입력된 답안을 가져와 채점 함수에 전달
      const answer = document.getElementById("modal-answer-input")?.value || "";
      await submitCurrentAnswer(answer);
    };
  }
}



//───────────────────────────────────────
// 오늘 학습 화면 초기화 및 X 버튼 이벤트
//───────────────────────────────────────

/**
 * renderToday()
 * ─────────────────────────────────────
 * [역할] "오늘 학습" 섹션 화면의 초기 상태를 설정합니다.
 *        goPage("today") 호출 시 실행됩니다.
 *
 * [초기화 내용]
 *   1. 단원 선택 화면(step-select_unit) 표시
 *   2. 모달 X 버튼에 오디오 정지 이벤트 등록
 *   3. "학습 시작" 버튼 클릭 이벤트 등록 (중복 방지 패턴 사용)
 *
 * [학습 시작 버튼 흐름]
 *   클릭 → 로딩 표시 → POST /api/explain (AI 개념 설명 요청) →
 *   설명 수신 → showSolutionModal로 개념 설명 표시
 *
 * [API 호출 - 학습 시작 버튼]
 *   엔드포인트: POST /api/explain
 *   전송 데이터: { unit_name: "선택된 단원명" }
 *   응답 예시:  { explanation: "분수는 전체를 같은 크기로 나누었을 때..." }
 */
function renderToday() {
  // 단원 선택 영역을 화면에 표시
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

  // "학습 시작" 버튼 이벤트 등록 (dataset.bound로 중복 등록 방지)
  const btnStart = document.getElementById("btn-start");
  if (btnStart && !btnStart.dataset.bound) {
    btnStart.dataset.bound = "1";  // 이벤트가 등록됐음을 표시
    btnStart.addEventListener("click", async () => {
      // 로딩 오버레이 표시 (화면 전체를 반투명으로 덮어 "처리 중" 표시)
      document.getElementById("loading-overlay").style.display = "flex";
      // DOM 업데이트가 즉시 반영되도록 잠깐 대기 (비동기 처리의 실행 순서 보장)
      await new Promise(resolve => setTimeout(resolve, 100));

      // 선택된 단원 가져오기
      const unit = document.getElementById("unit-select")?.value;
      if (!unit) {
        document.getElementById("loading-overlay").style.display = "none";
        alert("단원을 선택하세요");
        return;
      }

      // 선택된 단원을 localStorage에 저장 (다른 함수에서 참조용)
      localStorage.setItem("selected_unit", unit);

      try {
        // POST /api/explain: AI에게 해당 단원의 개념 설명 요청
        const res = await apiFetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ unit_name: unit }),
        });
        const data = await res.json();
        document.getElementById("loading-overlay").style.display = "none";

        // 서버에서 받은 개념 설명 텍스트
        const explanation = data.explanation || "설명이 없습니다.";

        // 개념 설명 모달 표시 (TTS 버튼 포함)
        // 다음 버튼 클릭 시 → 학생 직접 설명 입력 단계로 이동
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

/**
 * showStudentExplainModal(unit)
 * ─────────────────────────────────────
 * [역할] 학생이 이해한 내용을 직접 텍스트로 입력하는 모달을 표시합니다.
 *        입력 후 AI가 이해도를 평가합니다.
 *
 * [사용 시점] 개념 설명 모달의 "내가 설명해보기" 버튼 클릭 후
 *
 * [AI 이해도 평가 API]
 *   엔드포인트: POST /api/explain/evaluate
 *   전송 데이터: { concept: "단원명", student_explanation: "학생이 입력한 설명" }
 *   응답 예시:  { feedback: "잘 이해했어요!", is_passed: true }
 *
 * [평가 결과에 따른 분기]
 *   - is_passed = true  → "문제 풀기" 단계로 진행 (loadProblem)
 *   - is_passed = false → 보충 설명 요청 (POST /api/reexplain)
 *
 * [보충 설명 API]
 *   엔드포인트: POST /api/reexplain
 *   전송 데이터: { unit_name: "단원명" }
 *   응답 예시:  { explanation: "더 쉽게 설명하면..." }
 *
 * @param {string} unit - 현재 학습 중인 단원명
 */
function showStudentExplainModal(unit) {
  // 텍스트 입력 모달 표시
  showInputModal(`🗣️ ${unit} 직접 설명하기`, "어떻게 이해했는지 적어줘", "설명 완료! ✨", async (studentText) => {
    // 빈 입력 방지
    if (!studentText.trim()) return alert("설명을 적어줘");
    try {
      // POST /api/explain/evaluate: 학생 설명을 AI가 평가
      const res = await apiFetch("/api/explain/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concept: unit, student_explanation: studentText }),
      });
      const data = await res.json();
      const feedback = data.feedback || "평가 결과가 없습니다.";

      if (data.is_passed) {
        // 이해도 통과 → 문제 풀기 단계로 이동
        showSolutionModal("👨‍🏫 이해도 검토 결과", feedback, "이제 문제 풀기 📝", async () => { await loadProblem(); }, false);
      } else {
        // 이해도 미통과 → 보충 설명 제공
        showSolutionModal("👨‍🏫 이해도 검토 결과", feedback, "더 쉬운 보충 설명 듣기 ➡️", async () => {
          // 보충 설명 로딩 중 표시
          showSolutionModal("📖 보충 학습 (더 쉬운 설명)", "루미 선생님이 보충 설명을 준비 중... ⏳", "기다리는 중...", () => {}, false);
          try {
            // POST /api/reexplain: 더 쉬운 보충 설명 요청
            const res2 = await apiFetch("/api/reexplain", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ unit_name: unit }),
            });
            const re_data = await res2.json();
            // 보충 설명 모달 표시 (TTS 포함), 다음으로 문제 풀기
            showSolutionModal("📖 보충 학습", re_data.explanation || "설명이 없습니다.", "이제 문제 풀기 📝", async () => { await loadProblem(); }, true);
          } catch (e) { alert("보충 설명 로드 실패"); }
        }, false);
      }
    } catch { alert("평가 실패"); }
  });
}

// (이하 loadUnits, loadProblem, submitCurrentAnswer 등 기존 로직 동일)

/**
 * loadUnits()
 * ─────────────────────────────────────
 * [역할] 서버에서 단원 목록을 가져와 드롭다운 선택 목록을 채웁니다.
 *        goPage("today") 호출 시 renderToday()와 함께 실행됩니다.
 *
 * [API 호출]
 *   엔드포인트: GET /api/units
 *   응답 예시:  { units: ["분수의 덧셈", "분수의 뺄셈", "소수", ...] }
 *
 * [DOM 업데이트]
 *   id="unit-select" 인 <select> 요소에 <option> 태그를 동적으로 추가합니다.
 */
async function loadUnits() {
  const select = document.getElementById("unit-select");
  if (!select) return;
  try {
    // GET /api/units: 단원 목록 요청
    const res = await apiFetch("/api/units");
    const data = await res.json();

    // 기본 옵션 먼저 추가, 그 다음 각 단원을 option으로 추가
    select.innerHTML = `<option value="">단원 선택</option>`;
    (data.units || []).forEach(u => {
      const opt = document.createElement("option");
      opt.value = u;  // 선택값: 단원명
      opt.text = u;   // 표시 텍스트: 단원명
      select.add(opt);
    });
  } catch (e) { console.error("단원 목록 로드 실패"); }
}

/**
 * loadProblem()
 * ─────────────────────────────────────
 * [역할] 현재 선택된 단원의 수학 문제를 서버에서 가져옵니다.
 *        문제를 받으면 showQuestionModal()로 문제 모달을 표시합니다.
 *
 * [사용 시점]
 *   - 이해도 평가 통과 후 → loadProblem() 호출
 *   - 보충 설명 완료 후 → loadProblem() 호출
 *   - 채점 후 "다시 풀기" 클릭 시 → loadProblem() 호출
 *
 * [API 호출]
 *   엔드포인트: GET /api/problem?unit=분수의덧셈
 *   응답 예시:  {
 *     problem: { 문제: "...", 정답: "1/2", 단원: "분수의 덧셈" },
 *     image_b64: "base64인코딩된이미지..." (없으면 빈 문자열)
 *   }
 *
 * [데이터 저장]
 *   문제 전체 데이터를 localStorage에 JSON 형태로 저장합니다.
 *   채점 시 다시 불러와 서버에 함께 전송합니다.
 */
async function loadProblem() {
  // localStorage에서 현재 선택된 단원 가져오기
  const unit = localStorage.getItem("selected_unit");
  try {
    // GET /api/problem?unit=단원명: 해당 단원의 문제 요청
    const res = await apiFetch(`/api/problem?unit=${encodeURIComponent(unit)}`);
    const data = await res.json();
    const prob = data.problem;
    if (!prob) throw new Error("문제가 없습니다.");

    // 문제 데이터를 localStorage에 저장 (submitCurrentAnswer에서 사용)
    localStorage.setItem("current_problem", JSON.stringify(prob));

    // 정답을 전역 변수에 저장 (다양한 키명 지원)
    currentAnswer = prob.answer || prob["정답"] || prob["답"] || "";
    currentQuestionText = prob["문제"] || "";

    // 문제와 이미지를 모달로 표시
    showQuestionModal(prob, data.image_b64 || "");
  } catch (e) {
    console.error("문제 로드 중 상세 오류:", e);
    alert("문제를 불러오지 못했습니다.");
  }
}

/**
 * submitCurrentAnswer(answerText)
 * ─────────────────────────────────────
 * [역할] 학생이 입력한 답안을 서버에 전송하고 AI 채점을 받습니다.
 *        채점 후 최종 피드백 모달을 표시합니다.
 *
 * [사용 시점] 문제 모달의 "제출하기" 버튼 클릭 시
 *
 * [API 호출]
 *   엔드포인트: POST /api/evaluate
 *   전송 데이터: {
 *     problem: { 문제: "...", 정답: "1/2", ... },   // localStorage에서 불러온 문제 객체
 *     student_answer: "학생이 입력한 답"
 *   }
 *   응답 예시: {
 *     is_correct: true/false,
 *     feedback: "정답입니다! 풀이: ...",
 *   }
 *
 * [채점 후 처리]
 *   - 결과 모달 닫기 → showFinalFeedbackModal() 호출
 *   - 오류 시 제출 버튼 다시 활성화
 *
 * @param {string|null} answerText - 학생이 입력한 답안 (null이면 빈 문자열 처리)
 */
async function submitCurrentAnswer(answerText = null) {
  const studentAnswer = answerText ?? "";

  // 1. 저장된 문제 데이터 가져오기 (loadProblem에서 저장한 JSON)
  const savedData = localStorage.getItem("current_problem");
  if (!savedData) {
    alert("문제 데이터가 사라졌습니다. 다시 시도해 주세요.");
    return;
  }

  // JSON 문자열을 JavaScript 객체로 파싱
  const problemObj = JSON.parse(savedData);

  try {
    // 2. 서버로 채점 요청 (POST /api/evaluate)
    const res = await apiFetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem: problemObj,        // 백엔드가 기대하는 키 'problem'
        student_answer: studentAnswer
      }),
    });

    // 3. 응답 확인 (.catch(() => ({}))로 JSON 파싱 실패 시 빈 객체 반환)
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      console.error("서버 채점 에러:", data); // 위에서 이미 읽은 data 사용
      throw new Error(data.detail || "채점 실패");
    }

    // 4. 채점 성공: 문제 모달 닫고 최종 피드백 모달 표시
    closeResultModal();
    showFinalFeedbackModal(data.feedback, data.is_correct);

  } catch (err) {
    console.error("제출 프로세스 중 오류:", err);
    alert("채점 중 오류가 발생했습니다."+ err.message);

    // 오류 시 제출 버튼 다시 활성화 (사용자가 재시도 가능)
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

/**
 * showFinalFeedbackModal(feedback, isCorrect)
 * ─────────────────────────────────────
 * [역할] 채점 결과(피드백 텍스트)를 최종 피드백 모달(feedbackModal)에 표시합니다.
 *        "다시 풀기"와 "다른 단원 선택" 두 버튼을 제공합니다.
 *
 * [사용 시점] submitCurrentAnswer()에서 채점 결과를 받은 직후
 *
 * [모달 구조]
 *   - feedbackText    : 채점 피드백 텍스트 (수식 렌더링 포함)
 *   - feedbackRetryBtn    : "다시 풀기" 버튼 → loadProblem() 재호출
 *   - feedbackNextUnitBtn : "다른 단원 선택" 버튼 → goPage("today")로 초기화
 *   - closeFeedbackModalBtn : X 버튼으로 모달 닫기
 *
 * [버튼 비활성화 패턴]
 *   모달이 열리고 500ms 후에 버튼을 활성화합니다.
 *   빠른 더블 클릭으로 중복 실행되는 버그를 방지합니다.
 *
 * @param {string}  feedback  - AI 채점 피드백 텍스트
 * @param {boolean} isCorrect - 정답 여부 (현재 UI에서는 직접 활용하지 않음)
 */
function showFinalFeedbackModal(feedback, isCorrect) {
  // 에러 방지를 위해 요소가 있는지 하나씩 체크하며 진행합니다.
  const feedbackText = document.getElementById("feedbackText");
  const retryBtn = document.getElementById("feedbackRetryBtn");
  const nextUnitBtn = document.getElementById("feedbackNextUnitBtn");
  const closeBtn = document.getElementById("closeFeedbackModalBtn");

  if (feedbackText) {
    // prepareMathDisplayText 함수가 있는지 확인 후 사용 (분수 등 LaTeX 변환)
    const processedText = (typeof prepareMathDisplayText === "function")
                          ? prepareMathDisplayText(feedback)
                          : feedback;
    feedbackText.innerText = processedText;

    // MathJax로 피드백 텍스트 내 수식 렌더링
    if (typeof renderMath === "function") {
      renderMath("feedbackText");
    }
  }

  // "다시 풀기" 버튼 설정: 클릭 시 모달 닫고 새 문제 출제
  if (retryBtn) {
    retryBtn.style.display = "inline-block";
    retryBtn.disabled = true;  // 초기에는 비활성화 (500ms 후 활성화)
    retryBtn.onclick = async (e) => {
      if(e) e.preventDefault();
      if (typeof closeFeedbackModal === "function") closeFeedbackModal();
      if (typeof loadProblem === "function") await loadProblem();  // 새 문제 출제
    };
  }

  // "다른 단원 선택" 버튼 설정: 클릭 시 모달 닫고 단원 선택 화면으로
  if (nextUnitBtn) {
    nextUnitBtn.style.display = "inline-block";
    nextUnitBtn.disabled = true;  // 초기에는 비활성화 (500ms 후 활성화)
    nextUnitBtn.onclick = (e) => {
      if(e) e.preventDefault();
      if (typeof closeFeedbackModal === "function") closeFeedbackModal();
      localStorage.setItem("step", "select_unit");  // 학습 단계 초기화
      if (typeof goPage === "function") goPage("today");  // today 페이지로 이동
    };
  }

  // 최종 피드백 모달 열기 (app.js에 정의된 함수)
  if (typeof openFeedbackModal === "function") {
    openFeedbackModal();
  } else {
    console.error("openFeedbackModal 함수가 정의되지 않았습니다.");
  }

  // 500ms 후에 버튼 활성화 (빠른 클릭 방지)
  setTimeout(() => {
    if (retryBtn) retryBtn.disabled = false;
    if (nextUnitBtn) nextUnitBtn.disabled = false;
    if (closeBtn) closeBtn.disabled = false;
  }, 500);
}
