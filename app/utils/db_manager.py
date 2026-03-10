import sqlite3
import os
import pandas as pd
import bcrypt
from contextlib import contextmanager

DB_PATH = 'database/user_db.sqlite'
CSV_PATH = 'data/processed/math_tutor_dataset.csv'


@contextmanager
def get_db():
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


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


# ──────────────────────────────────────────────
# DB 초기화
# ──────────────────────────────────────────────

def init_db():
    with get_db() as (conn, c):

        c.execute("""
            CREATE TABLE IF NOT EXISTS users
            (username TEXT PRIMARY KEY,
             password TEXT,
             current_unit TEXT)
        """)

        c.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in c.fetchall()]

        if "nickname" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN nickname TEXT")

        if "character" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN character TEXT")

        c.execute("""
            CREATE TABLE IF NOT EXISTS learning_history
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT,
             problem_id TEXT,
             unit TEXT,
             is_correct INTEGER,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ⭐ 시험 결과 테이블 (주석님 코드 추가)
        c.execute("""
            CREATE TABLE IF NOT EXISTS exam_results
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT,
             unit TEXT,
             score INTEGER,
             total_questions INTEGER,
             wrong_numbers TEXT,
             feedback TEXT,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

        # ──────────────────────────────────────
        # 자유학습 채팅 기록 테이블
        # role: 'user'(학생) 또는 'assistant'(AI)
        # ──────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_history
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             username TEXT NOT NULL,
             role TEXT NOT NULL,
             content TEXT NOT NULL,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        """)

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
        "username": row[0],
        "password": row[1],
        "current_unit": row[2],
        "nickname": row[3],
        "character": row[4]
    }


# ──────────────────────────────────────────────
# 유저 생성
# ──────────────────────────────────────────────

def create_user(username: str, plain_password: str, nickname: str, character: str) -> bool:

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
        return False


# ──────────────────────────────────────────────
# 학습 결과 저장
# ──────────────────────────────────────────────

def save_history(username: str, problem_id: str, unit: str, is_correct: bool):

    with get_db() as (conn, c):

        c.execute(
            "INSERT INTO learning_history (username, problem_id, unit, is_correct) VALUES (?, ?, ?, ?)",
            (username, str(problem_id), unit, 1 if is_correct else 0)
        )


# ──────────────────────────────────────────────
# 학습 기록 조회
# ──────────────────────────────────────────────

def get_user_history(username: str) -> pd.DataFrame:

    with get_db() as (conn, c):

        query = "SELECT unit, is_correct, timestamp FROM learning_history WHERE username = ?"

        df = pd.read_sql_query(query, conn, params=(username,))

    return df


# ──────────────────────────────────────────────
# 오답 문제 조회
# ──────────────────────────────────────────────

def get_incorrect_problems(username: str) -> list[dict]:

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


def delete_user(username: str):

    with get_db() as (conn, c):

        c.execute(
            "DELETE FROM users WHERE username = ?",
            (username,)
        )


# ──────────────────────────────────────────────
# 시험 결과 저장 (주석님 기능)
# ──────────────────────────────────────────────

def save_exam_result(username: str, unit: str, score: int, total_questions: int,
                     wrong_numbers: str, feedback: str):

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

    with get_db() as (conn, c):

        c.execute(
            """
            SELECT id, unit, score, total_questions, wrong_numbers, feedback, timestamp
            FROM exam_results
            WHERE username = ?
            ORDER BY timestamp ASC
            """,
            (username,)
        )

        rows = c.fetchall()

    return [
        {
            "id": r[0],
            "unit": r[1],
            "score": r[2],
            "total_questions": r[3],
            "wrong_numbers": r[4],
            "feedback": r[5],
            "timestamp": r[6]
        }
        for r in rows
    ]


# ──────────────────────────────────────────────
# 자유학습 채팅 메시지 저장
# ──────────────────────────────────────────────

def save_chat_message(username: str, role: str, content: str):
    """
    자유학습 채팅 메시지 1건을 DB에 저장합니다.
    - username: 로그인한 학생 아이디
    - role: 'user'(학생) 또는 'assistant'(AI)
    - content: 메시지 내용
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
    특정 학생의 자유학습 채팅 기록을 최근 limit건만 가져옵니다.
    시간 순서대로(오래된 것 → 최신) 정렬하여 반환합니다.
    """
    with get_db() as (conn, c):
        # 최신순으로 limit개를 가져온 뒤 뒤집어서 시간순 정렬
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

    # 시간 역순으로 가져왔으므로 다시 뒤집어서 시간순 정렬
    return [
        {"role": r[0], "content": r[1], "timestamp": r[2]}
        for r in reversed(rows)
    ]