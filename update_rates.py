import os
import json
import requests
from datetime import datetime

# 1. 설정 및 경로
API_KEY = os.getenv('FSS_API_KEY')
DATA_FILE = 'data.json'

def fetch_fss_data():
    """금감원 API에서 예금 데이터를 가져와서 정제합니다."""
    if not API_KEY:
        print("API 키가 없습니다. 환경변수를 확인하세요.")
        return []

    # 정기예금(deposit) API 호출
    url = f"http://finlife.fss.or.kr/api/depositProductsSearch.json?auth={API_KEY}&topFinGrpNo=020000&pageNo=1"
    res = requests.get(url)
    data = res.json()
    
    base_list = data.get('result', {}).get('baseList', [])
    option_list = data.get('result', {}).get('optionList', [])

    # 금리 정보(optionList)를 상품코드별로 정리 (12개월 기준 최고금리 추출)
    rate_dict = {}
    for opt in option_list:
        p_code = opt['fin_prdt_cd']
        intr_rate2 = float(opt['intr_rate2'] or 0) # 우대금리 포함 최고금리
        
        # 12개월물 기준이거나 아직 해당 상품코드가 저장되지 않았다면 저장
        if opt['save_trm'] == "12":
            rate_dict[p_code] = intr_rate2

    # 상품명과 금리를 하나로 합치기
    latest_data = []
    for base in base_list:
        p_code = base['fin_prdt_cd']
        if p_code in rate_dict:
            latest_data.append({
                "bank": base['kor_co_nm'],
                "name": base['fin_prdt_nm'],
                "max": rate_dict[p_code],
                "p_code": p_code # 비교를 위한 고유 코드
            })
    return latest_data

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
    latest_api_data = fetch_fss_data() # API에서 최신 데이터 가져오기
    today = datetime.now().strftime('%Y-%m-%d')
    updated = False

    for latest in latest_api_data:
        # DB에서 같은 은행 & 같은 상품명을 찾음
        target = next((item for item in db if item['bank'] == latest['bank'] and item['name'] == latest['name']), None)
        
        if target:
            # 1. 기존 상품이 있을 경우: 금리 변동 체크
            if float(target['max']) != float(latest['max']):
                print(f"변동 감지 [{latest['bank']}]: {target['max']}% -> {latest['max']}%")
                target['max'] = latest['max']
                target['history'].append({"date": today, "rate": latest['max']})
                updated = True
        else:
            # 2. 새로운 상품이 발견되었을 경우: DB에 새로 추가
            print(f"새 상품 발견: {latest['bank']} - {latest['name']}")
            new_item = {
                "id": len(db) + 1,
                "bank": latest['bank'],
                "name": latest['name'],
                "type": "deposit", # 기본값 예금
                "base": latest['max'], # API 구조상 단순화를 위해 동일하게 세팅
                "max": latest['max'],
                "term": 12,
                "history": [{"date": today, "rate": latest['max']}]
            }
            db.append(new_item)
            updated = True

    if updated:
        save_db(db)
        print("데이터 업데이트 완료.")
    else:
        print("변동 사항이 없습니다.")

if __name__ == "__main__":
    update_process()
