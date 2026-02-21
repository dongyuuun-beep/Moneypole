import os
import json
import requests
from datetime import datetime

# 1. 설정 및 경로
API_KEY = os.getenv('FSS_API_KEY')
DATA_FILE = 'data.json'

def fetch_fss_data(product_type):
    if not API_KEY:
        print("API_KEY가 설정되지 않았습니다. GitHub Secrets를 확인하세요.")
        return []

    # [수정] 정확한 API 엔드포인트 경로 설정
    # 정기예금: depositProductsSearch.json / 적금: savingProductsSearch.json
    filename = "depositProductsSearch.json" if product_type == 'deposit' else "savingProductsSearch.json"
    url = f"http://finlife.fss.or.kr/api/{filename}"
    
    # [수정] 필수 파라미터 세트
    params = {
        'auth': API_KEY,
        'topFinGrpNo': '020000', # 권역코드: 은행
        'pageNo': '1'
    }
    
    try:
        # API 호출 (headers를 추가하여 브라우저 요청처럼 위장)
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, params=params, headers=headers, timeout=15)
        
        # 응답 텍스트가 "페이지가 없거나..."를 포함하는지 체크
        if "페이지가 없거나" in res.text or "잘못된 경로" in res.text:
            print(f"{product_type} 호출 경로 오류: 서버가 잘못된 경로라고 응답했습니다.")
            return []

        if res.status_code != 200:
            print(f"API 서버 응답 오류: {res.status_code}")
            return []

        data = res.json()
        
        if 'result' not in data:
            print(f"데이터 구조 오류: {data.get('message', '결과값이 없습니다.')}")
            return []

        base_list = data.get('result', {}).get('baseList', [])
        option_list = data.get('result', {}).get('optionList', [])

        # 12개월 기준 최고 금리 추출 로직
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
        print(f"{product_type} 데이터 수집 완료: {len(final_list)}건")
        return final_list

    except Exception as e:
        print(f"{product_type} 처리 중 오류 발생: {str(e)}")
        return []

# --- 아래 load_db, save_db, update_process 함수는 이전과 동일 ---
def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except: return []
    return []

def save_db(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_process():
    db = load_db()
    today = datetime.now().strftime('%Y-%m-%d')
    updated = False
    print("금리 데이터 업데이트 프로세스 시작")
    
    all_latest_data = fetch_fss_data('deposit') + fetch_fss_data('savings')
    if not all_latest_data:
        print("수집된 데이터가 없습니다.")
        return

    for latest in all_latest_data:
        target = next((item for item in db if item['bank'] == latest['bank'] and item['name'] == latest['name'] and item['type'] == latest['type']), None)
        if target:
            if float(target['max']) != float(latest['max']):
                target['max'] = latest['max']
                target['history'].append({"date": today, "rate": latest['max']})
                updated = True
        else:
            new_id = max([i['id'] for i in db], default=0) + 1
            db.append({
                "id": new_id, "bank": latest['bank'], "name": latest['name'], "type": latest['type'],
                "base": latest['max'], "max": latest['max'], "term": 12,
                "history": [{"date": today, "rate": latest['max']}]
            })
            updated = True

    if updated:
        db.sort(key=lambda x: x['max'], reverse=True)
        save_db(db)
        print(f"[{today}] 데이터 저장 완료")
    else:
        print(f"[{today}] 변경 사항 없음")

if __name__ == "__main__":
    update_process()
