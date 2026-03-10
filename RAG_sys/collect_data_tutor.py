import zipfile
import json
import os
import pandas as pd

root_dir = './'
problems = {}
answers = {}

print("🚀 ZIP 파일 내부에서 문제와 정답을 찾아 통합을 시작합니다...")

# 1. 모든 폴더와 ZIP 파일을 훑습니다.
for root, dirs, files in os.walk(root_dir):
    for filename in files:
        if filename.endswith('.zip'):
            zip_path = os.path.join(root, filename)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    # zip 안의 json 파일들만 골라냅니다.
                    json_names = [n for n in z.namelist() if n.endswith('.json')]
                    
                    for json_name in json_names:
                        with z.open(json_name) as f:
                            # BOM 오류 방지를 위해 utf-8-sig로 디코딩합니다.
                            content = f.read().decode('utf-8-sig')
                            data = json.loads(content)
                            qid = data.get('id')
                            
                            if not qid: continue

                            # A. 문제 데이터인 경우 (OCR_info 존재)
                            if 'OCR_info' in data:
                                problems[qid] = {
                                    'topic': data['question_info'][0]['question_topic_name'],
                                    'question': data['OCR_info'][0]['question_text'],
                                    'difficulty': data['question_info'][0]['question_difficulty']
                                }
                            # B. 정답 데이터인 경우 (answer_info 존재)
                            elif 'answer_info' in data:
                                answers[qid] = data['answer_info'][0]['answer_text']
                                
            except Exception as e:
                # 특정 파일 오류 시 건너뛰고 계속 진행합니다.
                continue

# 2. 문제와 정답 매칭 (ID 기준)
final_list = []
for qid, p_info in problems.items():
    if qid in answers:
        final_list.append({
            'ID': qid,
            '단원': p_info['topic'],
            '난이도': p_info['difficulty'],
            '문제': p_info['question'],
            '풀이및정답': answers[qid]
        })

# 3. 결과 저장
if final_list:
    df = pd.DataFrame(final_list)
    df.to_csv('math_tutor_dataset.csv', index=False, encoding='utf-8-sig')
    print(f"✨ 통합 성공! 총 {len(final_list)}개의 세트가 저장되었습니다.")
else:
    print("⚠️ 여전히 데이터를 찾지 못했습니다. 경로 탐색 범위를 확인해 보세요.")
    print(f"현재 찾은 문제 수: {len(problems)}, 정답 수: {len(answers)}")