import os
import json
import requests
from datetime import datetime

# 1. 설정 및 경로
API_KEY = os.getenv('FSS_API_KEY')
DATA_FILE = 'data.json'

def fetch_fss_data(product_type):
    """
    금감원 API에서 데이터를 가져옵니다.
    product_type: 'deposit' (예금) 또는 'savings' (적금)
    """
    if not API_KEY:
        print("API 키가 없습니다. GitHub Secrets 설정을 확인하세요.")
        return []

    # API 주소 결정
    api_url_map = {
        'deposit': 'depositProductsSearch.json',
        'savings': 'savingProductsSearch.json'
    }
    
    url = f"http://finlife.fss.or.kr/api/{api_url_map[product_type]}?auth={API_KEY}&topFinGrpNo=020000&pageNo=1"
    
    try:
        res = requests.get(url)
        data = res.json()
        
        base_list = data.get('result', {}).get('baseList', [])
        option_list = data.get('result', {}).get('optionList', [])

        # 12개월물 기준 최고 우대금리(intr_rate2) 추출
        rate_dict = {}
        for opt in option_list:
            if opt['save_trm'] == "12": # 12개월물 기준
                p_code = opt['fin_prdt_cd']
                rate = float(opt['intr_rate2'] or 0)
                # 동일 상품 중 가장 높은 금리 선택
                if p_code not in rate_dict or rate > rate_dict[p_code]:
                    rate_dict[p_code] = rate

        final_list = []
        for base in base_list:
            p_code = base['fin_prdt_cd']
            if p_code in rate_dict:
                final_list.append({
                    "bank": base['kor_co_nm'],
                    "name": base['fin_prdt_nm'],
                    "max": rate_dict[p_code],
                    "type": product_type
                })
        return final_list
    except Exception as e:
        print(f"{product_type} 데이터 호출 중 오류 발생: {e}")
        return []

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
    updated = False

    # 예금과 적금 데이터를 모두 가져옴
    all_latest_data = fetch_fss_data('deposit') + fetch_fss_data('savings')

    for latest in all_latest_data:
        # DB에서 같은 은행, 같은 상품명, 같은 타입(예금/적금)을 찾음
        target = next((item for item in db if 
                       item['bank'] == latest['bank'] and 
                       item['name'] == latest['name'] and 
                       item['type'] == latest['type']), None)
        
        if target:
            # 기존 상품: 금리 변동 시 히스토리 추가
            if float(target['max']) != float(latest['max']):
                print(f"[{latest['type'].upper()} 변동] {latest['bank']} : {target['max']}% -> {latest['max']}%")
                target['max'] = latest['max']
                target['history'].append({"date": today, "rate": latest['max']})
                updated = True
        else:
            # 새 상품: DB에 추가
            print(f"[{latest['type'].upper()} 신규] {latest['bank']} - {latest['name']}")
            new_id = max([i['id'] for i in db], default=0) + 1
            new_item = {
                "id": new_id,
                "bank": latest['bank'],
                "name": latest['name'],
                "type": latest['type'],
                "base": latest['max'],
                "max": latest['max'],
                "term": 12,
                "history": [{"date": today, "rate": latest['max']}]
            }
            db.append(new_item)
            updated = True

    if updated:
        # 금리 높은 순으로 정렬하여 저장 (웹에서 TOP 10 보여주기 편하게)
        db.sort(key=lambda x: x['max'], reverse=True)
        save_db(db)
        print(f"[{today}] 업데이트 완료!")
    else:
        print(f"[{today}] 변동 사항 없음.")

if __name__ == "__main__":
    update_process()
