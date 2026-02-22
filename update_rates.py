import requests
import json
import os
from datetime import datetime

# 1. 환경 설정 및 기본 변수 정의
API_KEY = os.environ.get('FSS_API_KEY')
DATA_FILE = 'data.json'
FIN_GROUPS = ["020000", "030300"]

# 2. 기존 데이터 로드 함수
def load_existing_data():
    if os.path.exists(DATA_FILE):
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
                
                # --- [변경 시작] 모든 기간 데이터를 유지하기 위한 로직 ---
                # [수정] 상품별로 모든 옵션(개월수별 금리)을 리스트 형태로 저장합니다.
                # 이는 계산기에서 사용자가 기간을 바꿀 때 모든 경우의 수를 보여주기 위함입니다.
                product_options = {}
                for opt in opt_list:
                    code = opt['fin_prdt_cd']
                    if code not in product_options:
                        product_options[code] = []
                    
                    product_options[code].append({
                        "save_trm": int(opt['save_trm']),
                        "intr_rate": float(opt['intr_rate'] or 0),
                        "intr_rate2": float(opt['intr_rate2'] or 0),
                        "intr_type": opt['intr_rate_type_nm']
                    })

                rate_map = {}
                for code, opts in product_options.items():
                    # [수정] 대표 금리를 결정하는 로직 (기본 표출용)
                    # 우선순위: 12개월 -> 24개월 -> 6개월 순서대로 찾되, 전체 옵션(opts)은 그대로 유지합니다.
                    selected_opt = None
                    for target_trm in [12, 24, 6]:
                        found = next((o for o in opts if o['save_trm'] == target_trm), None)
                        if found:
                            selected_opt = found
                            break
                    
                    if not selected_opt:
                        selected_opt = max(opts, key=lambda x: x['save_trm'])

                    rate_map[code] = {
                        "max": selected_opt['intr_rate2'],
                        "base": selected_opt['intr_rate'],
                        "intr_type": selected_opt['intr_type'],
                        "save_trm": selected_opt['save_trm'],
                        "all_options": opts # [수정] 계산기 대응을 위해 모든 개월수 데이터를 options 필드에 담습니다.
                    }
                # --- [변경 종료] ---
                
                for base in base_list:
                    code = base['fin_prdt_cd']
                    if code in rate_map:
                        all_products.append({
                            "id": code,
                            "bank": base['kor_co_nm'].strip(),
                            "name": base['fin_prdt_nm'].strip(),
                            "spcl_cnd": base.get('spcl_cnd', '').strip(),
                            "max": rate_map[code]['max'], # 대표 최고금리
                            "base": rate_map[code]['base'], # 대표 기본금리
                            "intr_type": rate_map[code]['intr_type'],
                            "save_trm": rate_map[code]['save_trm'], 
                            "options": rate_map[code]['all_options'], # [추가] 계산기용 전체 데이터 필드
                            "type": p_type
                        })
                
                max_page = int(data.get('max_page_no', 1))
                if page_no >= max_page: break
                page_no += 1
            except Exception as e:
                print(f"⚠️ {p_type} API 호출 중 에러: {e}")
                break
            
    return all_products

# 5. 메인 실행 로직
def main():
    master_data = load_existing_data()
    today = datetime.now().strftime('%Y-%m-%d')
    
    manual_types = ['parking', 'cma', 'bill', 'els', 'bond']
    preserved_data = []
    for item in master_data:
        if item.get('type') in manual_types:
            if 'save_trm' not in item:
                item['save_trm'] = 0
            preserved_data.append(item)
    
    print("🚀 API(예/적금) 데이터 수집 및 전 기간 보존 모드 시작...")
    api_deposits = fetch_all_products("deposit")
    api_savings = fetch_all_products("savings")
    
    all_new_data = api_deposits + api_savings
    updated_items = []
    
    for new_item in all_new_data:
        existing = next((item for item in master_data if item.get('id') == new_item['id']), None)
        
        # [수정] 히스토리 중복 기록 방지 (오늘 이미 기록했다면 덮어쓰기)
        # 대표 금리(max) 기준으로 변동 추이를 기록합니다.
        history = existing.get('history', []) if existing else []
        history = [h for h in history if h['date'] != today]
        
        if not history or round(history[-1]['rate'], 2) != round(new_item['max'], 2):
            history.append({"date": today, "rate": new_item['max']})
            
        new_item['history'] = history
        updated_items.append(new_item)
        
    final_output = preserved_data + updated_items

    if len(all_new_data) < 10:
        print(f"❌ 수집 데이터 부족으로 업데이트 중단")
        return

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 업데이트 완료! (전 기간 데이터 보존됨)")

if __name__ == "__main__":
    main()
