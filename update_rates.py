import os
import json
import requests
from datetime import datetime

API_KEY = os.getenv('FSS_API_KEY')
DATA_FILE = 'data.json'

def fetch_fss_data(product_type):
    if not API_KEY:
        print("API_KEY가 없습니다.")
        return []

    # 주소 끝에 .json이 붙어 있는지, 오타는 없는지 다시 확인한 정석 주소
    if product_type == 'deposit':
        url = "http://finlife.fss.or.kr/api/depositProductsSearch.json"
    else:
        url = "http://finlife.fss.or.kr/api/savingProductsSearch.json"
    
    # 파라미터를 딕셔너리로 넘기면 requests가 알아서 ?auth=... 형태로 붙여줍니다.
    params = {
        'auth': API_KEY,
        'topFinGrpNo': '020000',
        'pageNo': '1'
    }

    try:
        # 응답을 확인하기 위해 timeout을 충분히 줍니다.
        response = requests.get(url, params=params, timeout=20)
        
        # 서버에서 보낸 실제 텍스트 내용을 로그에 찍어 확인해봅니다 (디버깅용)
        if "페이지가 없거나" in response.text:
            print(f"{product_type} 실패: 아직 API 키가 서버 전체에 반영되지 않았거나 경로가 거부되었습니다.")
            return []

        data = response.json()
        result = data.get('result', {})

        if result.get('err_cd') != '000':
            print(f"API 에러: {result.get('err_msg')}")
            return []

        base_list = result.get('baseList', [])
        option_list = result.get('optionList', [])

        rate_dict = {}
        for opt in option_list:
            if str(opt.get('save_trm')) == "12":
                p_code = opt.get('fin_prdt_cd')
                rate = float(opt.get('intr_rate2') or 0)
                if p_code not in rate_dict or rate > rate_dict[p_code]:
                    rate_dict[p_code] = rate

        final_data = []
        for base in base_list:
            p_code = base.get('fin_prdt_cd')
            if p_code in rate_dict:
                final_data.append({
                    "bank": base.get('kor_co_nm'),
                    "name": base.get('fin_prdt_nm'),
                    "max": rate_dict[p_code],
                    "type": product_type
                })
        
        print(f"{product_type} 성공: {len(final_data)}건 수집 완료")
        return final_data

    except Exception as e:
        print(f"{product_type} 예외 발생: {str(e)}")
        return []

# --- load_db, save_db, update_process는 이전과 동일 ---
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
    latest_api = fetch_fss_data('deposit') + fetch_fss_data('savings')
    
    if not latest_api:
        print("수집 데이터 없음. 종료.")
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
        print("데이터 업데이트 완료")
    else:
        print("변동 사항 없음")

if __name__ == "__main__":
    update_process()
