"""
services/tutor_service.py  ─  튜터 로직 서비스 계층

[서비스 계층 패턴(Service Layer Pattern)이란?]
웹 애플리케이션에서 코드를 역할별로 분리하는 설계 방식입니다.

역할 분리 구조:
  ┌──────────────────────────────────────────────────────┐
  │  Router 계층 (app/routers/tutor.py)                  │
  │  → HTTP 요청/응답만 담당. 경로, 상태 코드, 인증 처리      │
  └─────────────────────────┬────────────────────────────┘
                            │ 비즈니스 로직 호출
  ┌─────────────────────────▼────────────────────────────┐
  │  Service 계층 (app/services/tutor_service.py)        │
  │  → 지금 이 파일! 핵심 비즈니스 로직을 처리                │
  │  → 비동기 처리, 데이터 가공, 여러 통합 함수 조합          │
  └─────────────────────────┬────────────────────────────┘
                            │ LangChain 체인 실행 요청
  ┌─────────────────────────▼────────────────────────────┐
  │  Integration 계층 (app/tutor/integration.py)         │
  │  → LangChain 체인 실행, 외부 API 호출, RAG 검색         │
  └──────────────────────────────────────────────────────┘

[서비스 계층을 사용하는 이유]
1. 관심사 분리(Separation of Concerns)
   - Router는 "어떻게 받고 보낼지"만 신경 씁니다.
   - Service는 "무엇을 처리할지"만 신경 씁니다.
2. 테스트 용이성
   - Router 없이도 Service 함수만 단독으로 테스트할 수 있습니다.
3. 재사용성
   - 여러 Router에서 같은 Service 함수를 호출할 수 있습니다.
4. 유지보수성
   - LangChain 로직이 바뀌어도 Service 계층만 수정하면 됩니다.

[asyncio.to_thread()가 필요한 이유]
LangChain의 체인 실행 함수들(explain_concept, evaluate_answer 등)은
동기(sync) 함수입니다. 일반 await로 호출할 수 없습니다.

FastAPI는 async/await 기반 비동기 서버입니다.
동기 함수를 async 함수 안에서 직접 호출하면,
그 함수가 실행되는 동안 전체 서버가 블록(멈춤)되어
다른 클라이언트의 요청을 처리하지 못합니다.

asyncio.to_thread(동기함수, 인자)는
동기 함수를 별도의 스레드(Thread)에서 실행합니다.
메인 이벤트 루프는 블록되지 않아 다른 요청을 계속 처리할 수 있습니다.

  [동기 함수 직접 호출 - 나쁜 예]
  result = explain_concept(unit_name)   ← 서버 전체가 멈춤

  [asyncio.to_thread 사용 - 좋은 예]
  result = await asyncio.to_thread(explain_concept, unit_name)
           ↑ 이 함수가 실행되는 동안 서버는 다른 요청을 처리할 수 있음
"""

import os, base64, zipfile, asyncio

# integration.py에서 LangChain 체인 함수들을 임포트합니다.
# 각 함수는 LangChain RunnableSequence(체인)를 실행하여 AI 응답을 반환합니다.
from app.tutor.integration import (
    explain_concept,                   # 개념 설명 생성 (LangChain 체인 실행)
    reexplain_concept,                 # 다른 방식으로 재설명 생성
    ask_question_to_tutor,             # 튜터에게 자유 질문 (채팅)
    evaluate_answer,                   # 문제 답안 채점
    evaluate_concept_understanding,    # 학생의 개념 이해도 평가
    get_units,                         # DB에서 단원 목록 조회
    get_problem_by_unit,               # 단원별 문제 조회
    get_exam_problems,                 # 시험용 문제 목록 조회
    classify_math_question,            # 자유학습: 수학 질문 분류
    ask_question_with_rag_context,     # 자유학습: RAG+LLM 답변
)


# ─────────────────────────────────────────────────────────
# 단원 목록 조회 서비스
#
# [호출 흐름]
# Router: GET /api/units → fetch_units()
# Service: fetch_units() → get_units.invoke({})
# Integration: get_units → DB 조회 → 단원 목록 반환
#
# get_units는 LangChain Tool로 래핑된 함수이므로 .invoke({}) 로 호출합니다.
# ({}: 인자가 없는 Tool 호출 방식)
# ─────────────────────────────────────────────────────────
async def fetch_units() -> list[str]:
    return get_units.invoke({})


# ─────────────────────────────────────────────────────────
# 단원별 문제 조회 서비스
#
# [호출 흐름]
# Router: GET /api/problem?unit_name=분수 → fetch_problem("분수")
# Service: fetch_problem() → get_problem_by_unit.invoke({"unit_name": "분수"})
# Integration: get_problem_by_unit → DB에서 해당 단원 문제 조회 → dict 반환
#
# 반환값 예시:
#   {"id": "001", "question": "3/4 + 1/4 = ?", "answer": "1", "unit": "분수"}
# ─────────────────────────────────────────────────────────
async def fetch_problem(unit_name: str) -> dict | None:
    return get_problem_by_unit.invoke({"unit_name": unit_name})


# ─────────────────────────────────────────────────────────
# 문제 이미지 base64 변환 서비스
#
# [역할]
# 문제 ID에 해당하는 이미지 파일을 찾아 base64 문자열로 반환합니다.
# 브라우저에서 <img src="data:image/png;base64,..." /> 형식으로 바로 표시 가능합니다.
#
# [탐색 순서]
# 1. data/raw/ 폴더에서 직접 이미지 파일 탐색
# 2. data/ 폴더의 zip 파일 내부에서 이미지 탐색
# 3. 없으면 None 반환
#
# [base64란?]
# 이진 파일(이미지)을 텍스트(ASCII)로 변환하는 인코딩 방식입니다.
# HTTP JSON 응답에는 이진 데이터를 직접 담을 수 없으므로 base64로 변환합니다.
# base64.b64encode(bytes).decode("utf-8") → "iVBORw0KGgoAAAANSUhEUg..." 형태의 문자열
# ─────────────────────────────────────────────────────────
def get_problem_image_b64(problem_id: str) -> str | None:
    """문제 ID에 해당하는 이미지를 base64로 반환. 없으면 None."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_path = os.path.join(base_dir, "data", "raw")
    target_id = str(problem_id).strip()
    valid_exts = ('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')

    # 1단계: data/raw/ 폴더에서 이미지 파일 직접 탐색
    if os.path.exists(raw_path):
        for root, dirs, files in os.walk(raw_path):
            for file in files:
                if target_id in file and file.endswith(valid_exts):
                    with open(os.path.join(root, file), "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")

    # 2단계: data/ 폴더의 zip 파일 내부에서 이미지 탐색
    # zipfile.ZipFile을 사용하면 zip을 압축 해제하지 않고 내용물을 바로 읽을 수 있습니다.
    data_path = os.path.join(base_dir, "data")
    for root, dirs, files in os.walk(data_path):
        for file in files:
            if file.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(os.path.join(root, file), "r") as z:
                        for name in z.namelist():
                            bn = os.path.basename(name).lower()
                            if target_id in bn and any(bn.endswith(e.lower()) for e in valid_exts):
                                return base64.b64encode(z.read(name)).decode("utf-8")
                except Exception:
                    continue
    return None


# ─────────────────────────────────────────────────────────
# 개념 설명 서비스
#
# [호출 흐름]
# Router: POST /api/explain → get_explanation("분수")
# Service: get_explanation() → explain_concept("분수")
# Integration: explain_concept → LangChain 프롬프트 실행 → AI 설명 텍스트 반환
#
# [explain_concept이 동기 함수임에도 await 없이 호출하는 이유]
# explain_concept()이 비교적 빠른 동기 함수이거나,
# 이 프로젝트에서 단순화된 구현을 사용하는 경우입니다.
# 실제 운영에서는 asyncio.to_thread()로 감싸는 것을 권장합니다.
# (재설명 get_reexplanation은 asyncio.to_thread를 사용하는 것과 비교해 보세요)
# ─────────────────────────────────────────────────────────
async def get_explanation(unit_name: str) -> str:
    return explain_concept(unit_name)

# ─────────────────────────────────────────────────────────
# 개념 재설명 서비스
#
# [호출 흐름]
# Router: POST /api/reexplain → get_reexplanation("분수")
# Service: get_reexplanation() → asyncio.to_thread(reexplain_concept, "분수")
# Integration: reexplain_concept → LangChain 체인 실행 → 다른 방식의 설명 반환
#
# [asyncio.to_thread 사용 이유]
# reexplain_concept은 LangChain 체인을 실행하는 동기 함수입니다.
# AI 모델 API 호출이 포함되어 수 초가 걸릴 수 있습니다.
# asyncio.to_thread()로 별도 스레드에서 실행하여
# 서버가 다른 요청도 동시에 처리할 수 있게 합니다.
# ─────────────────────────────────────────────────────────
async def get_reexplanation(unit_name: str) -> str:
    return await asyncio.to_thread(reexplain_concept, unit_name)

# ─────────────────────────────────────────────────────────
# 개념 이해도 평가 서비스
#
# [호출 흐름]
# Router: POST /api/evaluate-concept → evaluate_explanation("분수", "학생의 설명...")
# Service: evaluate_explanation() → evaluate_concept_understanding() 호출
# Integration: evaluate_concept_understanding → LangChain으로 AI 평가 → 피드백 텍스트 반환
#
# [PASS 판별 로직]
# AI가 생성한 피드백에 "[PASS]" 문자열이 포함되어 있으면 통과로 간주합니다.
# 대소문자 무관하게 판별하기 위해 .upper()를 사용합니다.
# is_passed: True → 다음 단계로 진행 / False → 재학습 필요
# ─────────────────────────────────────────────────────────
async def evaluate_explanation(concept: str, student_explanation: str) -> dict:
    feedback = evaluate_concept_understanding(concept, student_explanation)
    # AI 피드백에 "[PASS]"가 포함되어 있으면 개념 이해 통과로 처리
    is_passed = "[PASS]" in feedback.upper()
    return {"feedback": feedback, "is_passed": is_passed}


# ─────────────────────────────────────────────────────────
# 튜터 질문 서비스 (일반 채팅)
#
# [호출 흐름]
# Router: POST /api/chat → ask_tutor("분수가 뭐예요?", [...대화이력...])
# Service: ask_tutor() → ask_question_to_tutor(question, chat_history)
# Integration: ask_question_to_tutor → LangChain 대화 체인 실행 → AI 답변 반환
#
# chat_history: 이전 대화 내용을 리스트로 전달하여 문맥을 유지합니다.
# 예시: [{"role": "user", "content": "분수가 뭐예요?"}, {"role": "assistant", "content": "..."}]
# ─────────────────────────────────────────────────────────
async def ask_tutor(question: str, chat_history: list) -> str:
    return ask_question_to_tutor(question, chat_history)


# ─────────────────────────────────────────────────────────
# 단일 문제 답안 채점 서비스
#
# [호출 흐름]
# Router: POST /api/grade → grade_answer(problem_dict, "학생의 답")
# Service: grade_answer() → evaluate_answer(problem, student_answer)
# Integration: evaluate_answer → LangChain으로 AI 채점 → 피드백 텍스트 반환
#
# [정답 판별 로직]
# AI 피드백에 "[정답]"이 포함되어 있으면 정답으로 간주합니다.
# is_correct: True → 정답 / False → 오답
# ─────────────────────────────────────────────────────────
async def grade_answer(problem: dict, student_answer: str) -> dict:
    feedback = evaluate_answer(problem, student_answer)
    # AI 피드백에 "[정답]"이 포함되어 있으면 정답으로 처리
    is_correct = "[정답]" in feedback
    return {"feedback": feedback, "is_correct": is_correct}


# ─────────────────────────────────────────────────────────
# 시험 관련 서비스 함수
# ─────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────
# 시험 문제 생성 서비스
#
# [호출 흐름]
# Router: POST /api/exam/generate → generate_exam_questions("분수")
# Service: generate_exam_questions() → get_exam_problems("분수", n=10)
# Integration: get_exam_problems → DB에서 해당 단원 문제 10개 랜덤 조회 → list 반환
#
# n=10: 시험 문제 수 (기본값 10문제)
# ─────────────────────────────────────────────────────────
async def generate_exam_questions(unit_name: str) -> list:
    return get_exam_problems(unit_name, n=10)


# ─────────────────────────────────────────────────────────
# 시험 전체 채점 서비스 (병렬 처리 핵심!)
#
# [역할]
# 시험 문제 전체(10문제)를 한 번에 채점하고 점수를 계산합니다.
#
# [병렬 처리가 필요한 이유]
# 10문제를 순서대로(직렬로) 채점하면:
#   문제1 채점(3초) → 문제2 채점(3초) → ... → 문제10 채점(3초) = 총 30초
#
# asyncio.gather()로 동시에(병렬로) 채점하면:
#   문제1~10을 동시에 채점 → 가장 오래 걸리는 문제의 시간 = 약 3~5초
#
# [asyncio.gather()란?]
# 여러 코루틴(async 함수)을 동시에 실행하고 모든 결과가 나올 때까지 기다립니다.
# asyncio.gather(*[코루틴1, 코루틴2, ...]) → [결과1, 결과2, ...] 반환
#
# [asyncio.to_thread + asyncio.gather 조합]
# asyncio.to_thread(동기함수, 인자): 동기 함수를 별도 스레드에서 비동기로 실행
# asyncio.gather(*[...]): 여러 asyncio.to_thread를 동시에 실행
# 결과: 여러 동기 함수가 서로 다른 스레드에서 병렬로 실행됨
#
# [호출 흐름]
# Router: POST /api/exam/grade → grade_exam_answers(problems, answers)
# Service: grade_exam_answers()
#   → asyncio.gather(
#        asyncio.to_thread(grade_one_sync, problems[0], answers[0]),
#        asyncio.to_thread(grade_one_sync, problems[1], answers[1]),
#        ... (10개 동시 실행)
#      )
# Integration: evaluate_answer() → 각 문제별 AI 채점 결과 반환
# ─────────────────────────────────────────────────────────
async def grade_exam_answers(problems: list, answers: list) -> dict:

    # 단일 문제 채점 내부 함수 (동기 함수 - 스레드에서 실행됨)
    # grade_one_sync는 asyncio.to_thread()에 전달되어 별도 스레드에서 실행됩니다.
    def grade_one_sync(problem, answer):
        # 1. 공란인 경우에도 설명을 가져오기 위해 evaluate_answer를 호출하도록 변경하거나,
        #    최소한 설명을 포함하도록 수정해야 합니다.
        user_answer_str = str(answer).strip() if answer else ""

        try:
            # 공란이더라도 evaluate_answer가 해설을 반환하도록 호출합니다.
            # evaluate_answer는 LangChain 체인을 실행하는 동기 함수입니다.
            feedback = evaluate_answer(problem, user_answer_str)

            # 정답 여부 판단 - AI 피드백에 "[정답]"이 포함된 경우 정답으로 처리
            is_correct = "[정답]" in feedback

            # 만약 공란이었다면 피드백 앞에 안내 문구 추가 (선택 사항)
            if not user_answer_str:
                feedback = f"답을 입력하지 않았습니다.\n\n{feedback}"

            return {"feedback": feedback, "is_correct": is_correct}

        except Exception as e:
            # 채점 중 예외가 발생한 경우 오답 처리하고 에러 메시지를 피드백으로 반환
            return {"feedback": f"채점 중 오류가 발생했습니다. [오답] ({e})", "is_correct": False}

    # ─────────────────────────────────────────────────────
    # 핵심: asyncio.gather + asyncio.to_thread로 병렬 채점
    #
    # [코드 설명]
    # - range(len(problems)): 0, 1, 2, ..., 9 (10문제)
    # - asyncio.to_thread(grade_one_sync, problems[i], answers[i]):
    #     i번째 문제와 답안을 grade_one_sync 함수에 전달하여 별도 스레드에서 실행
    # - answers[i] if i < len(answers) else "":
    #     제출된 답안 수가 문제 수보다 적을 경우 빈 문자열로 처리
    # - *[...]: 리스트 컴프리헨션으로 만든 코루틴 리스트를 언패킹하여 gather에 전달
    # - await asyncio.gather(...): 모든 코루틴이 완료될 때까지 대기 후 결과 리스트 반환
    # ─────────────────────────────────────────────────────
    results = await asyncio.gather(*[
        asyncio.to_thread(
            grade_one_sync,
            problems[i],
            answers[i] if i < len(answers) else ""
        )
        for i in range(len(problems))
    ])

    # 채점 결과 집계
    # sum(1 for r in results if r["is_correct"]): 정답 개수 계산
    correct_count = sum(1 for r in results if r["is_correct"])
    total = len(problems)
    # 점수 계산: (정답수 / 전체문제수) * 100, 소수점 반올림
    score = round(correct_count / total * 100) if total > 0 else 0

    # 틀린 문제 번호 목록 (1-indexed로 변환, 예: [2, 5, 8])
    wrong_numbers = [i + 1 for i, r in enumerate(results) if not r["is_correct"]]

    # :star: 핵심 수정 부분: 'if not results[i]["is_correct"]' 조건을 제거합니다.
    # 모든 문제의 피드백을 딕셔너리로 구성 (오답뿐 아니라 정답도 포함)
    # key: "1", "2", ..., "10" (문자열 번호)
    # value: AI가 생성한 피드백 텍스트
    feedbacks = {
        str(i + 1): results[i]["feedback"]
        for i in range(len(results))
        # 이 뒤에 있던 필터링 조건을 삭제하여 모든 번호의 피드백을 포함시킵니다.
    }

    # 최종 채점 결과 반환
    # score: 점수 (0~100)
    # total: 전체 문제 수
    # correct: 정답 개수
    # wrong_numbers: 틀린 문제 번호 목록
    # feedbacks: 문제 번호별 AI 피드백
    return {
        "score": score,
        "total": total,
        "correct": correct_count,
        "wrong_numbers": wrong_numbers,
        "feedbacks": feedbacks,
    }


# ─────────────────────────────────────────────────────────
# 자유학습 채팅 서비스
#
# [역할]
# 학생이 자유롭게 수학 질문을 할 때 사용하는 서비스입니다.
# RAG(Retrieval-Augmented Generation)를 활용하여 더 정확한 답변을 생성합니다.
#
# [RAG란? (Retrieval-Augmented Generation)]
# LLM(AI 모델)이 답변을 생성할 때, 미리 구축된 문서 데이터베이스(벡터 스토어)에서
# 관련 문서를 검색하여 컨텍스트로 제공하는 방식입니다.
# AI가 학습 데이터에 없는 내용도 외부 문서를 참고하여 답변할 수 있게 합니다.
#
# [자유학습 처리 흐름]
# 1. 수학 질문 여부 분류 (classify_math_question)
#    → LLM이 질문이 수학과 관련 있는지 True/False로 판단
# 2. 수학 무관 질문 → 안내 메시지 반환 (AI 불필요 호출 방지)
# 3. 수학 질문 → RAG 검색 + LLM 답변 생성 (ask_question_with_rag_context)
#
# [asyncio.to_thread 사용]
# classify_math_question, ask_question_with_rag_context 모두 동기 함수이므로
# asyncio.to_thread()로 별도 스레드에서 실행합니다.
# ─────────────────────────────────────────────────────────
async def ask_tutor_with_rag(question: str, chat_history: list) -> dict:
    """
    자유학습 채팅 처리 흐름:
    1) 수학 질문인지 분류
    2) 수학이 아니면 → 안내 메시지 반환
    3) 수학이면 → RAG 검색 + LLM 답변 생성

    반환값: {"answer": str, "is_math": bool, "rag_used": bool}
    """
    # 1단계: 수학 관련 질문인지 LLM으로 분류
    # asyncio.to_thread(): classify_math_question이 동기 함수이므로 스레드에서 실행
    # classify_math_question → True (수학 질문) / False (수학 무관 질문)
    is_math = await asyncio.to_thread(classify_math_question, question)

    if not is_math:
        # 수학과 무관한 질문 → 안내 메시지 반환 (LLM 호출 없이 즉시 반환)
        # is_math: False, rag_used: False 로 클라이언트에게 알림
        return {
            "answer": "수학 학습에 대한 질문을 해 주세요 😊",
            "is_math": False,
            "rag_used": False
        }

    # 2단계: RAG 검색 + LLM 답변 생성
    # ask_question_with_rag_context: 동기 함수이므로 asyncio.to_thread로 실행
    # 반환값: (answer_data, rag_used)
    #   answer_data: {"answer": "AI 답변", "tts_text": "음성용 텍스트"}
    #   rag_used: True (RAG 문서 참조) / False (LLM만 사용)
    answer_data, rag_used = await asyncio.to_thread(
        ask_question_with_rag_context, question, chat_history
    )

    return {
        "answer": answer_data.get("answer", "답변 오류"),
        "tts_text": answer_data.get("tts_text", "음성 생성 오류"),
        "is_math": True,
        "rag_used": rag_used
    }
