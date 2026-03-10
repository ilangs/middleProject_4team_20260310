import pandas as pd
from openai import OpenAI
import os

# ==========================================
# 환경 설정 및 API 키, 파일 경로
# ==========================================
client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))

# 현재 파일(csv_refiner.py)의 위치를 기준으로 2단계 위인 최상위 폴더를 찾습니다.
# (위치: middleProject_4team_202603_modified -> RAG_sys -> csv_refiner.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# BASE_DIR을 기준으로 절대 경로 결합
INPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "math_tutor_dataset_before.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "math_tutor_dataset.csv")

def process_solution_with_llm(text: str) -> tuple:
    """
    LLM을 사용하여 기존 '풀이및정답' 텍스트에서 
    정답만 추출하고, 풀이를 친절한 선생님 톤으로 재작성합니다.
    """
    prompt = f"""
    너는 초등학생에게 수학을 가르치는 다정하고 친절한 수학 선생님 '루미'야.
    아래 주어진 원본 수학 문제의 '풀이 및 정답' 텍스트를 분석해서 다음 두 가지를 해줘.
    
    1. 최종 '정답'만 정확하게 추출할 것 (예: 785, 26(cm) 등)
    2. '풀이' 과정을 초등학생이 이해하기 쉽도록 아주 친절하고 구어체적인 톤으로 재작성할 것 (예: "자! 일의 자리부터 더해볼까?")

    원본 텍스트:
    {text}

    반드시 아래와 같이 '|' 기호로만 구분해서 응답해줘. 다른 군더더기 말은 넣지 마.
    정답|재작성된친절한풀이
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        result = response.choices[0].message.content.strip()
        
        # '|' 기준으로 정답과 풀이 분리
        ans, explanation = result.split('|', 1)
        return ans.strip(), explanation.strip()
        
    except Exception as e:
        print(f"⚠️ 처리 오류 발생: {e}")
        return "추출 실패", text # 오류 시 원본 반환

def main():
    print(f"[{INPUT_CSV}] 파일을 읽어옵니다...")
    df = pd.read_csv(INPUT_CSV)
    
    answers = []
    explanations = []
    
    print("LLM을 통해 정답 추출 및 풀이 재작성을 시작합니다. (시간이 조금 걸릴 수 있습니다)")
    for idx, row in df.iterrows():
        original_text = str(row.get('풀이및정답', ''))
        
        if not original_text or original_text.lower() == 'nan':
            answers.append("")
            explanations.append("")
            continue
            
        ans, exp = process_solution_with_llm(original_text)
        answers.append(ans)
        explanations.append(exp)
        
        print(f" - {idx+1}/{len(df)} 행 처리 완료")
        
    # 새로운 컬럼 추가
    df['정답'] = answers
    df['풀이'] = explanations
    
    # ID 체계를 'grade3_1st_step_01' 형태로 일괄 변경하고 싶다면 아래 주석을 해제하세요.
    # df['ID'] = [f"grade3_1st_step_{i:02d}" for i in range(1, len(df)+1)]
    
    # 불필요한 기존 컬럼 삭제 및 순서 재배치
    if '풀이및정답' in df.columns:
        df = df.drop(columns=['풀이및정답'])
        
    # 최종 데이터프레임 컬럼 순서 정렬
    df = df[['ID', '단원', '난이도', '문제', '정답', '풀이']]
    
    # 새 CSV로 저장 (한글 깨짐 방지를 위해 utf-8-sig 사용)
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"🎉 변환 완료! [{OUTPUT_CSV}] 파일이 생성되었습니다.")

if __name__ == "__main__":
    main()