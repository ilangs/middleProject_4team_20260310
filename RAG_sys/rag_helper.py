import chromadb
import pandas as pd
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

# 1. DB 및 임베딩 설정 (OpenAI 모델 사용)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

# 2. ChromaDB 클라이언트 설정
client = chromadb.PersistentClient(path="database/vector_store")

def build_vector_db():
    """CSV 데이터를 배치 단위로 쪼개어 벡터 DB에 저장합니다."""
    df = pd.read_csv('data/processed/math_tutor_dataset.csv')
    
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
        # metadata 내의 NaN(결측치)을 처리하지 않으면 오류가 날 수 있어 보강합니다.
        metadatas = batch_df[['ID', '단원', '난이도', '풀이및정답']].fillna("없음").to_dict('records')
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