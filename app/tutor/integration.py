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

DATA_PATH = 'data/processed/math_tutor_dataset.csv'

load_dotenv()
client = OpenAI()
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)


# ==========================================
# 1. 일반 함수 및 Tools
# ==========================================

def generate_speech_with_cache(text: str) -> bytes:
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    # ⭐ 핵심 변경: 프로젝트 폴더(assets/audio) 대신, Live Server가 감시하지 못하는 'OS 임시 폴더'를 사용합니다!
    audio_dir = os.path.join(tempfile.gettempdir(), "ai_math_tutor_audio")
    
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    file_path = os.path.join(audio_dir, f"{text_hash}.mp3")

    # 이미 생성된 음성이 임시 폴더에 있다면 바로 읽어옵니다. (OpenAI 비용 절감 & 속도 향상)
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text
        )
        
        # Live Server가 모르는 안전한 임시 폴더에 파일 저장
        response.write_to_file(file_path)

        with open(file_path, "rb") as f:
            return f.read()

    except Exception as e:
        print(f"❌ 음성 생성 오류: {e}")
        return None


@tool
def get_units() -> list:
    """수학 튜터 데이터셋에 있는 전체 단원 목록을 반환합니다."""
    df = pd.read_csv(DATA_PATH)
    return sorted(df['단원'].unique().tolist())


@tool
def get_problem_by_unit(unit_name: str) -> dict:
    """선택한 단원에서 문제 하나를 무작위로 반환합니다."""
    df = pd.read_csv(DATA_PATH)
    unit_df = df[df['단원'] == unit_name]

    if not unit_df.empty:
        return unit_df.sample(n=1).iloc[0].to_dict()

    return None


# ⭐ 시험용 문제 추출

def get_exam_problems(unit_name: str, n: int =3) -> list:

    df = pd.read_csv(DATA_PATH)
    unit_df = df[df['단원'] == unit_name]

    if unit_df.empty:
        return []

    k = min(n, len(unit_df))

    problems = unit_df.sample(n=k).to_dict("records")

    return [
        {key: (None if str(val) == "nan" else val) for key, val in p.items()}
        for p in problems
    ]

# ==========================================
# 2. LangChain 체인
# ==========================================

explain_prompt = ChatPromptTemplate.from_messages([
    ("system", """너는 수학 선생님인 토끼 캐릭터 '루미'야. 초등학교 학생들에게 아주 친절하고 상냥하게 말해줘.
    학생이 선택한 '{unit_name}' 단원에 대해 아주 쉽고 재미있는 비유를 들어서 한글로 설명해줘.
    
    [가이드라인]
    1. "안녕! 나는 루미 선생님이야!"처럼 친근하게 시작할 것.
    2. 초등학생이 이해하기 쉬운 비유를 하나 들어줄 것.
    3. 설명 마지막에는 "이해가 잘 되었니? 이제 문제를 하나 풀어볼까?"라고 물어봐줘.""")
])


explain_chain = explain_prompt | llm | StrOutputParser()

def explain_concept(unit_name: str) -> str:
    return explain_chain.invoke({"unit_name": unit_name})

reexplain_prompt = ChatPromptTemplate.from_messages([
    ("system", """너는 초등학생 수학 선생님인 토끼 캐릭터 '루미'야.
    학생이 '{unit_name}' 단원의 개념을 한 번 들었는데 잘 이해하지 못했어.
    처음 설명보다 훨씬 더 쉽고, 피자 나누기나 사탕 나누기 같은 일상생활의 재미있고 친숙한 예시를 들어서 아주 친절하게 한글로 다시 설명해줘. 수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해줘.
    """)
])

reexplain_chain = reexplain_prompt | llm | StrOutputParser()

def reexplain_concept(unit_name: str) -> str:
    """이해가 부족한 학생을 위한 더 쉬운 보충 설명 생성"""
    return reexplain_chain.invoke({"unit_name": unit_name})

concept_eval_prompt = ChatPromptTemplate.from_messages([
    ("system",  """당신은 초등학교 수학 선생님입니다. 학생이 '{concept}'에 대해 설명한 내용을 듣고 한글로 평가해주세요.
    
    [평가 규칙]
    1. 핵심 원리가 포함되었는지 확인합니다.
    2. 이해도가 충분하면 답변 마지막에 반드시 [PASS]라고 적어주세요.
    3. 설명이 부족하거나 틀렸다면 친절하게 교정해주고, 답변 마지막에 반드시 [FAIL]이라고 적어주세요.
    4. 모든 피드백은 따뜻하고 격려하는 말투로 작성하세요.
    5. 수학과 무관한 엉뚱한 대답을 하면 부드럽게 수학 학습으로 유도해줘.
    """),
    ("user", "{student_explanation}")
])

concept_chain = concept_eval_prompt | llm | StrOutputParser()

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
    ("user", "{student_answer}")
])

answer_chain = answer_eval_prompt | llm | StrOutputParser()

# ==========================================
# 3. Q&A 챗봇
# ==========================================

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

    messages = [SystemMessage(content=_QA_SYSTEM_PROMPT)]

    for turn in chat_history:
        role = turn.get("role", "")
        content = turn.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))

        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    try:
        response = llm.invoke(messages)
        return response.content

    except Exception as e:
        return f"오류 발생: {e}"


# ==========================================
# 4. LangGraph 상태
# ==========================================

class TutorState(TypedDict):

    units: Optional[list]
    selected_unit: Optional[str]
    problem: Optional[Dict]

    task_type: Optional[str]
    student_explanation: Optional[str]
    student_answer: Optional[str]
    feedback: Optional[str]

    messages: Annotated[list, add_messages]
    context: Optional[str]


def fetch_units_node(state: TutorState) -> Dict[str, Any]:
    return {"units": get_units.invoke({})}


def fetch_problem_node(state: TutorState) -> Dict[str, Any]:

    unit_name = state.get("selected_unit")

    if unit_name:
        return {"problem": get_problem_by_unit.invoke({"unit_name": unit_name})}

    return {"problem": None}


def evaluate_concept_node(state: TutorState) -> Dict[str, Any]:

    feedback = concept_chain.invoke({
        "concept": state["selected_unit"],
        "student_explanation": state["student_explanation"]
    })

    return {"feedback": feedback}


def evaluate_answer_node(state: TutorState) -> Dict[str, Any]:

    problem = state["problem"]

    feedback = answer_chain.invoke({
        "problem_question": problem["문제"],
        "problem_solution": problem["풀이"],
        "correct_answer": problem["정답"],
        "student_answer": state["student_answer"]
    })

    return {"feedback": feedback}


def entry_router(state: TutorState) -> str:

    task = state.get("task_type")

    if task == "concept":
        return "eval_concept"

    elif task == "answer":
        return "eval_answer"

    return "get_units"


# ==========================================
# 5. Graph 구성
# ==========================================

workflow = StateGraph(TutorState)

workflow.add_node("get_units", fetch_units_node)
workflow.add_node("get_problem", fetch_problem_node)
workflow.add_node("eval_concept", evaluate_concept_node)
workflow.add_node("eval_answer", evaluate_answer_node)

workflow.set_conditional_entry_point(
    entry_router,
    {
        "get_units": "get_units",
        "eval_concept": "eval_concept",
        "eval_answer": "eval_answer"
    }
)

workflow.add_edge("get_units", "get_problem")
workflow.add_edge("get_problem", END)
workflow.add_edge("eval_concept", END)
workflow.add_edge("eval_answer", END)

tutor_app = workflow.compile()


# ==========================================
# 6. Wrapper
# ==========================================

def get_problem_workflow(unit_name: str):
    return tutor_app.invoke({"selected_unit": unit_name, "messages": []})


def evaluate_concept_understanding(concept: str, student_explanation: str):

    result = tutor_app.invoke({
        "task_type": "concept",
        "selected_unit": concept,
        "student_explanation": student_explanation,
        "messages": []
    })

    return result.get("feedback")


def evaluate_answer(problem: dict, student_answer: str):

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
    """
    messages = [
        SystemMessage(content=_CLASSIFY_SYSTEM_PROMPT),
        HumanMessage(content=question)
    ]
    try:
        response = llm.invoke(messages)
        return "YES" in response.content.upper()
    except Exception:
        # 분류 오류 시 수학 질문으로 간주 (학생이 불편하지 않도록)
        return True


# ==========================================
# 8. RAG 연동 답변 생성 (자유학습용)
# ==========================================

def ask_question_with_rag_context(question: str, chat_history: list) -> tuple:
    """
    ChromaDB에서 유사 문제를 검색한 뒤, 그 내용을 참고자료로 활용하여
    LLM이 학생 눈높이에 맞는 답변을 생성합니다.
    수학과 무관한 엉뚱한 질문을 하면 부드럽게 수학 학습으로 유도해 주세요.

    반환값: (답변 딕셔너리, RAG 사용 여부)
    - 답변 딕셔너리 형태: {"answer": "화면 표시용", "tts_text": "음성 재생용 한글 발음"}
    """
    rag_context = ""    # RAG에서 찾은 참고자료 텍스트
    rag_used = False    # RAG를 실제로 활용했는지 여부

    # ── 1단계: ChromaDB에서 유사 문제 검색 ──
    try:
        from RAG_sys.rag_helper import search_problems

        results = search_problems(question, n_results=3)

        if results and results.get("documents") and results["documents"][0]:
            documents = results["documents"][0]
            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            distances = results["distances"][0] if results.get("distances") else []

            relevant_docs = []
            for i, doc in enumerate(documents):
                dist = distances[i] if i < len(distances) else 999
                if dist < 1.2:  # 임계값 (필요시 조정)
                    meta = metadatas[i] if i < len(metadatas) else {}
                    relevant_docs.append({
                        "문제": doc,
                        "단원": meta.get("단원", ""),
                        # ⭐ 변경: '풀이및정답' 대신 '정답'과 '풀이'를 각각 가져옵니다.
                        "정답": meta.get("정답", ""),
                        "풀이": meta.get("풀이", ""),
                    })

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
                rag_context = "\n\n".join(rag_parts)

    except Exception as e:
        print(f"⚠️ RAG 검색 오류 (LLM 직접 답변으로 전환): {e}")

    # ── 2단계: 시스템 프롬프트 구성 (JSON 출력 강제) ──
    # 중괄호 {} 포매팅 충돌을 막기 위해 f-string 대신 일반 문자열 사용 후 결합
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

    if rag_context:
        system_prompt += (
            "아래 참고자료를 바탕으로 개념과 예제를 학생 눈높이에 맞게 설명해줘.\n"
            "학생이 수학과 무관한 엉뚱한 얘기를 하면 부드럽게 수학 학습으로 유도해 줘\n\n"
            "참고자료에 없는 내용은 네가 아는 지식으로 보충해도 돼.\n\n"
            f"--- 참고자료 ---\n{rag_context}\n--- 참고자료 끝 ---"
        )

    # ── 3단계: 대화 기록 + 질문으로 LLM 호출 ──
    messages = [SystemMessage(content=system_prompt)]

    for turn in chat_history:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    # ── 4단계: 응답 파싱 및 반환 ──
    try:
        response = llm.bind(response_format={"type": "json_object"}).invoke(messages)
        raw_content = response.content.strip()
            
        parsed_data = json.loads(raw_content.strip())
        
        # 정상적으로 JSON이 파싱되면 딕셔너리 반환
        return parsed_data, rag_used

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON 파싱 오류: {e}\n원본 응답: {response.content}")
        # 파싱에 실패하면 화면용과 음성용에 동일한 텍스트 할당
        fallback_data = {"answer": response.content, "tts_text": response.content}
        return fallback_data, rag_used
        
    except Exception as e:
        error_data = {"answer": f"오류가 발생했어요: {e}", "tts_text": "오류가 발생했어요."}
        return error_data, False