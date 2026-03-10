"""
routers/tutor.py  ─  튜터 기능 API 라우터
"""

import json
import base64
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.routers.auth import get_current_user
from app.utils.db_manager import (
    save_history,
    get_user_history,
    get_incorrect_problems,
    save_exam_result,
    get_exam_results,
    save_chat_message,       # 자유학습 채팅 메시지 저장
    get_chat_history,        # 자유학습 채팅 기록 조회
)

from app.utils.langsmith_service import get_token_stats

from app.services.tutor_service import (
    fetch_units,
    fetch_problem,
    get_explanation as svc_get_explanation,
    get_reexplanation, # ⭐ 추가
    evaluate_explanation as svc_evaluate_explanation,
    ask_tutor as svc_ask_tutor,
    grade_answer as svc_grade_answer,
    get_problem_image_b64,
    generate_exam_questions,
    grade_exam_answers,
    ask_tutor_with_rag,      # 자유학습: RAG+LLM 채팅
)

router = APIRouter()


class ExplainRequest(BaseModel):
    unit_name: str


class StudentExplainRequest(BaseModel):
    concept: str
    student_explanation: str


class AskRequest(BaseModel):
    question: str
    chat_history: list = []


class EvaluateRequest(BaseModel):
    problem: dict
    student_answer: str


class SaveHistoryRequest(BaseModel):
    problem_id: str
    unit: str
    is_correct: bool


class ExamGenerateRequest(BaseModel):
    unit_name: str


class ExamSubmitRequest(BaseModel):
    unit: str
    problems: list
    answers: list


class ExamSaveRequest(BaseModel):
    unit: str
    score: int
    total_questions: int
    wrong_numbers: list
    feedbacks: dict


class TTSRequest(BaseModel):
    text: str


class FreeChatRequest(BaseModel):
    """자유학습 채팅 요청 모델"""
    question: str              # 학생이 입력한 질문
    chat_history: list = []    # 이전 대화 기록 (컨텍스트 유지용)


@router.get("/units")
async def get_unit_list(current_user: dict = Depends(get_current_user)):
    try:
        units = await fetch_units()
        return {"units": units}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/problem")
async def get_problem(unit: str, current_user: dict = Depends(get_current_user)):
    problem = await fetch_problem(unit)

    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{unit} 문제 없음"
        )

    cleaned = {k: (None if str(v) == "nan" else v) for k, v in problem.items()}
    image_b64 = get_problem_image_b64(str(cleaned.get("ID", "")))

    return {
        "problem": cleaned,
        "image_b64": image_b64
    }


@router.post("/explain")
async def get_explanation(
    body: ExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        explanation = await svc_get_explanation(body.unit_name)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reexplain")
async def get_supplementary_explanation(
    body: ExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        explanation = await get_reexplanation(body.unit_name)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/explain/evaluate")
async def evaluate_student_explanation(
    body: StudentExplainRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await svc_evaluate_explanation(
            body.concept,
            body.student_explanation
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
async def ask_tutor(
    body: AskRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        answer = await svc_ask_tutor(body.question, body.chat_history)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_student_answer(
    body: EvaluateRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await svc_grade_answer(body.problem, body.student_answer)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history")
async def record_history(
    body: SaveHistoryRequest,
    current_user: dict = Depends(get_current_user)
):
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


@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    try:
        df = get_user_history(current_user["username"])

        if df.empty:
            return {
                "history": [],
                "correct_rate": 0.0
            }

        correct_rate = round(df["is_correct"].mean() * 100, 1)

        return {
            "history": df.to_dict(orient="records"),
            "correct_rate": correct_rate
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/incorrect")
async def get_incorrect(current_user: dict = Depends(get_current_user)):
    try:
        problems = get_incorrect_problems(current_user["username"])
        return {"incorrect_problems": problems}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exam/generate")
async def exam_generate(
    body: ExamGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        problems = await generate_exam_questions(body.unit_name)

        if not problems:
            raise HTTPException(
                status_code=404,
                detail="시험 문제 없음"
            )

        return {
            "problems": problems,
            "count": len(problems)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exam/submit")
async def exam_submit(
    body: ExamSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await grade_exam_answers(body.problems, body.answers)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exam/save-result")
async def exam_save_result(
    body: ExamSaveRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        save_exam_result(
            username=current_user["username"],
            unit=body.unit,
            score=body.score,
            total_questions=body.total_questions,
            wrong_numbers=json.dumps(body.wrong_numbers, ensure_ascii=False),
            feedback=json.dumps(body.feedbacks, ensure_ascii=False)
        )

        return {"message": "시험 결과 저장 완료"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exam/results")
async def exam_results(current_user: dict = Depends(get_current_user)):
    try:
        results = get_exam_results(current_user["username"])
        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(
    body: TTSRequest,
    current_user: dict = Depends(get_current_user)
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="텍스트 없음")

    try:
        from app.tutor.integration import generate_speech_with_cache

        audio_bytes = await asyncio.to_thread(
            generate_speech_with_cache,
            body.text
        )

        if audio_bytes is None:
            raise HTTPException(status_code=500, detail="음성 생성 실패")

        return {
            "audio_b64": base64.b64encode(audio_bytes).decode()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────
# 자유학습 채팅 엔드포인트
# ─────────────────────────────────────────────────────────

@router.post("/free/chat")
async def free_chat(
    body: FreeChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    자유학습 채팅 엔드포인트

    흐름:
    1. 학생 메시지를 DB에 저장
    2. 수학 질문 분류 → RAG 검색 → LLM 답변 생성
    3. AI 응답을 DB에 저장
    4. 결과 반환
    """
    username = current_user["username"]
    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    try:
        # 학생 메시지 DB 저장
        save_chat_message(username, "user", question)

        # RAG + LLM 답변 생성 (수학 필터링 포함)
        result = await ask_tutor_with_rag(question, body.chat_history)

        # AI 응답 DB 저장
        save_chat_message(username, "assistant", result["answer"])

        return {
            "answer": result["answer"],
            "tts_text": result.get("tts_text", result["answer"]),
            "is_math": result["is_math"],
            "rag_used": result["rag_used"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/free/history")
async def free_chat_history(
    current_user: dict = Depends(get_current_user)
):
    """학생의 자유학습 채팅 기록을 반환합니다 (최근 50건)."""
    try:
        history = get_chat_history(current_user["username"])
        return {"history": history}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/logs")
async def get_token_logs(current_user: dict = Depends(get_current_user)):
    try:
        stats = get_token_stats(username=current_user["username"])
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))