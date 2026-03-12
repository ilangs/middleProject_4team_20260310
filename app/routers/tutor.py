"""
routers/tutor.py  ─  튜터 기능 API 라우터

[역할]
학생이 수학 튜터 앱을 사용할 때 호출하는 모든 HTTP 엔드포인트를 정의합니다.
프론트엔드(JS)의 apiFetch("/api/...") 호출이 이 파일의 함수들로 연결됩니다.

[계층 구조]
  프론트엔드(JS) → router(이 파일) → service(tutor_service.py) → integration(LangChain/DB)

[토큰 사용량 추적]
LLM을 호출하는 7개 엔드포인트에서 get_openai_callback()을 사용합니다.
  with get_openai_callback() as cb:
      result = await some_llm_function(...)
  # cb.prompt_tokens, cb.completion_tokens, cb.total_cost 로 토큰 정보 조회
  save_token_usage(...)  # 로컬 DB에 저장

[인증 방식]
모든 엔드포인트는 Depends(get_current_user)로 JWT 토큰을 검증합니다.
프론트엔드는 Authorization: Bearer {token} 헤더를 붙여서 요청합니다.
"""

import json, base64, asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

# JWT 토큰 검증 의존성
from app.routers.auth import get_current_user

# DB CRUD 함수들
from app.utils.db_manager import (
    save_history,              # 학습 기록 저장
    get_user_history,          # 학습 기록 조회
    get_incorrect_problems,    # 오답 문제 조회
    save_exam_result,          # 시험 결과 저장
    get_exam_results,          # 시험 결과 조회
    save_chat_message,         # 자유학습 채팅 메시지 저장
    get_chat_history,          # 자유학습 채팅 기록 조회
    save_token_usage,          # LLM 토큰 사용량 저장 ← 핵심!
    get_token_stats_from_db,   # 토큰 통계 조회 (로컬 DB 기반)
)

# LLM 토큰 사용량을 추적하는 콜백 (langchain-community 패키지)
# with get_openai_callback() as cb: 블록 안에서 호출된 모든 OpenAI API의
# 토큰 수와 비용을 자동으로 집계합니다.
from langchain_community.callbacks import get_openai_callback

# 서비스 계층 함수들 (실제 LLM 호출 및 비즈니스 로직)
from app.services.tutor_service import (
    fetch_units,
    fetch_problem,
    get_explanation     as svc_get_explanation,
    get_reexplanation,
    evaluate_explanation as svc_evaluate_explanation,
    ask_tutor           as svc_ask_tutor,
    grade_answer        as svc_grade_answer,
    get_problem_image_b64,
    generate_exam_questions,
    grade_exam_answers,
    ask_tutor_with_rag,        # 자유학습: RAG+LLM 채팅
)

router = APIRouter()


# ──────────────────────────────────────────────
# Pydantic 요청 모델 정의
# ──────────────────────────────────────────────
# [Pydantic이란?]
# FastAPI가 요청 body의 타입과 구조를 자동으로 검증해 주는 라이브러리.
# BaseModel을 상속하면 자동으로 유효성 검사 + Swagger 문서 생성.

class ExplainRequest(BaseModel):
    """개념 설명 요청: 단원명만 받음"""
    unit_name: str

class StudentExplainRequest(BaseModel):
    """학생 이해도 평가 요청: 단원명 + 학생이 말로 설명한 내용"""
    concept: str
    student_explanation: str

class AskRequest(BaseModel):
    """Q&A 질문 요청: 질문 + 이전 대화 기록 (컨텍스트)"""
    question: str
    chat_history: list = []

class EvaluateRequest(BaseModel):
    """문제 채점 요청: 문제 정보 dict + 학생 답변"""
    problem: dict
    student_answer: str

class SaveHistoryRequest(BaseModel):
    """학습 기록 저장 요청: 문제 ID, 단원, 정오답"""
    problem_id: str
    unit: str
    is_correct: bool

class ExamGenerateRequest(BaseModel):
    """시험 생성 요청: 단원명"""
    unit_name: str

class ExamSubmitRequest(BaseModel):
    """시험 제출 요청: 단원 + 문제 목록 + 학생 답변 목록"""
    unit: str
    problems: list
    answers: list

class ExamSaveRequest(BaseModel):
    """시험 결과 저장 요청: 점수, 오답 번호, 피드백"""
    unit: str
    score: int
    total_questions: int
    wrong_numbers: list
    feedbacks: dict

class TTSRequest(BaseModel):
    """TTS 요청: 음성으로 변환할 텍스트"""
    text: str

class TTSResponse(BaseModel):
    """TTS 응답: base64로 인코딩된 MP3 오디오"""
    audio_b64: str

class FreeChatRequest(BaseModel):
    """자유학습 채팅 요청: 학생 질문 + 이전 대화 기록"""
    question: str           # 학생이 입력한 질문
    chat_history: list = [] # 이전 대화 기록 (컨텍스트 유지용)


# ──────────────────────────────────────────────
# 단원 목록 조회
# ──────────────────────────────────────────────

@router.get("/units")
async def get_unit_list(current_user: dict = Depends(get_current_user)):
    """
    수학 튜터 데이터셋에서 단원 목록을 반환합니다. (LLM 미사용)
    CSV 파일에서 고유 단원명을 추출합니다.

    [호출 시점] section1.js - 페이지 로드 시 단원 선택 드롭다운 채우기
    """
    try:
        units = await fetch_units()
        return {"units": units}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 문제 조회
# ──────────────────────────────────────────────

@router.get("/problem")
async def get_problem(unit: str, current_user: dict = Depends(get_current_user)):
    """
    선택한 단원에서 무작위로 문제 1개를 반환합니다. (LLM 미사용)
    문제에 이미지가 있으면 base64로 인코딩하여 함께 반환합니다.

    [호출 시점] section1.js - 단원 선택 후 문제 표시
    """
    problem = await fetch_problem(unit)

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{unit} 문제 없음"
        )

    # NaN 값을 None으로 변환 (JSON 직렬화 오류 방지)
    cleaned    = {k: (None if str(v) == "nan" else v) for k, v in problem.items()}
    image_b64  = get_problem_image_b64(str(cleaned.get("ID", "")))

    return {
        "problem":   cleaned,
        "image_b64": image_b64
    }


# ──────────────────────────────────────────────
# 개념 설명 (LLM 호출 ①)
# ──────────────────────────────────────────────

@router.post("/explain")
async def get_explanation(
    body: ExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    선택한 단원에 대한 AI 개념 설명을 생성합니다.

    [LLM 사용] explain_chain (integration.py)
    [토큰 추적] get_openai_callback()으로 토큰 수 측정 후 DB 저장

    [호출 시점] section1.js - 단원 선택 직후 루미 선생님 설명 표시
    """
    try:
        with get_openai_callback() as cb:
            # LLM 호출 → 개념 설명 텍스트 반환
            explanation = await svc_get_explanation(body.unit_name)

        # 토큰 사용량을 로컬 DB(token_logs)에 저장
        save_token_usage(
            username=current_user["username"],
            action="개념설명",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return {"explanation": explanation}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 보충 설명 (LLM 호출 ②)
# ──────────────────────────────────────────────

@router.post("/reexplain")
async def get_supplementary_explanation(
    body: ExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    처음 설명을 이해하지 못한 학생을 위한 더 쉬운 보충 설명을 생성합니다.

    [LLM 사용] reexplain_chain (integration.py)
    [호출 시점] section1.js - "다시 설명해줘" 버튼 클릭 시
    """
    try:
        with get_openai_callback() as cb:
            explanation = await get_reexplanation(body.unit_name)

        save_token_usage(
            username=current_user["username"],
            action="추가설명",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return {"explanation": explanation}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 이해도 평가 (LLM 호출 ③)
# ──────────────────────────────────────────────

@router.post("/explain/evaluate")
async def evaluate_student_explanation(
    body: StudentExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    학생이 개념을 자신의 말로 설명한 내용을 AI가 평가합니다.
    [PASS] / [FAIL] 판정 + 격려 피드백을 반환합니다.

    [LLM 사용] concept_chain (integration.py)
    [호출 시점] section1.js - 학생이 개념 설명 입력 후 제출 시
    """
    try:
        with get_openai_callback() as cb:
            result = await svc_evaluate_explanation(
                body.concept,
                body.student_explanation
            )

        save_token_usage(
            username=current_user["username"],
            action="이해도평가",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Q&A 질문 (LLM 호출 ④)
# ──────────────────────────────────────────────

@router.post("/ask")
async def ask_tutor(
    body: AskRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    오늘의 학습 중 학생이 궁금한 점을 루미 선생님에게 질문합니다.
    chat_history를 넘겨 대화 맥락(컨텍스트)을 유지합니다.

    [LLM 사용] llm.invoke() 직접 호출 (integration.py)
    [호출 시점] section1.js - 학습 중 "선생님께 질문" 버튼 클릭 시
    """
    try:
        with get_openai_callback() as cb:
            answer = await svc_ask_tutor(body.question, body.chat_history)

        save_token_usage(
            username=current_user["username"],
            action="Q&A",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return {"answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 문제 채점 (LLM 호출 ⑤)
# ──────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate_student_answer(
    body: EvaluateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    학생의 문제 답변을 AI가 채점하고 [정답]/[오답] + 피드백을 반환합니다.

    [LLM 사용] answer_chain (integration.py)
    [호출 시점] section1.js - 학생이 답변 입력 후 제출 시
    """
    try:
        with get_openai_callback() as cb:
            result = await svc_grade_answer(body.problem, body.student_answer)

        save_token_usage(
            username=current_user["username"],
            action="채점",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 학습 기록 저장
# ──────────────────────────────────────────────

@router.post("/history")
async def record_history(
    body: SaveHistoryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    문제 풀이 결과(정오답)를 DB에 저장합니다. (LLM 미사용)
    section4.js 성적 대시보드의 데이터 소스가 됩니다.

    [호출 시점] section1.js - 채점 완료 후 "다음 문제" 버튼 클릭 시
    """
    try:
        save_history(
            username=current_user["username"],
            problem_id=body.problem_id,
            unit=body.unit,
            is_correct=body.is_correct
        )
        return {"message": "학습 기록 저장 완료"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 학습 기록 조회
# ──────────────────────────────────────────────

@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    """
    학생의 전체 학습 기록과 정답률을 반환합니다. (LLM 미사용)

    [호출 시점] section4.js - 성적 대시보드 페이지 로드 시
    """
    try:
        df = get_user_history(current_user["username"])

        if df.empty:
            return {"history": [], "correct_rate": 0.0}

        # 정답률 계산: is_correct 컬럼의 평균값 (0~1) × 100
        correct_rate = round(df["is_correct"].mean() * 100, 1)

        return {
            "history":      df.to_dict(orient="records"),
            "correct_rate": correct_rate
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 오답 문제 조회
# ──────────────────────────────────────────────

@router.get("/history/incorrect")
async def get_incorrect(current_user: dict = Depends(get_current_user)):
    """
    한 번도 정답을 맞히지 못한 문제 목록을 반환합니다. (LLM 미사용)
    오답노트 기능에 사용됩니다.

    [호출 시점] section4.js - 오답 문제 목록 표시 시
    """
    try:
        problems = get_incorrect_problems(current_user["username"])
        return {"incorrect_problems": problems}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 시험 문제 생성
# ──────────────────────────────────────────────

@router.post("/exam/generate")
async def exam_generate(
    body: ExamGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    선택한 단원에서 시험 문제 10개를 무작위 추출하여 반환합니다. (LLM 미사용)
    CSV 데이터셋에서 직접 조회하므로 빠르고 정확합니다.

    [호출 시점] section3.js - 단원 선택 후 "시험 시작" 클릭 시
    """
    try:
        problems = await generate_exam_questions(body.unit_name)

        if not problems:
            raise HTTPException(status_code=404, detail="시험 문제 없음")

        return {
            "problems": problems,
            "count":    len(problems)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 시험 일괄 채점 (LLM 호출 ⑥)
# ──────────────────────────────────────────────

@router.post("/exam/submit")
async def exam_submit(
    body: ExamSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    시험 전체 답안을 일괄 채점합니다.
    문제 수만큼 LLM을 병렬로 호출하므로 토큰 사용량이 많습니다.

    [LLM 사용] answer_chain × 문제 수 (asyncio.gather 병렬 처리)
    [호출 시점] section3.js - 시험 "제출" 버튼 클릭 시
    """
    try:
        with get_openai_callback() as cb:
            result = await grade_exam_answers(body.problems, body.answers)

        save_token_usage(
            username=current_user["username"],
            action="시험채점",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 시험 결과 저장
# ──────────────────────────────────────────────

@router.post("/exam/save-result")
async def exam_save_result(
    body: ExamSaveRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    시험 점수와 AI 피드백을 DB에 저장합니다. (LLM 미사용)
    section4.js 성적 이력의 데이터 소스가 됩니다.

    [호출 시점] section3.js - 시험 결과 확인 후 "저장" 처리 시
    """
    try:
        save_exam_result(
            username=current_user["username"],
            unit=body.unit,
            score=body.score,
            total_questions=body.total_questions,
            # 리스트를 JSON 문자열로 직렬화: [2, 4] → "[2, 4]"
            wrong_numbers=json.dumps(body.wrong_numbers, ensure_ascii=False),
            feedback=json.dumps(body.feedbacks, ensure_ascii=False)
        )
        return {"message": "시험 결과 저장 완료"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 시험 결과 목록 조회
# ──────────────────────────────────────────────

@router.get("/exam/results")
async def exam_results(current_user: dict = Depends(get_current_user)):
    """
    학생의 모든 시험 이력을 반환합니다. (LLM 미사용)

    [호출 시점] section4.js - 성적 대시보드의 시험 이력 탭 로드 시
    """
    try:
        results = get_exam_results(current_user["username"])
        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# TTS (음성 합성)
# ──────────────────────────────────────────────

@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    body: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    텍스트를 OpenAI TTS(tts-1, nova 목소리)로 음성 변환하여 base64 MP3로 반환합니다.
    동일 텍스트는 MD5 해시로 캐싱하여 API 비용을 절감합니다.

    [호출 시점] section1.js, section2.js - "음성 듣기" 버튼 클릭 시
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="텍스트 없음")

    try:
        from app.tutor.integration import generate_speech_with_cache

        # 동기 함수를 비동기로 실행 (서버 블로킹 방지)
        audio_bytes = await asyncio.to_thread(
            generate_speech_with_cache,
            body.text
        )

        if audio_bytes is None:
            raise HTTPException(status_code=500, detail="음성 생성 실패")

        return {"audio_b64": base64.b64encode(audio_bytes).decode()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 자유학습 채팅 (LLM 호출 ⑦)
# ──────────────────────────────────────────────

@router.post("/free/chat")
async def free_chat(
    body: FreeChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    자유학습 채팅 엔드포인트. RAG + LLM을 결합하여 맞춤형 답변을 생성합니다.

    [처리 흐름]
    1. 학생 질문 → DB 저장 (chat_history)
    2. LLM으로 수학 질문인지 분류 (classify_math_question)
    3. 수학 질문이면 → ChromaDB RAG 검색 → LLM 답변 생성
    4. AI 응답 → DB 저장 (chat_history)
    5. 토큰 사용량 → DB 저장 (token_logs)

    [LLM 사용]
    - 수학 분류기: 1회 호출
    - RAG 기반 답변: 1회 호출
    합계 최대 2회 호출 → 토큰 사용량이 다른 기능보다 많을 수 있음

    [호출 시점] section2.js - 채팅창에서 질문 전송 시
    """
    username = current_user["username"]
    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    try:
        # 학생 메시지를 먼저 DB에 저장
        save_chat_message(username, "user", question)

        # RAG + LLM 답변 생성 (수학 필터링 + 벡터 검색 포함)
        with get_openai_callback() as cb:
            result = await ask_tutor_with_rag(question, body.chat_history)

        # AI 응답을 DB에 저장
        save_chat_message(username, "assistant", result["answer"])

        # 토큰 사용량 DB 저장
        save_token_usage(
            username=username,
            action="AI자유학습",
            prompt=cb.prompt_tokens,
            completion=cb.completion_tokens,
            total=cb.total_tokens,
            cost=cb.total_cost,
        )

        return {
            "answer":   result["answer"],
            "tts_text": result.get("tts_text", result["answer"]),
            "is_math":  result["is_math"],
            "rag_used": result["rag_used"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 자유학습 채팅 기록 조회
# ──────────────────────────────────────────────

@router.get("/free/history")
async def free_chat_history(current_user: dict = Depends(get_current_user)):
    """
    학생의 자유학습 채팅 기록을 최근 50건 반환합니다. (LLM 미사용)

    [호출 시점] section2.js - 자유학습 탭 진입 시 이전 대화 복원
    """
    try:
        history = get_chat_history(current_user["username"])
        return {"history": history}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 토큰 사용량 통계 조회
# ──────────────────────────────────────────────

@router.get("/token/logs")
async def get_token_logs(current_user: dict = Depends(get_current_user)):
    """
    로컬 DB(token_logs 테이블)에서 사용자의 토큰 사용 통계를 반환합니다.

    [변경 이력]
    기존: LangSmith API에서 조회 → 할당량 초과 시 항상 0 반환
    변경: 로컬 SQLite DB에서 직접 조회 → 항상 정확한 데이터 반환

    [호출 시점] section5.js - 토큰 로그 탭 진입 시
    """
    try:
        stats = get_token_stats_from_db(username=current_user["username"])
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
