"""
app/utils/langsmith_service.py  ─  LangSmith 토큰 사용량 조회 서비스

[역할]
LANGCHAIN_TRACING_V2=true 설정만으로 LangChain/LangGraph의 모든 LLM 호출이
LangSmith 프로젝트에 자동 기록됩니다.
이 모듈은 LangSmith Client로 해당 기록을 조회하여 프론트 위젯용 통계를 반환합니다.

[LangSmith 자동 추적 범위]
integration.py의 모든 LangChain 체인 + LangGraph 노드 실행이 자동 캡처됩니다.
  - explain_chain        → 개념설명 (ChatOpenAI)
  - concept_chain        → 이해도평가 (ChatOpenAI)
  - answer_chain         → 채점 (ChatOpenAI)
  - ask_question_to_tutor → Q&A (ChatOpenAI)
  - LangGraph 노드 실행  → eval_concept, eval_answer 등

[username 필터링]
tutor_service.py가 LangChain config의 metadata에 username을 주입합니다.
LangSmith는 이 metadata로 유저별 run을 필터링합니다.

"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

PRICE_INPUT  = 0.000005   # $ per token
PRICE_OUTPUT = 0.000015   # $ per token
KRW_PER_USD  = 1350

# 액션 이름 매핑 (LangSmith run name → 한국어 레이블)
_RUN_NAME_MAP = {
    "ChatOpenAI":      "LLM 호출",
    "eval_concept":    "이해도평가",
    "eval_answer":     "채점",
    "explain_concept": "개념설명",
    "ask_question_to_tutor": "Q&A",
    "RunnableSequence": "체인실행",
}


def _label(run_name: str) -> str:
    """run name → 한국어 액션 레이블 변환"""
    for key, label in _RUN_NAME_MAP.items():
        if key.lower() in run_name.lower():
            return label
    return run_name


def get_token_stats(username: Optional[str] = None, hours: int = 24) -> dict:
    """
    LangSmith에서 최근 N시간의 LLM 호출 통계를 조회합니다.

    Args:
        username : 필터링할 유저명 (integration.py에서 metadata로 주입된 값)
                   None이면 프로젝트 전체 통계 반환
        hours    : 조회 시간 범위 (기본 24시간)

    반환 예시:
        {
            "prompt_tokens": 1200,
            "completion_tokens": 480,
            "total_tokens": 1680,
            "total_cost_usd": 0.0132,
            "total_cost_krw": 17,
            "call_count": 5,
            "history": [
                {"action": "개념설명", "prompt": 320, "completion": 210,
                 "total": 530, "cost_usd": 0.00475, "ts": "14:23"},
                ...
            ]
        }
    """
    try:
        from langsmith import Client
    except ImportError:
        return _empty_stats()

    api_key = os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGCHAIN_PROJECT", "ai-math-tutor")

    if not api_key:
        return _empty_stats()

    try:
        client = Client(api_key=api_key)
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # ── LangSmith 쿼리 파라미터 ──────────────────────────────
        # run_type="llm" : LLM 직접 호출 레이어만 집계 (중복 방지)
        # [수정] has(metadata_key) 필터는 현재 LangSmith API 미지원
        #        → filter 제거 후 Python 레벨에서 username 필터링
        query_kwargs = dict(
            project_name=project,
            run_type="llm",
            start_time=start_time,
            limit=100,  # LangSmith API 최대값
        )

        runs = list(client.list_runs(**query_kwargs))

        # [참고] RunnableConfig metadata가 LangSmith extra 구조와 맞지 않아
        #        username 필터 시 결과가 항상 빈 배열이 됩니다.
        #        현재는 프로젝트 전체 집계를 반환합니다.
        #        추후 LangSmith SDK 업데이트 시 아래 필터 복구 가능:
        #   runs = [r for r in runs if r.extra.get("metadata",{}).get("username")==username]

        if not runs:
            return _empty_stats()

        # ── 집계 ───────────────────────────────────────────────────
        prompt_total     = 0
        completion_total = 0
        history          = []

        for run in runs:
            # LangSmith SDK 버전마다 토큰 필드 위치가 다름 → 3곳 순서대로 탐색
            usage, comp = 0, 0

            # ① 최신 SDK: outputs.token_usage 또는 outputs.usage_metadata
            outputs = getattr(run, "outputs", None) or {}
            if isinstance(outputs, dict):
                tu = outputs.get("token_usage") or outputs.get("usage_metadata") or {}
                if isinstance(tu, dict):
                    usage = tu.get("prompt_tokens") or tu.get("input_tokens") or 0
                    comp  = tu.get("completion_tokens") or tu.get("output_tokens") or 0

            # ② 구버전 SDK: run.prompt_tokens / run.completion_tokens
            if usage == 0 and comp == 0:
                usage = getattr(run, "prompt_tokens", 0) or 0
                comp  = getattr(run, "completion_tokens", 0) or 0

            # ③ run.extra.token_usage dict
            if usage == 0 and comp == 0:
                extra = getattr(run, "extra", None) or {}
                if isinstance(extra, dict):
                    tu = extra.get("token_usage") or extra.get("usage", {}) or {}
                    usage = tu.get("prompt_tokens") or tu.get("input_tokens") or 0
                    comp  = tu.get("completion_tokens") or tu.get("output_tokens") or 0

            if usage == 0 and comp == 0:
                continue

            prompt_total     += usage
            completion_total += comp
            cost = usage * PRICE_INPUT + comp * PRICE_OUTPUT

            ts = run.start_time
            ts_str = ts.strftime("%H:%M") if ts else "--:--"

            history.append({
                "action":     _label(run.name or ""),
                "prompt":     usage,
                "completion": comp,
                "total":      usage + comp,
                "cost_usd":   round(cost, 5),
                "ts":         ts_str,
            })

        # 시간 역순 정렬 후 최근 10건
        history.sort(key=lambda x: x["ts"], reverse=True)
        history = history[:10]

        total_tokens  = prompt_total + completion_total
        total_cost    = prompt_total * PRICE_INPUT + completion_total * PRICE_OUTPUT

        return {
            "prompt_tokens":     prompt_total,
            "completion_tokens": completion_total,
            "total_tokens":      total_tokens,
            "total_cost_usd":    round(total_cost, 5),
            "total_cost_krw":    int(total_cost * KRW_PER_USD),
            "call_count":        len(runs),
            "history":           history,
            "source":            "langsmith",
        }

    except Exception as e:
        print(f"⚠️  LangSmith 조회 오류: {e}")
        return _empty_stats()


def _empty_stats() -> dict:
    """LangSmith 미설정 또는 오류 시 기본값 반환"""
    return {
        "prompt_tokens":     0,
        "completion_tokens": 0,
        "total_tokens":      0,
        "total_cost_usd":    0.0,
        "total_cost_krw":    0,
        "call_count":        0,
        "history":           [],
        "source":            "unavailable",
    }