import json
import os
from datetime import datetime

# 데이터 파일 경로
DATA_FILE = 'data.json'

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_db(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_process():
    db = load_db()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # [매뉴얼 입력 예시] 실제로는 외부 API나 CSV에서 읽어올 수 있습니다.
    # 예시: 금리가 변동된 최신 리스트 정보를 여기에 입력합니다.
latest_data = [
        {"id": 1, "max": 4.5}, # 국민은행 예금 금리가 4.5로 올랐다고 가정
        {"id": 2, "max": 5.2}, 
    ]

    updated = False
    for latest in latest_data:
        for item in db:
            if item['id'] == latest['id']:
                # 기존 금리와 다를 경우에만 history에 추가
                if item['max'] != latest['max']:
                    print(f"변동 감지: {item['bank']} {item['max']}% -> {latest['max']}%")
                    item['max'] = latest['max']
                    item['history'].append({"date": today, "rate": latest['max']})
                    updated = True
                break
    
    if updated:
        save_db(db)
        print("금리 변동 사항이 저장되었습니다.")
    else:
        print("변동 사항이 없습니다.")

if __name__ == "__main__":
    update_process()
