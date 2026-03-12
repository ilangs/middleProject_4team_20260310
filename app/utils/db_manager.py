"""
app/utils/db_manager.py  ─  SQLite 데이터베이스 관리 모듈

[역할]
이 파일은 프로젝트의 모든 로컬 데이터를 SQLite 파일(database/user_db.sqlite)에
저장·조회하는 함수들을 모아 놓은 "데이터 계층(Data Layer)"입니다.

[DB 테이블 구조]
┌──────────────────────────────────────────────────────────────────────────┐
│  users            - 회원 계정 정보 (아이디, 비밀번호, 닉네임, 캐릭터)      │
│  learning_history - 오늘의 학습 문제 풀이 기록 (정오답, 단원, 시각)        │
│  exam_results     - 단원 시험 결과 (점수, 오답 번호, AI 피드백)            │
│  chat_history     - 자유학습 AI 채팅 대화 기록                             │
│  token_logs       - LLM API 호출 시 소비된 토큰 수·비용 기록               │
└──────────────────────────────────────────────────────────────────────────┘

[설계 원칙]
- 모든 DB 연결은 contextmanager(get_db)로 관리 → 자동 커밋·롤백·연결 해제
- 비밀번호는 bcrypt 해시로 저장 (평문 절대 저장 금지)
- 각 함수는 단일 책임 원칙에 따라 하나의 CRUD 작업만 수행
"""

import sqlite3
import os
import pandas as pd
import bcrypt
from contextlib import contextmanager

# ──────────────────────────────────────────────
# 경로 상수
# ──────────────────────────────────────────────
DB_PATH  = 'database/user_db.sqlite'           # SQLite 파일 경로
CSV_PATH = 'data/processed/math_tutor_dataset.csv'  # 문제 데이터셋 경로

# ──────────────────────────────────────────────
# 토큰 비용 상수 (OpenAI GPT-4o 기준)
# ──────────────────────────────────────────────
PRICE_INPUT  = 0.000005   # 입력 토큰 1개당 $
PRICE_OUTPUT = 0.000015   # 출력 토큰 1개당 $
KRW_PER_USD  = 1350       # 달러→원 환율 (고정값, 실제 환율과 다를 수 있음)


# ──────────────────────────────────────────────
# DB 연결 컨텍스트 매니저
# ──────────────────────────────────────────────

@contextmanager
def get_db():
    """
    SQLite 연결을 안전하게 열고 닫는 컨텍스트 매니저.

    [사용 패턴]
        with get_db() as (conn, c):
            c.execute("SELECT ...")
            rows = c.fetchall()
        # with 블록을 벗어나면 자동으로 commit/close 처리

    [동작 흐름]
        1. database 폴더가 없으면 자동 생성
        2. DB 연결 열기
        3. try 블록 안에서 yield → 호출자가 SQL 실행
        4. 정상 종료 → commit
        5. 예외 발생 → rollback 후 예외 재전파
        6. finally → 항상 conn.close()
    """
    if not os.path.exists('database'):
        os.makedirs('database')

    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()
        yield conn, c
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 비밀번호 유틸리티
# ──────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    평문 비밀번호를 bcrypt 해시 문자열로 변환합니다.
    로그인 시 verify_password()와 함께 사용합니다.

    [bcrypt란?]
    단방향 암호화 알고리즘. 같은 비밀번호라도 실행할 때마다
    다른 해시값이 생성되지만(salt 때문), checkpw()로 검증 가능합니다.
    """
    salt   = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    입력된 평문 비밀번호가 DB에 저장된 해시와 일치하는지 확인합니다.
    로그인 엔드포인트(POST /auth/login)에서 호출됩니다.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


# ──────────────────────────────────────────────
# DB 초기화
# ──────────────────────────────────────────────

def init_db():
    """
    서버 시작 시(startup_event) 1회 호출되어 모든 테이블을 생성합니다.

    [CREATE TABLE IF NOT EXISTS 의미]
    이미 테이블이 있으면 건너뛰므로 기존 데이터가 삭제되지 않습니다.
    서버를 재시작해도 안전합니다.

    [ALTER TABLE로 컬럼 추가]
    기존 users 테이블에 nickname, character 컬럼이 없으면 추가합니다.
    마이그레이션(스키마 변경) 처리를 간단하게 구현한 방식입니다.

    [기본 계정 생성]
    student01 / 1234 계정을 INSERT OR IGNORE로 생성합니다.
    이미 존재하면 무시(중복 오류 방지).
    """
    with get_db() as (conn, c):

        # ── users 테이블 ──────────────────────────────
        # username을 PRIMARY KEY로 사용 → 중복 아이디 자동 방지
        c.execute("""
            CREATE TABLE IF NOT EXISTS users
            (username    TEXT PRIMARY KEY,
             password    TEXT,
             current_unit TEXT)
        """)

        # 기존 테이블에 컬럼이 없으면 추가 (ALTER TABLE)
        c.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in c.fetchall()]

        if "nickname" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN nickname TEXT")

        if "character" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN character TEXT")

        # ── learning_history 테이블 ───────────────────
        # 오늘의 학습에서 문제를 풀 때마다 1행씩 기록
        # is_correct: 1=정답, 0=오답
        c.execute("""
            CREATE TABLE IF NOT EXISTS learning_history
            (id         INTEGER PRIMARY KEY AUTOINCREMENT,
             username   TEXT,
             problem_id TEXT,
             unit       TEXT,
             is_correct INTEGER,
             timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ── exam_results 테이블 ───────────────────────
        # 단원 시험 완료 후 결과를 1행으로 저장
        # wrong_numbers: JSON 문자열 "[2, 4, 7]" 형식
        # feedback: JSON 문자열 {"1": "...", "2": "..."} 형식
        c.execute("""
            CREATE TABLE IF NOT EXISTS exam_results
            (id              INTEGER PRIMARY KEY AUTOINCREMENT,
             username        TEXT,
             unit            TEXT,
             score           INTEGER,
             total_questions INTEGER,
             wrong_numbers   TEXT,
             feedback        TEXT,
             timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ── chat_history 테이블 ───────────────────────
        # 자유학습 채팅 1턴당 2행 저장 (role='user' + role='assistant')
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_history
            (id        INTEGER PRIMARY KEY AUTOINCREMENT,
             username  TEXT NOT NULL,
             role      TEXT NOT NULL,    -- 'user' 또는 'assistant'
             content   TEXT NOT NULL,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ── token_logs 테이블 ─────────────────────────
        # LLM API 호출 시마다 1행 기록
        # action: 어떤 기능에서 호출했는지 ("개념설명", "채점" 등)
        # total_cost_usd: 해당 호출의 USD 비용 (입력+출력 토큰 합산)
        c.execute("""
            CREATE TABLE IF NOT EXISTS token_logs
            (id                INTEGER PRIMARY KEY AUTOINCREMENT,
             username          TEXT NOT NULL,
             action            TEXT NOT NULL,
             prompt_tokens     INTEGER DEFAULT 0,
             completion_tokens INTEGER DEFAULT 0,
             total_tokens      INTEGER DEFAULT 0,
             total_cost_usd    REAL    DEFAULT 0.0,
             timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ── 기본 테스트 계정 생성 ─────────────────────
        # INSERT OR IGNORE: 이미 존재하면 조용히 건너뜀
        hashed_pw = hash_password("1234")
        c.execute(
            """
            INSERT OR IGNORE INTO users
            (username, password, current_unit, nickname, character)
            VALUES (?, ?, ?, ?, ?)
            """,
            ('student01', hashed_pw, 'None', '학생1', 'bunny')
        )


# ──────────────────────────────────────────────
# 유저 조회
# ──────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    """
    username으로 사용자 정보를 조회합니다.
    존재하지 않으면 None을 반환합니다.

    [사용처]
    - auth.py: 로그인 시 비밀번호 검증
    - auth.py: JWT 토큰 검증 시 사용자 유효성 확인
    """
    with get_db() as (conn, c):
        c.execute(
            """
            SELECT username, password, current_unit, nickname, character
            FROM users
            WHERE username = ?
            """,
            (username,)
        )
        row = c.fetchone()

    if row is None:
        return None

    return {
        "username":     row[0],
        "password":     row[1],
        "current_unit": row[2],
        "nickname":     row[3],
        "character":    row[4]
    }


# ──────────────────────────────────────────────
# 유저 생성 (회원가입)
# ──────────────────────────────────────────────

def create_user(username: str, plain_password: str,
                nickname: str, character: str) -> bool:
    """
    새 사용자를 DB에 등록합니다.

    [반환값]
    - True  : 등록 성공
    - False : 아이디 중복 (IntegrityError → PRIMARY KEY 충돌)

    [사용처]
    - auth.py: POST /auth/register 엔드포인트
    """
    try:
        hashed_pw = hash_password(plain_password)

        with get_db() as (conn, c):
            c.execute(
                """
                INSERT INTO users
                (username, password, current_unit, nickname, character)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, hashed_pw, 'None', nickname, character)
            )
        return True

    except sqlite3.IntegrityError:
        # PRIMARY KEY(username) 중복 → 아이디 이미 사용 중
        return False


# ──────────────────────────────────────────────
# 학습 결과 저장
# ──────────────────────────────────────────────

def save_history(username: str, problem_id: str,
                 unit: str, is_correct: bool):
    """
    오늘의 학습에서 문제 1개를 풀었을 때 기록을 저장합니다.

    [사용처]
    - tutor.py: POST /api/history 엔드포인트
    - 학생이 AI 채점 후 "다음 문제" 버튼을 누를 때 호출됩니다.

    [is_correct]
    - True  → is_correct=1 (정답)
    - False → is_correct=0 (오답)
    """
    with get_db() as (conn, c):
        c.execute(
            "INSERT INTO learning_history (username, problem_id, unit, is_correct) VALUES (?, ?, ?, ?)",
            (username, str(problem_id), unit, 1 if is_correct else 0)
        )


# ──────────────────────────────────────────────
# 학습 기록 조회
# ──────────────────────────────────────────────

def get_user_history(username: str) -> pd.DataFrame:
    """
    특정 학생의 전체 학습 기록을 DataFrame으로 반환합니다.

    [반환 컬럼]
    - unit       : 단원명
    - is_correct : 정오답 (1/0)
    - timestamp  : 풀이 시각

    [사용처]
    - tutor.py: GET /api/history → 성적 대시보드(section4.js)에 표시
    """
    with get_db() as (conn, c):
        query = "SELECT unit, is_correct, timestamp FROM learning_history WHERE username = ?"
        df = pd.read_sql_query(query, conn, params=(username,))

    return df


# ──────────────────────────────────────────────
# 오답 문제 조회
# ──────────────────────────────────────────────

def get_incorrect_problems(username: str) -> list[dict]:
    """
    한 번도 정답을 맞히지 못한 문제 목록을 반환합니다.

    [알고리즘]
    1. learning_history에서 problem_id별로 그룹화
    2. SUM(is_correct) = 0 인 문제 ID만 추출 (= 항상 틀린 문제)
    3. CSV에서 해당 ID의 문제 원문 조회하여 반환

    [사용처]
    - tutor.py: GET /api/history/incorrect → 오답노트 기능
    """
    with get_db() as (conn, c):
        query = """
            SELECT problem_id FROM learning_history
            WHERE username = ?
            GROUP BY problem_id
            HAVING SUM(is_correct) = 0
        """
        incorrect_ids = pd.read_sql_query(
            query, conn, params=(username,)
        )['problem_id'].tolist()

    df = pd.read_csv(CSV_PATH)
    return df[df['ID'].astype(str).isin(incorrect_ids)].to_dict('records')


# ──────────────────────────────────────────────
# 시험 결과 저장
# ──────────────────────────────────────────────

def save_exam_result(username: str, unit: str, score: int,
                     total_questions: int, wrong_numbers: str, feedback: str):
    """
    단원 시험 완료 후 결과를 DB에 저장합니다.

    [파라미터]
    - wrong_numbers : JSON 문자열 예) "[2, 5, 7]"
    - feedback      : JSON 문자열 예) {"1": "잘 했어요", "2": "..."}

    [사용처]
    - tutor.py: POST /api/exam/save-result 엔드포인트
    """
    with get_db() as (conn, c):
        c.execute(
            """
            INSERT INTO exam_results
            (username, unit, score, total_questions, wrong_numbers, feedback)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, unit, score, total_questions, wrong_numbers, feedback)
        )


# ──────────────────────────────────────────────
# 시험 결과 조회
# ──────────────────────────────────────────────

def get_exam_results(username: str) -> list:
    """
    특정 학생의 모든 시험 결과를 시간 순으로 반환합니다.

    [사용처]
    - tutor.py: GET /api/exam/results → 성적 대시보드(section4.js)
    """
    with get_db() as (conn, c):
        c.execute(
            """
            SELECT id, unit, score, total_questions,
                   wrong_numbers, feedback, timestamp
            FROM exam_results
            WHERE username = ?
            ORDER BY timestamp ASC
            """,
            (username,)
        )
        rows = c.fetchall()

    return [
        {
            "id":              r[0],
            "unit":            r[1],
            "score":           r[2],
            "total_questions": r[3],
            "wrong_numbers":   r[4],
            "feedback":        r[5],
            "timestamp":       r[6]
        }
        for r in rows
    ]


# ──────────────────────────────────────────────
# 자유학습 채팅 메시지 저장
# ──────────────────────────────────────────────

def save_chat_message(username: str, role: str, content: str):
    """
    자유학습 채팅 메시지 1건을 DB에 저장합니다.

    [파라미터]
    - role    : 'user' (학생 입력) 또는 'assistant' (AI 응답)
    - content : 메시지 내용

    [사용처]
    - tutor.py: POST /api/free/chat 에서 2번 호출
      ① 학생 질문 저장 (role='user')
      ② AI 응답 저장  (role='assistant')
    """
    with get_db() as (conn, c):
        c.execute(
            "INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)",
            (username, role, content)
        )


# ──────────────────────────────────────────────
# 자유학습 채팅 기록 조회
# ──────────────────────────────────────────────

def get_chat_history(username: str, limit: int = 50) -> list:
    """
    특정 학생의 자유학습 채팅 기록을 최근 limit건 반환합니다.
    시간 오름차순(오래된 것 → 최신)으로 정렬하여 반환합니다.

    [정렬 방식]
    DESC로 최신 limit개를 가져온 후 → reversed()로 시간순 정렬
    이렇게 하는 이유: OFFSET 없이 최신 N건만 효율적으로 가져오기 위함

    [사용처]
    - tutor.py: GET /api/free/history → section2.js 대화창에 표시
    """
    with get_db() as (conn, c):
        c.execute(
            """
            SELECT role, content, timestamp
            FROM chat_history
            WHERE username = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (username, limit)
        )
        rows = c.fetchall()

    # DESC로 가져왔으므로 reversed()로 뒤집어서 시간순 정렬
    return [
        {"role": r[0], "content": r[1], "timestamp": r[2]}
        for r in reversed(rows)
    ]


# ──────────────────────────────────────────────
# 토큰 사용량 저장
# ──────────────────────────────────────────────

def save_token_usage(username: str, action: str,
                     prompt: int, completion: int,
                     total: int, cost: float = 0.0):
    """
    LLM API 호출 1회의 토큰 사용량과 비용을 DB에 저장합니다.

    [파라미터]
    - action     : 어떤 기능에서 호출했는지 (예: "개념설명", "채점", "AI자유학습")
    - prompt     : 입력 토큰 수 (사용자→LLM으로 보낸 텍스트 분량)
    - completion : 출력 토큰 수 (LLM이 생성한 응답 텍스트 분량)
    - total      : prompt + completion
    - cost       : 해당 호출의 USD 비용

    [사용처]
    - tutor.py: 각 LLM 엔드포인트에서 get_openai_callback()으로 토큰 계산 후 호출
    """
    with get_db() as (conn, c):
        c.execute(
            """
            INSERT INTO token_logs
            (username, action, prompt_tokens, completion_tokens, total_tokens, total_cost_usd)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, action, prompt, completion, total, cost)
        )


# ──────────────────────────────────────────────
# 토큰 사용량 통계 조회 (section5.js 용)
# ──────────────────────────────────────────────

def get_token_stats_from_db(username: str) -> dict:
    """
    token_logs 테이블에서 사용자의 누적 토큰 사용 통계를 집계합니다.

    [반환 형식] ← section5.js의 renderTokenPage()가 기대하는 구조
    {
        "prompt_tokens":     입력 토큰 합계,
        "completion_tokens": 출력 토큰 합계,
        "total_tokens":      전체 토큰 합계,
        "total_cost_usd":    총 비용 (달러),
        "total_cost_krw":    총 비용 (원화),
        "call_count":        총 API 호출 횟수,
        "history":           최근 10건 상세 기록 리스트,
        "source":            "database"
    }

    [history 항목 구조]
    {
        "action":     기능명 (예: "개념설명"),
        "prompt":     입력 토큰,
        "completion": 출력 토큰,
        "total":      합계 토큰,
        "cost_usd":   달러 비용,
        "ts":         시각 "HH:MM" 형식
    }

    [사용처]
    - tutor.py: GET /api/token/logs 엔드포인트
    """
    with get_db() as (conn, c):

        # ── 전체 합계 집계 ─────────────────────────
        # COALESCE: 값이 NULL이면 0으로 대체 (기록이 없을 때 오류 방지)
        c.execute(
            """
            SELECT
                COALESCE(SUM(prompt_tokens),     0),
                COALESCE(SUM(completion_tokens), 0),
                COALESCE(SUM(total_tokens),      0),
                COALESCE(SUM(total_cost_usd),    0.0),
                COUNT(*)
            FROM token_logs
            WHERE username = ?
            """,
            (username,)
        )
        agg = c.fetchone()

        # ── 최근 10건 상세 기록 ────────────────────
        c.execute(
            """
            SELECT action, prompt_tokens, completion_tokens,
                   total_tokens, total_cost_usd, timestamp
            FROM token_logs
            WHERE username = ?
            ORDER BY timestamp DESC
            LIMIT 10
            """,
            (username,)
        )
        rows = c.fetchall()

    prompt     = agg[0]
    completion = agg[1]
    total      = agg[2]
    cost_usd   = agg[3]
    call_count = agg[4]

    # timestamp 예: "2026-03-12 14:23:05" → "14:23" 추출
    history = [
        {
            "action":     r[0],
            "prompt":     r[1],
            "completion": r[2],
            "total":      r[3],
            "cost_usd":   round(r[4], 5),
            "ts":         r[5][11:16] if r[5] else "--:--",
        }
        for r in rows
    ]

    return {
        "prompt_tokens":     prompt,
        "completion_tokens": completion,
        "total_tokens":      total,
        "total_cost_usd":    round(cost_usd, 5),
        "total_cost_krw":    int(cost_usd * KRW_PER_USD),
        "call_count":        call_count,
        "history":           history,
        "source":            "database",   # LangSmith가 아닌 로컬 DB에서 읽음
    }
