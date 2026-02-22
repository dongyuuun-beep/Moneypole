import requests # 웹페이지 통신 및 API 호출을 위한 라이브러리입니다.
import json # JSON 데이터를 다루기 위한 라이브러리입니다.
import os # 시스템 환경변수(API 키 등)를 불러오기 위한 라이브러리입니다.
from datetime import datetime # 금리 변동 이력에 날짜를 기록하기 위한 라이브러리입니다.

# 1. 환경 설정 및 기본 변수 정의
API_KEY = os.environ.get('FSS_API_KEY') # GitHub Secrets에서 API 키를 가져옵니다.
DATA_FILE = 'data.json' # 데이터가 누적되어 저장될 파일명입니다.
FIN_GROUPS = ["020000", "030300"] # 020000: 시중은행, 030300: 저축은행 코드입니다.

# 2. 기존 데이터 로드 함수 (히스토리 유지를 위해 필수)
def load_existing_data():
    if os.path.exists(DATA_FILE): # 데이터 파일이 이미 존재하는지 확인합니다.
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

# 3. [API] 예금/적금 전체 페이지 수집 함수
def fetch_all_products(p_type):
    endpoint = "depositProductsSearch.json" if p_type == "deposit" else "savingProductsSearch.json"
    all_products = []
    
    if not API_KEY:
        print(f"⚠️ API_KEY가 설정되지 않아 {p_type} 수집을 건너뜜")
        return []

    for group in FIN_GROUPS:
        page_no = 1
        while True:
            url = f"http://finlife.fss.or.kr/finlifeapi/{endpoint}?auth={API_KEY}&topFinGrpNo={group}&pageNo={page_no}"
            try:
                res = requests.get(url, timeout=10)
                if res.status_code != 200: break
                
                data = res.json().get('result', {})
                base_list = data.get('baseList', [])
                opt_list = data.get('optionList', [])
                
                rate_map = {}
                for opt in opt_list:
                    code = opt['fin_prdt_cd']
                    if str(opt['save_trm']) == "12":
                        rate_map[code] = {
                            "max": float(opt['intr_rate2'] or 0),
                            "base": float(opt['intr_rate'] or 0),
                            "intr_type": opt['intr_rate_type']
                        }
                
                for base in base_list:
                    code = base['fin_prdt_cd']
                    if code in rate_map:
                        all_products.append({
                            "id": code,
                            "bank": base['kor_co_nm'].strip(),
                            "name": base['fin_prdt_nm'].strip(),
                            "spcl_cnd": base.get('spcl_cnd', '').strip(),
                            "max": rate_map[code]['max'],
                            "base": rate_map[code]['base'],
                            "intr_type": rate_map[code]['intr_type'],
                            "type": p_type
                        })
                
                max_page = int(data.get('max_page_no', 1))
                if page_no >= max_page: break
                page_no += 1
            except Exception as e:
                print(f"⚠️ {p_type} API 호출 중 에러: {e}")
                break
            
    return all_products

# 5. 메인 실행 로직 (API 수집 및 히스토리 업데이트)
def main():
    master_data = load_existing_data()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # [수동 관리 품목 보존] 파킹통장(parking)을 포함하여 직접 관리하는 유형들을 보존합니다.
    manual_types = ['parking', 'cma', 'bill', 'els', 'bond']
    preserved_data = [item for item in master_data if item.get('type') in manual_types]
    
    print("🚀 API(예/적금) 데이터 수집 시작...")
    # 주석을 해제하여 정식 API로부터 데이터를 가져옵니다.
    api_deposits = fetch_all_products("deposit")
    api_savings = fetch_all_products("savings")
    
    # 크롤링 없이 API로 가져온 데이터만 사용합니다.
    all_new_data = api_deposits + api_savings
    updated_items = []
    
    for new_item in all_new_data:
        existing = next((item for item in master_data if item.get('id') == new_item['id']), None)
        
        history = []
        if existing and 'history' in existing:
            history = existing['history']
            if history and history[-1]['rate'] != new_item['max']:
                history.append({"date": today, "rate": new_item['max']})
        else:
            history = [{"date": today, "rate": new_item['max']}]
            
        new_item['history'] = history
        updated_items.append(new_item)
        
    final_output = preserved_data + updated_items

    # [방어 로직] API 데이터 수집이 실패하여 건수가 너무 적으면 덮어쓰지 않습니다.
    if len(all_new_data) < 10:
        print(f"❌ 수집된 API 데이터가 너무 적습니다 ({len(all_new_data)}건). 파일을 업데이트하지 않습니다.")
        return

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 업데이트 완료! (수동 보존: {len(preserved_data)}건, API 갱신: {len(updated_items)}건)")

if __name__ == "__main__":
    main()
