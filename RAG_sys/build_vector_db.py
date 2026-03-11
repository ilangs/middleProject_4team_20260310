import sys
import os

# 현재 파일 위치를 기준으로 최상위 폴더(root) 경로를 구해 시스템 경로에 추가합니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from rag_helper import build_vector_db

if __name__ == "__main__":
    print("📋 벡터 DB 인덱싱을 시작합니다. 잠시만 기다려 주세요...")
    try:
        build_vector_db()
        print("✨ 인덱싱 완료! 이제 RAG 검색 기능을 사용할 수 있습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")