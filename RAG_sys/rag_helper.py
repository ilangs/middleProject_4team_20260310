import chromadb
import pandas as pd
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 🌟 절대 경로 세팅
# 현재 파일(rag_helper.py)을 기준으로 2단계 위인 최상위 폴더를 찾습니다.
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DB 저장 폴더와 CSV 파일 경로를 절대 경로로 안전하게 결합
DB_PATH = os.path.join(BASE_DIR, "database", "vector_store")
CSV_PATH = os.path.join(BASE_DIR, "data", "processed", "math_tutor_dataset.csv")


# 1. DB 및 임베딩 설정 (OpenAI 모델 사용)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

# 2. ChromaDB 클라이언트 설정 (절대 경로 적용)
client = chromadb.PersistentClient(path=DB_PATH)

def build_vector_db():
    """CSV 데이터를 배치 단위로 쪼개어 벡터 DB에 저장합니다."""
    # 절대 경로로 CSV 파일 읽기
    df = pd.read_csv(CSV_PATH)
    
    collection = client.get_or_create_collection(
        name="math_problems", 
        embedding_function=openai_ef
    )
    
    # 1. 배치 사이즈 설정 (한 번에 100개씩 처리)
    batch_size = 100
    total_len = len(df)
    
    print(f"📦 총 {total_len}개의 데이터를 {batch_size}개씩 나누어 등록을 시작합니다...")

    for i in range(0, total_len, batch_size):
        # 현재 배치 구간 설정
        batch_df = df.iloc[i : i + batch_size]
        
        documents = batch_df['문제'].tolist()
        # 분리된 정답과 풀이 컬럼을 사용하도록 반영됨
        metadatas = batch_df[['ID', '단원', '난이도', '정답', '풀이']].fillna("없음").to_dict('records')
        ids = batch_df['ID'].astype(str).tolist()
        
        try:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"✅ [{i + len(batch_df)}/{total_len}] 등록 완료...")
        except Exception as e:
            print(f"❌ {i}번째 배치 등록 중 오류 발생: {e}")
            continue

    print(f"✨ 모든 데이터({total_len}개)가 벡터 DB에 성공적으로 등록되었습니다!")

def search_problems(query_text, n_results=1):
    """학생의 질문과 가장 유사한 문제를 찾아옵니다."""
    collection = client.get_collection(name="math_problems", embedding_function=openai_ef)
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    return results