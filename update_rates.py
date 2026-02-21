import json
import os
from datetime import datetime

# 데이터 파일 경로
DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_product_rate(p_id, new_rate):
    """
    상품 ID와 새로운 금리를 입력받아 변동이 있을 때만 history를 누적합니다.
    """
    products = load_data()
    today = datetime.now().strftime('%Y-%m-%d')
    updated = False

    for p in products:
        if p['id'] == p_id:
            # 기존 금리와 다를 경우에만 히스토리 추가
            if p.get('max') != new_rate:
                print(f"[{p['bank']}] 금리 변동 감지: {p['max']}% -> {new_rate}%")
                
                # 히스토리에 변동일과 금리 추가
                if 'history' not in p: p['history'] = []
                p['history'].append({"date": today, "rate": new_rate})
                
                # 현재 최고 금리 업데이트
                p['max'] = new_rate
                updated = True
            else:
                print(f"[{p['bank']}] 금리 변동 없음. 기록을 유지합니다.")
            break
    
    if updated:
        save_data(products)
        print("data.json에 성공적으로 저장되었습니다.")
    else:
        print("변경사항이 없어 파일을 저장하지 않았습니다.")

# --- 메뉴얼 등록/수정 사용 예시 ---
# 사용법: update_product_rate(상품ID, 새로운금리)
if __name__ == "__main__":
    # 예: ID 1번 상품의 금리가 4.5%로 올랐을 때 실행
    update_product_rate(1, 4.5)
