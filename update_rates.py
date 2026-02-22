import requests # 웹페이지 통신 및 API 호출을 위한 라이브러리입니다.
import json # JSON 데이터를 다루기 위한 라이브러리입니다.
import os # 시스템 환경변수(API 키 등)를 불러오기 위한 라이브러리입니다.
from datetime import datetime # 금리 변동 이력에 날짜를 기록하기 위한 라이브러리입니다.
from bs4 import BeautifulSoup # 웹페이지 크롤링(HTML 분석)을 위한 라이브러리입니다.

# 1. 환경 설정 및 기본 변수 정의
API_KEY = os.environ.get('FSS_API_KEY') # GitHub Secrets에서 API 키를 가져옵니다.
DATA_FILE = 'data.json' # 데이터가 누적되어 저장될 파일명입니다.
FIN_GROUPS = ["020000", "030300"] # 020000: 시중은행, 030300: 저축은행 코드입니다.

# 2. 기존 데이터 로드 함수 (히스토리 유지를 위해 필수)
def load_existing_data():
    if os.path.exists(DATA_FILE): # 데이터 파일이 이미 존재하는지 확인합니다.
        with open(DATA_FILE, 'r', encoding='utf-8') as f: # 한글 깨짐 방지를 위해 UTF-8로 엽니다.
            return json.load(f) # 기존 파일의 데이터를 파이썬 리스트로 변환하여 반환합니다.
    return [] # 파일이 없으면 빈 리스트를 반환합니다.

# 3. [API] 예금/적금 전체 페이지 수집 함수
def fetch_all_products(p_type):
    # 예금(deposit)과 적금(savings)에 맞춰 API 엔드포인트를 설정합니다.
    endpoint = "depositProductsSearch.json" if p_type == "deposit" else "savingProductsSearch.json"
    all_products = [] # 전체 상품을 담을 리스트입니다.
    
    for group in FIN_GROUPS: # 시중은행과 저축은행을 번갈아 조회합니다.
        page_no = 1 # 항상 1페이지부터 시작합니다.
        while True: # 다음 페이지가 없을 때까지 계속 반복합니다.
            url = f"http://finlife.fss.or.kr/finlifeapi/{endpoint}?auth={API_KEY}&topFinGrpNo={group}&pageNo={page_no}"
            res = requests.get(url) # API 서버에 요청을 보냅니다.
            if res.status_code != 200: break # 에러 발생 시 반복을 중단합니다.
            
            data = res.json().get('result', {}) # 응답에서 'result' 데이터만 추출합니다.
            base_list = data.get('baseList', []) # 기본 정보(은행명, 상품명 등) 리스트입니다.
            opt_list = data.get('optionList', []) # 금리 정보 리스트입니다.
            
            # 금리 정보 맵핑 (12개월 기준)
            rate_map = {}
            for opt in opt_list:
                code = opt['fin_prdt_cd'] # 상품 코드를 추출합니다.
                if str(opt['save_trm']) == "12": # 12개월 가입 기준 데이터만 가져옵니다.
                    rate_map[code] = {
                        "max": float(opt['intr_rate2'] or 0), # 최고 우대 금리
                        "base": float(opt['intr_rate'] or 0), # 기본 금리
                        "intr_type": opt['intr_rate_type'] # 단리/복리 여부
                    }
            
            # 기본 정보와 금리 정보를 결합합니다.
            for base in base_list:
                code = base['fin_prdt_cd']
                if code in rate_map: # 금리 정보가 있는 상품만 추가합니다.
                    all_products.append({
                        "id": code, # 고유 식별자입니다.
                        "bank": base['kor_co_nm'], # 은행명
                        "name": base['fin_prdt_nm'], # 상품명
                        "spcl_cnd": base.get('spcl_cnd', ''), # 우대 금리 조건
                        "max": rate_map[code]['max'],
                        "base": rate_map[code]['base'],
                        "intr_type": rate_map[code]['intr_type'],
                        "type": p_type # deposit 또는 savings
                    })
            
            max_page = data.get('max_page_no', 1) # 전체 페이지 수를 확인합니다.
            if page_no >= max_page: break # 마지막 페이지면 반복문을 탈출합니다.
            page_no += 1 # 다음 페이지 조회를 위해 페이지 번호를 올립니다.
            
    return all_products # 수집된 전체 API 상품 리스트를 반환합니다.
# 4. [크롤링] 파킹통장(입출금자유예금) 데이터 수집 함수
def crawl_parking_accounts():
    parking_products = []
    # 웹페이지 대신 금감원이 사용하는 데이터 경로(JSON)를 직접 호출합니다.
    url = "https://finlife.fss.or.kr/finlife/svings/fdrmDpst/list.json?menuNo=700002"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finlife.fss.or.kr/finlife/svings/fdrmDpst/list.do?menuNo=700002'
        }
        # 금감원 서버에 데이터를 요청합니다.
        res = requests.post(url, headers=headers) 
        data = res.json()
        
        # 내부 데이터 리스트를 가져옵니다.
        items = data.get('result', {}).get('list', [])
        
        for index, item in enumerate(items):
            rate_val = float(item.get('intr_rate', 0) or 0)
            if rate_val > 0:
                parking_products.append({
                    "id": f"parking_{index}",
                    "bank": item.get('kor_co_nm', '').strip(),
                    "name": item.get('fin_prdt_nm', '').strip(),
                    "spcl_cnd": item.get('spcl_cnd', '입출금이 자유로운 파킹통장입니다.'),
                    "max": rate_val,
                    "base": rate_val,
                    "type": "parking"
                })
        print(f"✅ 파킹통장 JSON 수집 결과: {len(parking_products)}건")
    except Exception as e:
        print(f"⚠️ 파킹통장 수집 실패: {e}")
    
    return parking_products


# 5. 메인 실행 로직 (API + 크롤링 병합 및 히스토리 업데이트)
def main():
    master_data = load_existing_data() # 기존에 저장된 데이터(히스토리 포함)를 불러옵니다.
    today = datetime.now().strftime('%Y-%m-%d') # '202X-XX-XX' 형태의 오늘 날짜 문자열을 만듭니다.
    
    # 크롤링과 API가 아닌 순수 '수동 관리' 품목만 따로 보존합니다 (CMA, 발행어음 등).
    manual_types = ['cma', 'bill', 'els', 'bond']
    preserved_data = [item for item in master_data if item.get('type') in manual_types]
    
    print("🚀 API(예/적금) 및 크롤링(파킹통장) 데이터 수집 시작...")
    #api_deposits = fetch_all_products("deposit") # API로 예금을 가져옵니다.
    ##api_savings = fetch_all_products("savings") # API로 적금을 가져옵니다.
    crawled_parking = crawl_parking_accounts() # 크롤링으로 파킹통장을 가져옵니다.
    
    # 수집한 3가지 종류의 데이터를 하나의 큰 리스트로 합칩니다.
    all_new_data =  crawled_parking #+ api_deposits + api_savings
    updated_items = [] # 최종 업데이트 될 아이템들을 담을 리스트입니다.
    
    # 금리 변동 추이(Graph) 로직을 적용합니다.
    for new_item in all_new_data:
        # 기존 데이터 중에서 지금 처리 중인 상품과 동일한 ID를 가진 것을 찾습니다.
        existing = next((item for item in master_data if item.get('id') == new_item['id']), None)
        
        history = [] # 히스토리를 저장할 리스트입니다.
        if existing and 'history' in existing:
            history = existing['history'] # 기존 히스토리를 가져옵니다.
            # 최근 기록된 금리와 오늘 확인한 금리가 다를 때만 새로운 기록을 남깁니다.
            if history and history[-1]['rate'] != new_item['max']:
                history.append({"date": today, "rate": new_item['max']})
        else:
            # 완전히 처음 수집되는 상품이면 오늘 날짜로 첫 기록을 생성합니다.
            history = [{"date": today, "rate": new_item['max']}]
            
        new_item['history'] = history # 갱신된 히스토리를 상품 데이터에 넣습니다.
        updated_items.append(new_item) # 업데이트된 상품을 최종 리스트에 추가합니다.
        
    # 수동 보존 데이터와 새로 수집/갱신된 데이터를 합칩니다.
    final_output = preserved_data + updated_items

    # [방어 로직] 수집된 데이터가 너무 적으면 비정상으로 간주하고 업데이트를 중단합니다.
    # (예: API 점검 등으로 0건이 수집되었을 때 기존 데이터를 지우지 않기 위함)
    if len(all_new_data) < 10: # 최소 10건 이상일 때만 저장 (기준 숫자는 적절히 조절 가능)
        print(f"❌ 수집된 데이터가 너무 적습니다 ({len(all_new_data)}건). 파일을 업데이트하지 않고 종료합니다.")
        return

    # 위 조건을 통과한 경우에만 아래의 파일 저장(json.dump) 코드가 실행되도록 합니다.
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 업데이트 완료! (수동 보존: {len(preserved_data)}건, API+크롤링 갱신: {len(updated_items)}건)")

if __name__ == "__main__":
    main() # 파이썬 파일 실행 시 main() 함수를 구동합니다.
