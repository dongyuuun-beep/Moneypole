import requests # API 통신을 위해 requests 라이브러리를 불러옵니다.
import json # 데이터를 JSON 파일로 읽고 쓰기 위해 불러옵니다.
import os # GitHub Secrets 등 환경변수에 접근하기 위해 불러옵니다.
from datetime import datetime # 금리가 변경된 '오늘 날짜'를 기록하기 위해 불러옵니다.

# 1. 환경 설정 및 기본 변수 정의
API_KEY = os.environ.get('FSS_API_KEY') # GitHub 환경변수에서 금감원 API 키를 가져옵니다.
DATA_FILE = 'data.json' # 데이터가 누적 저장될 파일 이름입니다.
FIN_GROUPS = ["020000", "030300"] # 020000: 시중은행(신한, 국민 등), 030300: 저축은행 코드입니다.

# 2. 기존 데이터 로드 함수 (히스토리를 유지하기 위해 필수)
def load_existing_data():
    if os.path.exists(DATA_FILE): # 파일이 실제로 존재하는지 확인합니다.
        with open(DATA_FILE, 'r', encoding='utf-8') as f: # 한글 깨짐 방지를 위해 utf-8로 엽니다.
            return json.load(f) # 기존 JSON 데이터를 파이썬 리스트로 변환하여 반환합니다.
    return [] # 파일이 없다면 빈 리스트를 반환하여 새로 시작합니다.

# 3. 특정 상품군(예금/적금)의 "모든 페이지" 데이터를 긁어오는 함수
def fetch_all_products(p_type):
    # 예금이면 depositProductsSearch, 적금이면 savingProductsSearch 엔드포인트를 사용합니다.
    endpoint = "depositProductsSearch.json" if p_type == "deposit" else "savingProductsSearch.json"
    all_products = [] # 수집된 모든 상품을 담을 빈 리스트입니다.
    
    for group in FIN_GROUPS: # 시중은행과 저축은행을 번갈아가며 조회합니다.
        page_no = 1 # 항상 1페이지부터 조회를 시작합니다.
        
        while True: # 다음 페이지가 없을 때까지 무한 반복하여 누락되는 은행이 없게 합니다.
            # API 호출 URL 구성 (pageNo 변수를 통해 페이지를 넘깁니다)
            url = f"http://finlife.fss.or.kr/finlifeapi/{endpoint}?auth={API_KEY}&topFinGrpNo={group}&pageNo={page_no}"
            res = requests.get(url) # API 서버에 데이터를 요청합니다.
            
            if res.status_code != 200: 
                break # 서버 에러 시 해당 그룹 조회를 중단합니다.
            
            data = res.json().get('result', {}) # 응답 데이터 중 'result' 알맹이만 빼냅니다.
            base_list = data.get('baseList', []) # 상품의 기본 정보(이름, 은행명 등) 리스트입니다.
            opt_list = data.get('optionList', []) # 상품의 금리 정보 리스트입니다.
            
            # 금리 정보(opt_list)에서 12개월 기준 데이터만 뽑아 딕셔너리로 맵핑합니다.
            rate_map = {}
            for opt in opt_list:
                code = opt['fin_prdt_cd'] # 상품 고유 코드를 가져옵니다.
                if str(opt['save_trm']) == "12": # 가입 기간이 12개월인 데이터만 선별합니다.
                    rate_map[code] = {
                        "max": float(opt['intr_rate2'] or 0), # 최고 우대 금리
                        "base": float(opt['intr_rate'] or 0), # 기본 금리
                        "intr_type": opt['intr_rate_type'] # 단리/복리 여부
                    }
            
            # 기본 정보(base_list)와 금리 정보(rate_map)를 결합합니다.
            for base in base_list:
                code = base['fin_prdt_cd'] # 상품 코드를 기준으로 매칭합니다.
                if code in rate_map: # 해당 상품의 12개월 금리 정보가 존재한다면
                    all_products.append({
                        "id": code, # 나중에 히스토리 추적을 위해 상품 코드를 'id'로 저장합니다.
                        "bank": base['kor_co_nm'], # 은행명 (예: 신한은행)
                        "name": base['fin_prdt_nm'], # 상품명
                        "spcl_cnd": base.get('spcl_cnd', ''), # 우대 금리 조건 (HTML 상세페이지용)
                        "max": rate_map[code]['max'], # 최고 금리
                        "base": rate_map[code]['base'], # 기본 금리
                        "intr_type": rate_map[code]['intr_type'], # 단리/복리
                        "type": p_type # 예금(deposit)인지 적금(savings)인지 구분
                    })
            
            max_page = data.get('max_page_no', 1) # API가 알려주는 전체 페이지 수를 확인합니다.
            if page_no >= max_page: # 현재 페이지가 마지막 페이지라면
                break # 반복문을 탈출하여 다음 금융권역(저축은행)으로 넘어갑니다.
            
            page_no += 1 # 마지막 페이지가 아니라면 페이지 번호를 1 올려서 다음 페이지를 조회합니다.
            
    return all_products # 짤리는 것 없이 싹 긁어온 전체 상품 리스트를 반환합니다.

# 4. 메인 실행 로직 (히스토리 누적 및 크롤링 데이터 보존)
def main():
    master_data = load_existing_data() # 기존 data.json 파일을 불러옵니다.
    today = datetime.now().strftime('%Y-%m-%d') # 오늘 날짜를 YYYY-MM-DD 형식으로 문자열로 만듭니다.
    
    # [크롤링 대비] API로 긁지 않고 외부 크롤링/수동으로 관리할 항목들을 미리 빼서 보존합니다.
    manual_types = ['parking', 'cma', 'bill', 'els', 'bond']
    preserved_data = [item for item in master_data if item.get('type') in manual_types]
    
    print("🚀 전체 은행/저축은행 예적금 데이터 수집 시작...")
    api_deposits = fetch_all_products("deposit") # 예금 전체 데이터를 가져옵니다.
    api_savings = fetch_all_products("savings") # 적금 전체 데이터를 가져옵니다.
    api_all = api_deposits + api_savings # 새로 수집한 예적금 데이터를 합칩니다.
    
    updated_items = [] # 최종적으로 업데이트될 예적금 리스트입니다.
    
    # 금리 변동 추이(Graph)를 만들기 위한 핵심 로직입니다.
    for new_item in api_all:
        # 기존 데이터(master_data) 중에 현재 상품(new_item)과 id가 같은 것을 찾습니다.
        existing = next((item for item in master_data if item.get('id') == new_item['id']), None)
        
        history = [] # 히스토리를 담을 빈 리스트를 준비합니다.
        if existing and 'history' in existing:
            history = existing['history'] # 기존에 누적된 히스토리 기록을 그대로 가져옵니다.
            # 가장 최근(마지막) 기록의 금리와 오늘 긁어온 최고 금리가 다를 경우에만!
            if history and history[-1]['rate'] != new_item['max']:
                # 오늘 날짜와 변경된 새 금리를 히스토리 맨 끝에 추가합니다.
                history.append({"date": today, "rate": new_item['max']})
        else:
            # 기존에 없던 완전 신규 상품이라면, 오늘 날짜로 첫 히스토리 기록을 만듭니다.
            history = [{"date": today, "rate": new_item['max']}]
            
        new_item['history'] = history # 업데이트된 히스토리 리스트를 새 데이터에 집어넣습니다.
        updated_items.append(new_item) # 완성된 상품 데이터를 결과 리스트에 담습니다.
        
    # [크롤링용 보존 데이터] + [새로고침된 API 예적금 데이터] 병합
    final_output = preserved_data + updated_items
    
    # 최종 데이터를 JSON 파일로 덮어쓰기 저장합니다.
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2) # 들여쓰기(indent)로 보기 좋게 포맷팅합니다.
        
    print(f"✅ 업데이트 완료! (수동/크롤링 보존: {len(preserved_data)}건, API 갱신: {len(updated_items)}건)")

if __name__ == "__main__":
    main() # 파이썬 스크립트가 실행되면 main() 함수를 호출합니다.
