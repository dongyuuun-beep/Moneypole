import requests # API 통신을 위한 라이브러리를 불러옵니다.
import json # JSON 파일 저장을 위한 라이브러리를 불러옵니다.
import os # API 키 등 환경변수 접근을 위한 라이브러리를 불러옵니다.

# 1. 설정 (인증키는 GitHub Secrets에 'FSS_API_KEY'로 저장해야 합니다)
API_KEY = os.environ.get('FSS_API_KEY') # 환경변수에서 금감원 API 키를 가져옵니다.
DATA_FILE = 'data.json' # 결과가 저장될 파일 이름입니다.

# 2. 데이터 수집 함수 (상품 종류: deposit 또는 savings)
def fetch_fss_data(product_type):
    # 예금이면 depositProductsSearch, 적금이면 savingProductsSearch 주소를 사용합니다.
    endpoint = "depositProductsSearch.json" if product_type == "deposit" else "savingProductsSearch.json"
    # 금융권역은 020000(은행)으로 설정하여 데이터를 요청합니다.
    url = f"http://finlife.fss.or.kr/finlifeapi/{endpoint}?auth={API_KEY}&topFinGrpNo=020000&pageNo=1"
    
    response = requests.get(url) # 해당 주소로 데이터를 요청합니다.
    if response.status_code != 200: return [] # 연결 실패 시 빈 리스트를 반환합니다.
    
    raw_data = response.json().get('result', {}) # 결과에서 result 항목만 추출합니다.
    base_list = raw_data.get('baseList', []) # 상품의 기본 정보 리스트입니다.
    option_list = raw_data.get('optionList', []) # 금리 및 단리/복리 정보 리스트입니다.
    
    # 금리 정보(optionList)를 상품코드별로 정리합니다.
    rate_map = {}
    for opt in option_list:
        code = opt['fin_prdt_cd'] # 상품코드를 가져옵니다.
        term = int(opt['save_trm']) # 가입 기간(개월)을 가져옵니다.
        # 가장 대중적인 12개월 기준 데이터만 우선 수집합니다.
        if term == 12:
            rate_map[code] = {
                "base": float(opt['intr_rate'] or 0), # 기본 금리입니다.
                "max": float(opt['intr_rate2'] or 0), # 우대 포함 최고 금리입니다.
                "term": term, # 가입 기간입니다.
                "intr_type": opt['intr_rate_type'] # 단리(S)/복리(M) 타입입니다.
            }

    # 기본 정보와 금리 정보를 합쳐 최종 리스트를 만듭니다.
    result = []
    for base in base_list:
        code = base['fin_prdt_cd'] # 상품코드를 키로 사용합니다.
        if code in rate_map: # 금리 정보가 매칭되는 경우만 추가합니다.
            result.append({
                "bank": base['kor_co_nm'], # 은행 이름입니다.
                "name": base['fin_prdt_nm'], # 상품 이름입니다.
                "base": rate_map[code]['base'], # 기본 금리입니다.
                "max": rate_map[code]['max'], # 최고 금리입니다.
                "term": rate_map[code]['term'], # 기간입니다.
                "intr_type": rate_map[code]['intr_type'], # 'S' 또는 'M' (단리/복리) 입니다.
                "type": product_type # 'deposit' 또는 'savings' 구분입니다.
            })
    return result

# 3. 메인 실행 로직
def main():
    # 기존 데이터가 있으면 불러와서 파이킹통장, CMA 등 수동 데이터를 보존합니다.
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f) # 기존 파일을 읽어옵니다.
    else:
        old_data = [] # 파일이 없으면 빈 리스트로 시작합니다.

    # 파킹통장(parking), CMA(cma), 발행어음(bill), ELS(els), 채권(bond) 등은 보존합니다.
    manual_types = ['parking', 'cma', 'bill', 'els', 'bond']
    preserved_data = [item for item in old_data if item.get('type') in manual_types]

    print("🚀 금리 데이터 업데이트 중...")
    new_deposits = fetch_fss_data("deposit") # 최신 예금 데이터를 가져옵니다.
    new_savings = fetch_fss_data("savings") # 최신 적금 데이터를 가져옵니다.
    
    # 보존된 데이터와 새로 수집한 예적금 데이터를 하나로 합칩니다.
    final_data = preserved_data + new_deposits + new_savings

    # 최종 데이터를 data.json 파일로 저장합니다.
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2) # 한글 깨짐 방지 설정을 적용합니다.
    
    print(f"✅ 완료! (보존: {len(preserved_data)}건, API 수집: {len(new_deposits + new_savings)}건)")

if __name__ == "__main__":
    main() # 스크립트를 실행합니다.
