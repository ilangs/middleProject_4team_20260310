"""
================================================================================
파일명: integration.py
위치  : app/tutor/integration.py
================================================================================

【이 파일의 역할】
이 파일은 초등학교 수학 AI 튜터 시스템의 '두뇌' 역할을 합니다.
LangChain, LangGraph, OpenAI TTS, RAG(검색 기반 답변 생성) 기술을 하나로
통합하여, 서버(server.py) → 라우터(app/routers/tutor.py) →
서비스(app/services/tutor_service.py) 계층에서 호출할 수 있는
핵심 함수들을 모두 이 파일에서 정의합니다.

【이 파일이 제공하는 기능 목록】
  1. TTS(음성합성) 캐싱          : generate_speech_with_cache()
  2. LangChain Tool              : get_units(), get_problem_by_unit()
  3. 시험 문제 추출               : get_exam_problems()
  4. LangChain 체인               : explain_chain, reexplain_chain,
                                    concept_chain, answer_chain
  5. Q&A 챗봇                    : ask_question_to_tutor()
  6. LangGraph 상태(State) 정의   : TutorState
  7. LangGraph 노드 함수          : fetch_units_node, fetch_problem_node,
                                    evaluate_concept_node, evaluate_answer_node
  8. LangGraph 라우터             : entry_router()
  9. LangGraph 그래프 컴파일       : tutor_app
 10. Wrapper 함수                 : evaluate_concept_understanding(),
                                    evaluate_answer()
 11. 수학 질문 분류               : classify_math_question()
 12. RAG 연동 답변 생성           : ask_question_with_rag_context()

【3주차 학습 포인트 - AI Agent 개발 핵심 개념】
  ★ LangChain 체인(Chain)
      프롬프트 → LLM → 출력 파서를 파이프(|)로 연결한 처리 흐름.
      한 번 정의하면 .invoke()로 언제든 재사용할 수 있습니다.

  ★ LangGraph StateGraph
      AI 워크플로우를 "노드(처리 단계)"와 "엣지(연결 경로)"로 표현하는
      그래프 구조. 상태(State)를 공유하며 여러 노드가 순서대로 또는
      조건에 따라 실행됩니다.

  ★ RAG (Retrieval-Augmented Generation)
      LLM이 답변할 때 ChromaDB(벡터 데이터베이스)에서 관련 문서를 먼저
      검색(Retrieve)하여 참고자료로 제공한 뒤 답변(Generate)하는 방식.
      LLM의 "환각(hallucination)" 문제를 줄이고 정확도를 높입니다.

  ★ asyncio.to_thread()
      이 파일의 함수들은 모두 동기(sync) 함수입니다.
      FastAPI 서버는 비동기(async)로 동작하므로, 동기 함수를 그대로 호출하면
      서버 전체가 멈춥니다. asyncio.to_thread()는 동기 함수를 별도의
      스레드에서 실행하여 서버가 멈추지 않도록 보호합니다.
      (실제 사용: app/services/tutor_service.py에서 호출)

  ★ TTS 캐싱
      동일한 텍스트를 반복 변환하면 OpenAI API 비용이 낭비됩니다.
      텍스트의 MD5 해시를 파일명으로 삼아 임시 폴더에 저장해 두고,
      같은 텍스트가 다시 요청되면 저장된 파일을 바로 반환합니다.
================================================================================
"""

import os, json, hashlib, tempfile
import pandas as pd
from typing import TypedDict, Optional, Dict, Any, Annotated
from dotenv import load_dotenv

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# CSV 데이터셋 경로: 단원명, 문제, 풀이, 정답 컬럼을 포함합니다.
DATA_PATH = 'data/processed/math_tutor_dataset.csv'

# .env 파일에서 OPENAI_API_KEY 등의 환경변수를 로드합니다.
load_dotenv()

# OpenAI 공식 클라이언트 - TTS(음성합성) API 호출에 사용합니다.
client = OpenAI()

# LangChain용 ChatOpenAI 래퍼 - 모든 LangChain 체인과 LangGraph 노드에서 사용합니다.
# temperature=0.7: 0에 가까울수록 일관된 답변, 1에 가까울수록 창의적인 답변이 나옵니다.
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)


# ==========================================
# 1. 일반 함수 및 Tools
# ==========================================

def generate_speech_with_cache(text: str) -> bytes:
    """
    【TTS 캐싱 함수】
    텍스트를 음성(MP3)으로 변환하되, 이미 변환한 적 있으면 캐시에서 즉시 반환합니다.

    【TTS 캐싱이란?】
    - 같은 문장을 매번 OpenAI API에 요청하면 비용이 계속 발생합니다.
    - 텍스트의 MD5 해시값을 파일명으로 사용하여 OS 임시 폴더에 저장해 둡니다.
    - 같은 텍스트가 다시 요청되면 API 호출 없이 저장된 파일을 그대로 반환합니다.
    - 결과: OpenAI 비용 절감 + 응답 속도 향상의 두 가지 이점을 얻습니다.

    【OS 임시 폴더를 사용하는 이유】
    - 프로젝트 폴더(assets/audio 등)에 저장하면 VS Code Live Server가 파일 변경을
      감지하고 브라우저를 강제 새로고침하여 학습 중인 화면이 초기화됩니다.
    - tempfile.gettempdir()는 OS가 관리하는 임시 폴더(예: C:/Users/.../AppData/Local/Temp)를
      반환하므로 Live Server의 감시 대상에서 벗어납니다.

    매개변수:
        text (str): 음성으로 변환할 한글 텍스트

    반환값:
        bytes: MP3 오디오 데이터 (실패 시 None)

    호출 위치:
        app/routers/tutor.py → /api/tts 엔드포인트에서
        asyncio.to_thread(generate_speech_with_cache, tts_text)로 호출됩니다.
    """
    # 텍스트를 MD5 해시로 변환하여 고유한 파일명으로 사용합니다.
    # 같은 텍스트는 항상 같은 해시값을 생성하므로 캐시 키 역할을 합니다.
    text_hash = hashlib.md5(text.encode()).hexdigest()

    # ⭐ 핵심 변경: 프로젝트 폴더(assets/audio) 대신, Live Server가 감시하지 못하는 'OS 임시 폴더'를 사용합니다!
    audio_dir = os.path.join(tempfile.gettempdir(), "ai_math_tutor_audio")

    # 임시 폴더가 없으면 새로 생성합니다.
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    # 캐시 파일 경로: 해시값.mp3 형태로 저장됩니다.
    file_path = os.path.join(audio_dir, f"{text_hash}.mp3")

    # 이미 생성된 음성이 임시 폴더에 있다면 바로 읽어옵니다. (OpenAI 비용 절감 & 속도 향상)
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()

    # 캐시에 없으면 OpenAI TTS API를 호출하여 새로 생성합니다.
    try:
        response = client.audio.speech.create(
            model="tts-1",      # OpenAI의 TTS 모델
            voice="nova",       # 'nova' 목소리: 밝고 친근한 여성 목소리
            input=text          # 음성으로 변환할 텍스트
        )

        # Live Server가 모르는 안전한 임시 폴더에 파일 저장
        response.write_to_file(file_path)

        # 저장된 파일을 바이트로 읽어서 반환합니다.
        with open(file_path, "rb") as f:
            return f.read()

    except Exception as e:
        print(f"❌ 음성 생성 오류: {e}")
        return None


# ──────────────────────────────────────────
# LangChain @tool 데코레이터란?
# @tool을 붙이면 일반 함수가 LangChain이 인식할 수 있는 "도구(Tool)"가 됩니다.
# LangGraph 노드 안에서 tool.invoke({인자})로 호출할 수 있습니다.
# 함수의 docstring이 LLM에게 "이 도구가 어떤 일을 하는지" 설명하는 역할을 합니다.
# ──────────────────────────────────────────

@tool
def get_units() -> list:
    """수학 튜터 데이터셋에 있는 전체 단원 목록을 반환합니다."""
    # CSV 파일을 읽어 '단원' 컬럼의 고유값(unique)을 정렬하여 반환합니다.
    df = pd.read_csv(DATA_PATH)
    return sorted(df['단원'].unique().tolist())


@tool
def get_problem_by_unit(unit_name: str) -> dict:
    """선택한 단원에서 문제 하나를 무작위로 반환합니다."""
    # 전체 데이터에서 선택한 단원의 행만 필터링합니다.
    df = pd.read_csv(DATA_PATH)
    unit_df = df[df['단원'] == unit_name]

    # 해당 단원에 문제가 있으면 1개를 무작위로 골라 딕셔너리로 반환합니다.
    if not unit_df.empty:
        return unit_df.sample(n=1).iloc[0].to_dict()

    # 해당 단원이 없으면 None을 반환합니다.
    return None


# ⭐ 시험용 문제 추출

def get_exam_problems(unit_name: str, n: int =3) -> list:
    """
    【시험 문제 추출 함수】
    선택한 단원에서 시험용 문제를 n개 추출합니다.

    【@tool 없이 일반 함수인 이유】
    get_units, get_problem_by_unit은 LangGraph 노드 안에서 도구로 호출되지만,
    get_exam_problems는 서비스 계층(tutor_service.py)에서 직접 호출되므로
    @tool 데코레이터가 필요 없습니다.

    매개변수:
        unit_name (str): 단원 이름 (예: "분수의 덧셈과 뺄셈")
        n (int)        : 추출할 문제 수 (기본값 3)

    반환값:
        list[dict]: 문제 딕셔너리의 리스트. NaN 값은 None으로 변환됩니다.

    호출 위치:
        app/services/tutor_service.py → get_exam_problems_service()에서 호출됩니다.
    """
    df = pd.read_csv(DATA_PATH)
    unit_df = df[df['단원'] == unit_name]

    # 해당 단원의 문제가 없으면 빈 리스트를 반환합니다.
    if unit_df.empty:
        return []

    # 요청한 n개보다 실제 문제 수(len(unit_df))가 적을 수 있으므로 min()으로 안전하게 처리합니다.
    k = min(n, len(unit_df))

    # k개를 무작위로 추출하고 딕셔너리 리스트로 변환합니다.
    problems = unit_df.sample(n=k).to_dict("records")

    # pandas가 빈 셀을 float("nan")으로 처리하는데, JSON 직렬화 시 오류가 납니다.
    # "nan" 문자열을 None으로 바꿔서 안전하게 반환합니다.
    return [
        {key: (None if str(val) == "nan" else val) for key, val in p.items()}
        for p in problems
    ]

# ==========================================
# 2. LangChain 체인
# ==========================================
#
# 【LangChain 체인(Chain)이란?】
# 체인은 "프롬프트 템플릿 → LLM → 출력 파서"를 파이프(|) 기호로 연결한 것입니다.
#
#   ChatPromptTemplate  : 변수({unit_name} 등)를 포함한 프롬프트 틀을 정의합니다.
#   llm                 : ChatOpenAI 인스턴스 (GPT-4o). 실제 AI 추론을 담당합니다.
#   StrOutputParser()   : LLM의 응답 객체(AIMessage)에서 텍스트(str)만 꺼냅니다.
#
# 사용 예시:
#   explain_chain.invoke({"unit_name": "분수"})
#   → 프롬프트에 "분수"를 채워 GPT-4o에 보내고, 결과 문자열을 반환합니다.
#
# 체인을 사용하면 같은 처리 흐름을 여러 번 재사용할 수 있어 코드가 간결해집니다.
# ==========================================

# ── explain_chain: 단원 개념 첫 설명 생성 ──
# 학생이 단원을 처음 선택했을 때 루미 선생님이 개념을 설명하는 체인입니다.
explain_prompt = ChatPromptTemplate.from_messages([
    ("system", """너는 수학 선생님인 토끼 캐릭터 '루미'야. 초등학교 학생들에게 아주 친절하고 상냥하게 말해줘.
    학생이 선택한 '{unit_name}' 단원에 대해 아주 쉽고 재미있는 비유를 들어서 한글로 설명해줘.

    [가이드라인]
    1. "안녕! 나는 루미 선생님이야!"처럼 친근하게 시작할 것.
    2. 초등학생이 이해하기 쉬운 비유를 하나 들어줄 것.
    3. 설명 마지막에는 "이해가 잘 되었니? 이제 문제를 하나 풀어볼까?"라고 물어봐줘.""")
])

# 파이프(|) 연산자로 프롬프트 → LLM → 문자열 파서를 연결합니다.
# 이것이 LangChain의 핵심 문법인 LCEL(LangChain Expression Language)입니다.
explain_chain = explain_prompt | llm | StrOutputParser()

def explain_concept(unit_name: str) -> str:
    """
    【개념 첫 설명 함수】
    explain_chain을 호출하여 선택한 단원의 개념 설명 텍스트를 생성합니다.

    매개변수:
        unit_name (str): 설명할 단원 이름 (예: "곱셈")

    반환값:
        str: 루미 선생님 스타일의 개념 설명 텍스트

    호출 위치:
        app/services/tutor_service.py → explain_concept_service()에서 호출됩니다.
        (참고: 해당 서비스 함수는 asyncio.to_thread()로 이 동기 함수를 감쌉니다.)
    """
    return explain_chain.invoke({"unit_name": unit_name})

# ── reexplain_chain: 단원 개념 재설명 생성 ──
# 학생이 첫 설명을 이해하지 못했을 때 더 쉬운 예시로 재설명하는 체인입니다.
# explain_chain과 구조는 동일하지만 시스템 프롬프트(지시사항)가 다릅니다.
reexplain_prompt = ChatPromptTemplate.from_messages([
    ("system", """너는 초등학생 수학 선생님인 토끼 캐릭터 '루미'야.
    학생이 '{unit_name}' 단원의 개념을 한 번 들었는데 잘 이해하지 못했어.
    처음 설명보다 훨씬 더 쉽고, 피자 나누기나 사탕 나누기 같은 일상생활의 재미있고 친숙한 예시를 들어서 아주 친절하게 한글로 다시 설명해줘. 수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해줘.
    """)
])

reexplain_chain = reexplain_prompt | llm | StrOutputParser()

def reexplain_concept(unit_name: str) -> str:
    """이해가 부족한 학생을 위한 더 쉬운 보충 설명 생성

    【재설명 함수】
    학생이 "잘 모르겠어요"를 선택했을 때 호출됩니다.
    explain_concept()과 달리 일상생활 비유(피자, 사탕 등)를 강조하는 프롬프트를 사용합니다.

    매개변수:
        unit_name (str): 재설명할 단원 이름

    반환값:
        str: 더 쉬운 예시를 포함한 보충 설명 텍스트

    호출 위치:
        app/services/tutor_service.py → reexplain_concept_service()에서
        asyncio.to_thread(reexplain_concept, unit_name)로 호출됩니다.
    """
    return reexplain_chain.invoke({"unit_name": unit_name})

# ── concept_chain: 학생의 개념 이해도 평가 ──
# 학생이 자신의 말로 개념을 설명했을 때, 그 이해도를 채점하는 체인입니다.
# 답변 마지막에 [PASS] 또는 [FAIL]을 포함시켜 서비스 계층에서 파싱할 수 있게 합니다.
concept_eval_prompt = ChatPromptTemplate.from_messages([
    ("system",  """당신은 초등학교 수학 선생님입니다. 학생이 '{concept}'에 대해 설명한 내용을 듣고 한글로 평가해주세요.

    [평가 규칙]
    1. 핵심 원리가 포함되었는지 확인합니다.
    2. 이해도가 충분하면 답변 마지막에 반드시 [PASS]라고 적어주세요.
    3. 설명이 부족하거나 틀렸다면 친절하게 교정해주고, 답변 마지막에 반드시 [FAIL]이라고 적어주세요.
    4. 모든 피드백은 따뜻하고 격려하는 말투로 작성하세요.
    5. 수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해줘.
    """),
    ("user", "{student_explanation}")   # 학생이 입력한 설명 텍스트가 들어갑니다.
])

# concept_chain: 개념 이해도 평가 체인
# 사용 위치: evaluate_concept_node() 안에서 직접 호출됩니다.
concept_chain = concept_eval_prompt | llm | StrOutputParser()

# ── answer_chain: 학생의 문제 풀이 답안 평가 ──
# 학생이 문제의 답을 제출했을 때 정오답 여부와 피드백을 생성하는 체인입니다.
# 답변 마지막에 반드시 [정답] 또는 [오답]을 포함시켜 서비스 계층에서 파싱합니다.
answer_eval_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    너는 초등학교 수학 선생님이야.
    학생의 답변을 평가할 때 다음 [출력 규칙]을 반드시 지켜서 한글로 답변해 줘.
    수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해 줘.

    [출력 규칙]
    1. 모든 숫자와 연산 기호는 LaTeX 형식인 $ 기호로 감싸서 표현해.
       (예: 5000 + 3000은 $5000 + 3000$으로 작성)
    2. 분수는 \\frac{{분자}}{{분모}} 형식을 사용해. (예: $\\frac{{1}}{{2}}$)
    3. 곱셈 기호는 \\times, 나눗셈 기호는 \\div를 사용해.

    [문제 정보]
    문제: {problem_question}
    정답 및 풀이: {problem_solution}

    [학생의 답변]
    {student_answer}

    [가이드라인]
    1. 정답 여부만 말하지 말고, 학생이 어느 부분을 잘했는지 혹은 왜 틀렸는지 친절하게 설명해줘.
    2. 정답을 맞혔다면 칭찬하고 다음 단계로 격려해줘.
    3. 틀렸다면 정답을 바로 주지 말고, 다시 생각할 수 있는 '힌트'를 먼저 줘.
    4. 모든 수식은 LaTeX 형식(예: $2 + 3 = 5$)으로 작성해줘.
    5. **반드시 답변의 맨 마지막 줄에 [정답] 또는 [오답]이라고 명확하게 적어줘.**
    """),
    ("user", "{student_answer}")    # 학생이 제출한 답안이 들어갑니다.
])

# answer_chain: 문제 정오답 평가 체인
# 사용 위치: evaluate_answer_node() 안에서 직접 호출됩니다.
answer_chain = answer_eval_prompt | llm | StrOutputParser()

# ==========================================
# 3. Q&A 챗봇
# ==========================================

# Q&A 챗봇의 시스템 프롬프트 (루미 선생님의 기본 성격과 규칙을 정의합니다)
# 별도의 체인을 만들지 않고, llm.invoke(messages)를 직접 호출하는 방식을 사용합니다.
# 이유: 대화 기록(chat_history)을 동적으로 메시지 리스트에 추가해야 하기 때문입니다.
_QA_SYSTEM_PROMPT = """
        너는 수학 선생님 '루미'야.
        초등학생 질문에 친절하게 한글로 답해줘.
        너는 엄격하고 전문적인 수학 선생님이야. 모든 답변은 수학적 지식에 근거해야 해.

        가장 중요한 규칙:
        수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해줘.

        지침:
        - 초등학생 3학년 눈높이에 맞게 상냥한 말투(~했어?, ~단다!)를 사용할 것.
        - 모든 수식은 LaTeX 형식(예: $2 + 3 = 5$)으로 작성해줘.
        """


def ask_question_to_tutor(question: str, chat_history: list) -> str:
    """
    【Q&A 챗봇 함수】
    학생의 질문과 이전 대화 기록을 바탕으로 루미 선생님의 답변을 생성합니다.

    【LangChain 체인 대신 llm.invoke()를 직접 사용하는 이유】
    - 대화 기록(chat_history)을 HumanMessage/AIMessage 객체로 변환하여
      메시지 리스트에 순서대로 쌓아야 합니다.
    - ChatPromptTemplate은 고정된 구조에 적합하지만, 대화 기록처럼
      개수가 동적으로 변하는 경우에는 직접 메시지 리스트를 구성하는 방식이
      더 유연합니다.

    매개변수:
        question (str)     : 학생이 입력한 질문 텍스트
        chat_history (list): 이전 대화 기록 리스트.
                             각 요소는 {"role": "user"|"assistant", "content": "..."} 형태입니다.

    반환값:
        str: 루미 선생님의 답변 텍스트 (오류 발생 시 오류 메시지 문자열 반환)

    호출 위치:
        app/services/tutor_service.py → ask_question_service()에서 호출됩니다.
        (이 함수는 동기 함수이므로, 서비스에서 asyncio.to_thread()로 감싸서 호출합니다.)
    """
    # 시스템 메시지(루미의 역할 설정)를 첫 번째로 추가합니다.
    messages = [SystemMessage(content=_QA_SYSTEM_PROMPT)]

    # 이전 대화 기록을 LangChain 메시지 객체로 변환하여 순서대로 추가합니다.
    # LLM이 대화 문맥을 이해하려면 이전 질문-답변 쌍이 모두 필요합니다.
    for turn in chat_history:
        role = turn.get("role", "")
        content = turn.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))  # 학생의 이전 발화

        elif role == "assistant":
            messages.append(AIMessage(content=content))      # 루미의 이전 답변

    # 현재 학생 질문을 마지막에 추가합니다.
    messages.append(HumanMessage(content=question))

    try:
        # LLM에 전체 대화 기록을 넘겨 답변을 생성합니다.
        response = llm.invoke(messages)
        return response.content  # AIMessage 객체에서 텍스트만 추출

    except Exception as e:
        return f"오류 발생: {e}"


# ==========================================
# 4. LangGraph 상태
# ==========================================
#
# 【LangGraph StateGraph란?】
# LangGraph는 여러 AI 처리 단계(노드)를 그래프 구조로 연결하는 프레임워크입니다.
#
# 핵심 개념:
#   State(상태): 그래프의 모든 노드가 공유하는 데이터 저장소입니다.
#                노드가 실행될 때마다 State를 읽고 업데이트합니다.
#
#   Node(노드): State를 받아 처리하고, 업데이트된 State를 반환하는 함수입니다.
#               예: fetch_units_node, fetch_problem_node, evaluate_concept_node
#
#   Edge(엣지): 노드와 노드를 연결하는 실행 경로입니다.
#               일반 엣지: A 노드가 끝나면 항상 B 노드로 이동합니다.
#               조건부 엣지: 상태값에 따라 다른 노드로 분기합니다.
#
#   Router(라우터): 조건부 엣지에서 어느 노드로 갈지 결정하는 함수입니다.
#                   예: entry_router() → task_type에 따라 분기
#
# 이 튜터 시스템에서 사용하는 StateGraph 흐름:
#   [시작]
#     ↓ entry_router() 판단
#     ├─ task_type == None    → get_units → get_problem → [종료]
#     ├─ task_type == "concept" → eval_concept → [종료]
#     └─ task_type == "answer"  → eval_answer  → [종료]
# ==========================================

class TutorState(TypedDict):
    """
    【LangGraph 공유 상태(State) 클래스】
    StateGraph의 모든 노드가 이 딕셔너리를 통해 데이터를 주고받습니다.
    TypedDict를 사용하여 각 키의 타입을 명시적으로 선언합니다.

    필드 설명:
        units (list)              : get_units Tool이 반환한 전체 단원 목록
        selected_unit (str)       : 학생이 선택한 단원 이름
        problem (dict)            : get_problem_by_unit Tool이 반환한 문제 정보
        task_type (str)           : 워크플로우 분기 결정 키
                                    None → 문제 가져오기 흐름
                                    "concept" → 개념 이해도 평가 흐름
                                    "answer"  → 정오답 평가 흐름
        student_explanation (str) : 학생이 자신의 말로 설명한 개념 텍스트
        student_answer (str)      : 학생이 제출한 문제 풀이 답안
        feedback (str)            : LLM이 생성한 피드백 텍스트
        messages (list)           : LangGraph 메시지 기록 (add_messages: 덮어쓰지 않고 누적)
        context (str)             : 미래 확장용 추가 컨텍스트 (현재 미사용)
    """

    units: Optional[list]
    selected_unit: Optional[str]
    problem: Optional[Dict]

    task_type: Optional[str]
    student_explanation: Optional[str]
    student_answer: Optional[str]
    feedback: Optional[str]

    # Annotated[list, add_messages]: 일반 list와 달리, 새 메시지를 기존 목록에 추가(append)합니다.
    # 덮어쓰기(replace)가 아닌 누적 방식으로 대화 기록을 유지합니다.
    messages: Annotated[list, add_messages]
    context: Optional[str]


# ── LangGraph 노드 함수들 ──
# 각 노드 함수는 (state: TutorState) → Dict[str, Any] 형태를 가집니다.
# 반환한 딕셔너리의 키-값이 State에 업데이트됩니다.

def fetch_units_node(state: TutorState) -> Dict[str, Any]:
    """
    【노드: 단원 목록 가져오기】
    get_units LangChain Tool을 호출하여 CSV에서 전체 단원 목록을 가져옵니다.

    진입 조건: entry_router()가 task_type == None일 때 이 노드로 라우팅합니다.
    다음 노드: fetch_problem_node (get_units → get_problem 엣지로 연결됨)

    반환값: {"units": [...단원 목록...]}이 TutorState에 업데이트됩니다.
    """
    return {"units": get_units.invoke({})}


def fetch_problem_node(state: TutorState) -> Dict[str, Any]:
    """
    【노드: 문제 가져오기】
    State에서 선택된 단원(selected_unit)을 읽어 해당 단원의 문제 1개를 가져옵니다.

    진입 조건: fetch_units_node 이후 자동으로 실행됩니다. (get_units → get_problem 엣지)
    다음 노드: END (그래프 종료)

    반환값: {"problem": {문제 딕셔너리}} 또는 {"problem": None}이 State에 업데이트됩니다.
    """
    unit_name = state.get("selected_unit")

    # selected_unit이 있을 때만 문제를 조회합니다.
    if unit_name:
        return {"problem": get_problem_by_unit.invoke({"unit_name": unit_name})}

    # 단원이 선택되지 않은 경우 None을 반환합니다.
    return {"problem": None}


def evaluate_concept_node(state: TutorState) -> Dict[str, Any]:
    """
    【노드: 개념 이해도 평가】
    concept_chain을 호출하여 학생의 개념 설명이 올바른지 평가합니다.

    진입 조건: entry_router()가 task_type == "concept"일 때 이 노드로 라우팅합니다.
    다음 노드: END (그래프 종료)

    State에서 읽는 값:
        - state["selected_unit"]      : 평가 기준이 되는 단원(개념) 이름
        - state["student_explanation"]: 학생이 작성한 개념 설명 텍스트

    반환값: {"feedback": "평가 결과 텍스트 ([PASS] 또는 [FAIL] 포함)"}이 State에 업데이트됩니다.
    """
    feedback = concept_chain.invoke({
        "concept": state["selected_unit"],
        "student_explanation": state["student_explanation"]
    })

    return {"feedback": feedback}


def evaluate_answer_node(state: TutorState) -> Dict[str, Any]:
    """
    【노드: 문제 정오답 평가】
    answer_chain을 호출하여 학생의 답안이 맞는지 평가하고 피드백을 생성합니다.

    진입 조건: entry_router()가 task_type == "answer"일 때 이 노드로 라우팅합니다.
    다음 노드: END (그래프 종료)

    State에서 읽는 값:
        - state["problem"]       : 문제 딕셔너리 (문제, 풀이, 정답 키를 포함)
        - state["student_answer"]: 학생이 제출한 답안 텍스트

    반환값: {"feedback": "정오답 피드백 텍스트 ([정답] 또는 [오답] 포함)"}이 State에 업데이트됩니다.
    """
    problem = state["problem"]

    feedback = answer_chain.invoke({
        "problem_question": problem["문제"],
        "problem_solution": problem["풀이"],
        "correct_answer": problem["정답"],
        "student_answer": state["student_answer"]
    })

    return {"feedback": feedback}


def entry_router(state: TutorState) -> str:
    """
    【LangGraph 조건부 진입 라우터】
    State의 task_type 값을 읽어 그래프의 첫 번째 실행 노드를 결정합니다.

    【라우터(Router)란?】
    - 일반 엣지는 항상 같은 다음 노드로 이동합니다.
    - 조건부 엣지는 이 라우터 함수의 반환값에 따라 다른 노드로 분기합니다.
    - set_conditional_entry_point()에 등록되어 그래프 시작 시 가장 먼저 호출됩니다.

    반환값 → 실행될 노드 이름:
        "eval_concept" : task_type == "concept" → evaluate_concept_node 실행
        "eval_answer"  : task_type == "answer"  → evaluate_answer_node 실행
        "get_units"    : 그 외(None 등)         → fetch_units_node 실행

    호출 위치:
        workflow.set_conditional_entry_point()에 등록되어 LangGraph가 자동으로 호출합니다.
    """
    task = state.get("task_type")

    if task == "concept":
        return "eval_concept"   # → evaluate_concept_node

    elif task == "answer":
        return "eval_answer"    # → evaluate_answer_node

    return "get_units"          # → fetch_units_node (기본 흐름)


# ==========================================
# 5. Graph 구성
# ==========================================
#
# 【LangGraph StateGraph 구성 방법】
# 1. StateGraph(상태 클래스)로 그래프 인스턴스를 생성합니다.
# 2. add_node(이름, 함수)로 처리 단계(노드)를 등록합니다.
# 3. set_conditional_entry_point(라우터, 매핑)로 조건부 진입점을 설정합니다.
# 4. add_edge(출발 노드, 도착 노드)로 노드 간 연결(엣지)을 정의합니다.
# 5. compile()로 실행 가능한 Runnable 객체(tutor_app)를 생성합니다.
#
# 완성된 그래프 흐름:
#   [START]
#     ↓ entry_router() 판단
#     ├─ "get_units"    → fetch_units_node → fetch_problem_node → [END]
#     ├─ "eval_concept" → evaluate_concept_node                 → [END]
#     └─ "eval_answer"  → evaluate_answer_node                  → [END]
# ==========================================

# StateGraph 인스턴스 생성: TutorState를 공유 상태로 사용합니다.
workflow = StateGraph(TutorState)

# 노드 등록: (노드 이름, 실행할 함수)를 연결합니다.
workflow.add_node("get_units", fetch_units_node)        # 단원 목록 조회 노드
workflow.add_node("get_problem", fetch_problem_node)    # 문제 조회 노드
workflow.add_node("eval_concept", evaluate_concept_node) # 개념 이해도 평가 노드
workflow.add_node("eval_answer", evaluate_answer_node)   # 문제 정오답 평가 노드

# 조건부 진입점 설정: entry_router()의 반환값과 노드 이름을 매핑합니다.
# entry_router가 "get_units"를 반환하면 → get_units 노드로, 나머지도 동일한 방식입니다.
workflow.set_conditional_entry_point(
    entry_router,
    {
        "get_units": "get_units",
        "eval_concept": "eval_concept",
        "eval_answer": "eval_answer"
    }
)

# 일반 엣지 정의: A 노드가 완료되면 항상 B 노드로 이동합니다.
workflow.add_edge("get_units", "get_problem")   # 단원 조회 완료 → 문제 조회
workflow.add_edge("get_problem", END)            # 문제 조회 완료 → 그래프 종료
workflow.add_edge("eval_concept", END)           # 개념 평가 완료 → 그래프 종료
workflow.add_edge("eval_answer", END)            # 정오답 평가 완료 → 그래프 종료

# 그래프 컴파일: 위에서 정의한 노드와 엣지를 최종적으로 실행 가능한 객체로 변환합니다.
# tutor_app.invoke(state)로 그래프를 실행할 수 있습니다.
tutor_app = workflow.compile()


# ==========================================
# 6. Wrapper
# ==========================================
#
# 【Wrapper 함수란?】
# LangGraph 그래프(tutor_app)를 직접 호출하는 대신, 외부 코드(tutor_service.py)가
# 쉽게 사용할 수 있도록 감싸는(wrap) 함수들입니다.
# State 딕셔너리를 직접 구성하는 번거로움을 숨기고, 명확한 인터페이스를 제공합니다.
# ==========================================

def evaluate_concept_understanding(concept: str, student_explanation: str):
    """
    【개념 이해도 평가 Wrapper】
    LangGraph를 통해 학생의 개념 설명을 평가하고 피드백 텍스트를 반환합니다.

    내부 동작:
        1. task_type="concept"으로 State를 구성합니다.
        2. tutor_app.invoke()로 그래프를 실행합니다.
        3. entry_router → eval_concept → evaluate_concept_node → concept_chain 순서로 실행됩니다.
        4. State에 저장된 "feedback" 값을 꺼내 반환합니다.

    매개변수:
        concept (str)             : 평가 기준 단원 이름 (예: "분수")
        student_explanation (str) : 학생이 자신의 말로 작성한 개념 설명

    반환값:
        str: LLM이 생성한 평가 피드백 (마지막에 [PASS] 또는 [FAIL] 포함)

    호출 위치:
        app/services/tutor_service.py → evaluate_concept_service()에서 호출됩니다.
        (asyncio.to_thread()로 감싸서 비동기 환경에서 안전하게 호출됩니다.)
    """
    result = tutor_app.invoke({
        "task_type": "concept",
        "selected_unit": concept,
        "student_explanation": student_explanation,
        "messages": []
    })

    return result.get("feedback")


def evaluate_answer(problem: dict, student_answer: str):
    """
    【문제 정오답 평가 Wrapper】
    LangGraph를 통해 학생의 답안을 평가하고 피드백 텍스트를 반환합니다.

    내부 동작:
        1. task_type="answer"로 State를 구성합니다.
        2. tutor_app.invoke()로 그래프를 실행합니다.
        3. entry_router → eval_answer → evaluate_answer_node → answer_chain 순서로 실행됩니다.
        4. State에 저장된 "feedback" 값을 꺼내 반환합니다.

    매개변수:
        problem (dict)        : 문제 정보 딕셔너리. 최소한 "문제", "풀이", "정답" 키를 포함해야 합니다.
        student_answer (str)  : 학생이 제출한 답안 텍스트

    반환값:
        str: LLM이 생성한 정오답 피드백 (마지막에 [정답] 또는 [오답] 포함)

    호출 위치:
        app/services/tutor_service.py → evaluate_answer_service()와
        evaluate_exam_answers_service()에서 호출됩니다.
        (asyncio.to_thread()로 감싸서 비동기 환경에서 안전하게 호출됩니다.)
    """
    result = tutor_app.invoke({
        "task_type": "answer",
        "problem": problem,
        "student_answer": student_answer,
        "messages": []
    })

    return result.get("feedback")


# ==========================================
# 7. 수학 질문 분류 (자유학습용)
# ==========================================

# LLM에게 "수학 관련이면 YES, 아니면 NO" 한 단어만 답하게 하는 프롬프트
# 체인을 쓰지 않고 llm.invoke()를 직접 호출합니다.
# 이유: 단순한 YES/NO 분류이므로 ChatPromptTemplate 없이 메시지 리스트로 충분합니다.
_CLASSIFY_SYSTEM_PROMPT = """너는 질문 분류기야.
학생의 질문이 수학과 관련된 질문인지 판단해.
수학 개념, 수학 문제 풀이, 수학 공식, 수학적 사고와 관련된 질문이면 "YES"
그 외 모든 질문이면 "NO"
반드시 YES 또는 NO 한 단어만 답해."""


def classify_math_question(question: str) -> bool:
    """
    학생의 질문이 수학 관련인지 LLM으로 분류합니다.
    - True: 수학 관련 질문
    - False: 수학과 무관한 질문
    - 분류 실패 시 True 반환 (사용자 경험 우선)

    【분류기(Classifier)로 LLM을 사용하는 이유】
    - 단순 키워드 매칭은 "피자를 8조각으로 나누면 몇 분의 몇이야?" 같은 문장을
      수학 질문으로 인식하지 못합니다.
    - LLM은 문장의 의미(semantic)를 이해하므로 더 정확하게 분류할 수 있습니다.
    - 단, LLM 호출은 비용이 발생하므로, 응답을 YES/NO로 제한하여 토큰을 최소화합니다.

    매개변수:
        question (str): 학생이 입력한 질문 텍스트

    반환값:
        bool: True = 수학 관련 질문, False = 수학 무관 질문

    호출 위치:
        app/services/tutor_service.py → free_study_service()에서
        asyncio.to_thread(classify_math_question, question)으로 호출됩니다.
    """
    messages = [
        SystemMessage(content=_CLASSIFY_SYSTEM_PROMPT),
        HumanMessage(content=question)
    ]
    try:
        response = llm.invoke(messages)
        # "YES"가 포함되어 있으면 수학 질문으로 판단합니다.
        # .upper()로 대소문자 구분 없이 비교합니다.
        return "YES" in response.content.upper()
    except Exception:
        # 분류 오류 시 수학 질문으로 간주 (학생이 불편하지 않도록)
        return True


# ==========================================
# 8. RAG 연동 답변 생성 (자유학습용)
# ==========================================
#
# 【RAG (Retrieval-Augmented Generation)란?】
# RAG는 "검색(Retrieval) + 생성(Generation)"을 결합한 AI 기술입니다.
#
# 일반 LLM 답변의 문제점:
#   - LLM은 학습 데이터에 없는 내용을 그럴듯하게 지어내는 "환각(hallucination)"이 발생합니다.
#   - 특히 수학 문제처럼 정확한 답이 요구되는 경우 신뢰성이 떨어집니다.
#
# RAG의 해결 방법:
#   1. 검색(Retrieve): 학생 질문과 유사한 문제를 ChromaDB(벡터 DB)에서 먼저 찾습니다.
#      - 텍스트를 수치 벡터(embedding)로 변환하여 의미적으로 가까운 문서를 검색합니다.
#      - 거리(distance) 기반으로 유사도를 측정하며, 임계값(1.2) 이하인 것만 사용합니다.
#   2. 생성(Generate): 검색된 문제와 풀이를 참고자료로 LLM에 제공한 뒤 답변을 생성합니다.
#      - LLM은 "근거 있는" 답변을 할 수 있어 정확도가 높아집니다.
#
# 이 시스템에서의 RAG 흐름:
#   학생 질문 → ChromaDB 검색 → 유사 문제/풀이 추출 → 시스템 프롬프트에 포함
#            → LLM 답변 생성 (JSON 형식: answer + tts_text)
# ==========================================

def ask_question_with_rag_context(question: str, chat_history: list) -> tuple:
    """
    ChromaDB에서 유사 문제를 검색한 뒤, 그 내용을 참고자료로 활용하여
    LLM이 학생 눈높이에 맞는 답변을 생성합니다.
    수학과 무관한 엉뚱한 질문을 하면 부드럽게 수학 학습으로 유도해 주세요.

    반환값: (답변 딕셔너리, RAG 사용 여부)
    - 답변 딕셔너리 형태: {"answer": "화면 표시용", "tts_text": "음성 재생용 한글 발음"}

    【JSON 형식 출력을 강제하는 이유】
    - 화면에 표시할 텍스트(LaTeX 수식 포함)와 TTS로 읽어줄 텍스트(순수 한글)가 달라야 합니다.
    - JSON의 "answer" 키는 화면용(수식 포함), "tts_text" 키는 음성용(한글 발음)으로 분리합니다.
    - LLM의 response_format={"type": "json_object"} 옵션으로 반드시 JSON만 출력하게 강제합니다.

    매개변수:
        question (str)     : 학생이 자유학습 탭에서 입력한 질문 텍스트
        chat_history (list): 이전 대화 기록 리스트
                             각 요소: {"role": "user"|"assistant", "content": "..."}

    반환값:
        tuple: (응답 딕셔너리, rag_used 불리언)
               응답 딕셔너리: {"answer": "화면 표시용 텍스트", "tts_text": "음성용 한글 텍스트"}
               rag_used: ChromaDB 검색 결과를 실제로 활용했으면 True, 아니면 False

    호출 위치:
        app/services/tutor_service.py → free_study_service()에서
        asyncio.to_thread(ask_question_with_rag_context, question, chat_history)로 호출됩니다.
    """
    rag_context = ""    # RAG에서 찾은 참고자료 텍스트
    rag_used = False    # RAG를 실제로 활용했는지 여부

    # ── 1단계: ChromaDB에서 유사 문제 검색 ──
    # RAG_sys/rag_helper.py의 search_problems()를 호출합니다.
    # 이 함수는 학생 질문을 벡터로 변환하여 ChromaDB에서 의미적으로 유사한 문제를 찾습니다.
    try:
        from RAG_sys.rag_helper import search_problems

        # n_results=3: 가장 유사한 문제 3개를 검색합니다.
        results = search_problems(question, n_results=3)

        # 검색 결과가 있으면 필터링합니다.
        if results and results.get("documents") and results["documents"][0]:
            documents = results["documents"][0]     # 문제 텍스트 목록
            metadatas = results["metadatas"][0] if results.get("metadatas") else []  # 단원, 정답, 풀이 등 메타데이터
            distances = results["distances"][0] if results.get("distances") else []  # 벡터 거리값 (낮을수록 유사)

            relevant_docs = []
            for i, doc in enumerate(documents):
                dist = distances[i] if i < len(distances) else 999
                # 임계값 1.2 이하인 문서만 사용합니다.
                # 거리가 너무 크면(1.2 초과) 질문과 관련성이 낮은 문서이므로 제외합니다.
                if dist < 1.2:  # 임계값 (필요시 조정)
                    meta = metadatas[i] if i < len(metadatas) else {}
                    relevant_docs.append({
                        "문제": doc,
                        "단원": meta.get("단원", ""),
                        # ⭐ 변경: '풀이및정답' 대신 '정답'과 '풀이'를 각각 가져옵니다.
                        "정답": meta.get("정답", ""),
                        "풀이": meta.get("풀이", ""),
                    })

            # 임계값을 통과한 유사 문서가 있으면 RAG 컨텍스트를 구성합니다.
            if relevant_docs:
                rag_used = True
                rag_parts = []
                for j, rd in enumerate(relevant_docs):
                    # ⭐ 변경: LLM에게 참고자료를 넘겨줄 때 정답과 풀이를 나눠서 줍니다.
                    rag_parts.append(
                        f"[참고자료 {j+1}]\n"
                        f"단원: {rd['단원']}\n"
                        f"문제: {rd['문제']}\n"
                        f"정답: {rd['정답']}\n"
                        f"풀이: {rd['풀이']}"
                    )
                # 여러 참고자료를 빈 줄로 구분하여 하나의 문자열로 합칩니다.
                rag_context = "\n\n".join(rag_parts)

    except Exception as e:
        # RAG 검색 실패 시 오류를 출력하고, RAG 없이 LLM 단독 답변으로 전환합니다.
        print(f"⚠️ RAG 검색 오류 (LLM 직접 답변으로 전환): {e}")

    # ── 2단계: 시스템 프롬프트 구성 (JSON 출력 강제) ──
    # 중괄호 {} 포매팅 충돌을 막기 위해 f-string 대신 일반 문자열 사용 후 결합
    # (f-string 안에서 JSON 예시의 {}가 Python 포매팅 문법과 충돌하기 때문입니다.)
    system_prompt = (
        "너는 수학 선생님 '루미'야.\n"
        "초등학생 질문에 친절하고 쉽게 답해줘.\n"
        "학생이 수학과 무관한 엉뚱한 질문을 하면 부드럽게 수학 학습으로 유도해 줘\n"
        "수치 계산은 반드시 정확하게 해줘.\n\n"
        "【중요: 출력 형식】\n"
        "반드시 아래의 JSON 형식으로만 응답해야 해. 마크다운 코드 블록이나 다른 부연 설명은 절대 넣지 마.\n"
        "{\n"
        '  "answer": "학생 화면에 보여줄 답변 (수식은 $...$ 형식으로 포함)",\n'
        '  "tts_text": "시각장애인이 듣고 완벽하게 이해할 수 있도록, answer 내용 중 모든 수식을 순수 한글 발음으로 풀어서 쓴 텍스트. 분수 \\frac{A}{B}는 \'B 분의 A\'로 읽고, 기호는 반드시 한글(÷는 나누기, =는 은, ×는 고파기)로 적어. 또한 \'나눗셈\'이라는 단어는 발음 오류 방지를 위해 \'나눋쎔\'으로 강제로 적어줘."\n'
        "}\n\n"
    )

    # RAG로 찾은 참고자료가 있으면 시스템 프롬프트 뒤에 추가합니다.
    # RAG 컨텍스트가 없으면 LLM이 자체 지식만으로 답변합니다.
    if rag_context:
        system_prompt += (
            "아래 참고자료를 바탕으로 개념과 예제를 학생 눈높이에 맞게 설명해줘.\n"
            "학생이 수학과 무관한 엉뚱한 얘기를 하면 부드럽게 수학 학습으로 유도해 줘\n\n"
            "참고자료에 없는 내용은 네가 아는 지식으로 보충해도 돼.\n\n"
            f"--- 참고자료 ---\n{rag_context}\n--- 참고자료 끝 ---"
        )

    # ── 3단계: 대화 기록 + 질문으로 LLM 호출 ──
    # 시스템 프롬프트로 시작하고, 이전 대화 기록을 순서대로 추가합니다.
    messages = [SystemMessage(content=system_prompt)]

    for turn in chat_history:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # 현재 학생 질문을 마지막에 추가합니다.
    messages.append(HumanMessage(content=question))

    # ── 4단계: 응답 파싱 및 반환 ──
    try:
        # response_format={"type": "json_object"}: LLM이 반드시 JSON 형식으로만 답하게 강제합니다.
        # .bind()로 이 옵션을 llm에 추가한 뒤 invoke()로 호출합니다.
        response = llm.bind(response_format={"type": "json_object"}).invoke(messages)
        raw_content = response.content.strip()

        # JSON 문자열을 파이썬 딕셔너리로 변환합니다.
        parsed_data = json.loads(raw_content.strip())

        # 정상적으로 JSON이 파싱되면 딕셔너리 반환
        return parsed_data, rag_used

    except json.JSONDecodeError as e:
        # JSON 파싱 실패 시: 원본 텍스트를 그대로 answer와 tts_text 양쪽에 넣어 반환합니다.
        # 학생이 빈 화면을 보는 것보다 파싱 실패한 텍스트라도 보여주는 것이 낫습니다.
        print(f"⚠️ JSON 파싱 오류: {e}\n원본 응답: {response.content}")
        # 파싱에 실패하면 화면용과 음성용에 동일한 텍스트 할당
        fallback_data = {"answer": response.content, "tts_text": response.content}
        return fallback_data, rag_used

    except Exception as e:
        # 그 외 모든 오류: 오류 메시지를 포함한 딕셔너리를 반환하고 rag_used=False로 설정합니다.
        error_data = {"answer": f"오류가 발생했어요: {e}", "tts_text": "오류가 발생했어요."}
        return error_data, False
