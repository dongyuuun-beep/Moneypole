import os
import json
import requests
from datetime import datetime

API_KEY = os.getenv('FSS_API_KEY')
DATA_FILE = 'data.json'

def fetch_fss_data(product_type):
    if not API_KEY:
        print("API_KEY가 없습니다. GitHub Secrets 설정을 확인하세요.")
        return []

    # [수정됨] 정확한 공식 API 경로 반영 (/finlifeapi/)
    api_name = "depositProductsSearch.json" if product_type == 'deposit' else "savingProductsSearch.json"
    url = f"http://finlife.fss.or.kr/finlifeapi/{api_name}"
    
    params = {
        'auth': API_KEY,
        'topFinGrpNo': '020000', # 은행
        'pageNo': '1'
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        
        # 만약 여전히 HTML이 온다면 출력 (이제 올 일 없을 겁니다!)
        if "<html>" in response.text or "잘못된 경로" in response.text:
            print(f"❌ {product_type} 경로 오류. 주소나 키를 다시 확인하세요.")
            return []

        data = response.json()
        result = data.get('result', {})

        if result.get('err_cd') != '000':
            print(f"⚠️ API 에러: {result.get('err_msg')}")
            return []

        base_list = result.get('baseList', [])
        option_list = result.get('optionList', [])

        # 12개월 금리 추출
        rate_dict = {}
        for opt in option_list:
            if str(opt.get('save_trm')) == "12":
                p_code = opt.get('fin_prdt_cd')
                rate = float(opt.get('intr_rate2') or 0)
                if p_code not in rate_dict or rate > rate_dict[p_code]:
                    rate_dict[p_code] = rate

        final_list = []
        for base in base_list:
            p_code = base.get('fin_prdt_cd')
            if p_code in rate_dict:
                final_list.append({
                    "bank": base.get('kor_co_nm'),
                    "name": base.get('fin_prdt_nm'),
                    "max": rate_dict[p_code],
                    "type": product_type
                })
        print(f"✅ {product_type} 수집 성공: {len(final_list)}건")
        return final_list

    except Exception as e:
        print(f"❌ {product_type} 처리 중 오류: {str(e)}")
        return []

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except: return []
    return []

def save_db(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_process():
    db = load_db()
    today = datetime.now().strftime('%Y-%m-%d')
    print("🚀 금리 업데이트 시작...")
    
    latest_api = fetch_fss_data('deposit') + fetch_fss_data('savings')
    
    if not latest_api:
        print("⚠️ 수집된 데이터가 없어 종료합니다.")
        return

    updated = False
    for latest in latest_api:
        target = next((i for i in db if i['bank'] == latest['bank'] and i['name'] == latest['name'] and i['type'] == latest['type']), None)
        
        if target:
            if float(target['max']) != float(latest['max']):
                target['max'] = latest['max']
                target['history'].append({"date": today, "rate": latest['max']})
                updated = True
        else:
            new_id = max([i['id'] for i in db], default=0) + 1
            db.append({
                "id": new_id, "bank": latest['bank'], "name": latest['name'], "type": latest['type'],
                "max": latest['max'], "term": 12,
                "history": [{"date": today, "rate": latest['max']}]
            })
            updated = True

    if updated:
        db.sort(key=lambda x: x['max'], reverse=True)
        save_db(db)
        print(f"🎉 [{today}] 업데이트 및 저장 완료!")
    else:
        print(f"😴 [{today}] 변동 사항 없음.")

if __name__ == "__main__":
    update_process()
