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
                
                # --- [변경 시작] 기간별 우선순위 추출 로직 ---
                product_options = {}
                for opt in opt_list:
                    code = opt['fin_prdt_cd']
                    if code not in product_options:
                        product_options[code] = []
                    product_options[code].append(opt)

                rate_map = {}
                for code, opts in product_options.items():
                    selected_opt = None
                    # 우선순위: 12개월 -> 24개월 -> 6개월 순서대로 찾기
                    for target_trm in ["12", "24", "6"]:
                        found = next((o for o in opts if str(o['save_trm']) == target_trm), None)
                        if found:
                            selected_opt = found
                            break
                    
                    if not selected_opt:
                        selected_opt = max(opts, key=lambda x: int(x['save_trm']))

                    # [수정] save_trm을 반드시 정수(int)로 저장하여 JS의 숫자 필터와 호환성을 맞춥니다.
                    rate_map[code] = {
                        "max": float(selected_opt['intr_rate2'] or 0),
                        "base": float(selected_opt['intr_rate'] or 0),
                        "intr_type": selected_opt['intr_rate_type_nm'],
                        "save_trm": int(selected_opt['save_trm']) 
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
                            "max": rate_map[code]['max'],
                            "base": rate_map[code]['base'],
                            "intr_type": rate_map[code]['intr_type'],
                            "save_trm": rate_map[code]['save_trm'], # 필드 반영
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
    # [수정] 기존 데이터 중 수동 카테고리(파킹 등)에 기간(save_trm)이 없으면 0으로 채워줍니다.
    # 이렇게 해야 웹의 JS 필터에서 "12개월" 등을 선택했을 때 에러로 리스트가 사라지지 않습니다.
    preserved_data = []
    for item in master_data:
        if item.get('type') in manual_types:
            if 'save_trm' not in item:
                item['save_trm'] = 0 # 파킹통장 등은 기간이 없으므로 0으로 설정
            preserved_data.append(item)
    
    print("🚀 API(예/적금) 데이터 수집 및 기간 최적화 시작...")
    api_deposits = fetch_all_products("deposit")
    api_savings = fetch_all_products("savings")
    
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

    if len(all_new_data) < 10:
        print(f"❌ 수집 데이터 부족으로 업데이트 중단")
        return

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        # [수정] indent=2를 유지하여 사람이 읽기 좋게 저장하고, 
        # 파일이 완전히 새로 쓰여지도록 보장합니다.
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 업데이트 완료! (데이터 수 {len(final_output)}개)")

if __name__ == "__main__":
    main()
