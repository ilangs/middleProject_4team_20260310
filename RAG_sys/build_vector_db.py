import sys
import os

# 현재 위치가 scripts 폴더이므로, 상위 폴더(root)를 경로에 추가해야 utils를 불러올 수 있습니다.
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from rag_helper import build_vector_db

if __name__ == "__main__":
    print("📋 벡터 DB 인덱싱을 시작합니다. 잠시만 기다려 주세요...")
    try:
        build_vector_db()
        print("✨ 인덱싱 완료! 이제 RAG 검색 기능을 사용할 수 있습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        