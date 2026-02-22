import requests # API 통신을 위한 라이브러리입니다.
import json # JSON 파일 처리를 위한 라이브러리입니다.
import os # 환경 변수 및 파일 경로 확인을 위한 라이브러리입니다.
from datetime import datetime # 금리 변동 날짜를 기록하기 위한 모듈입니다.

# 1. API 설정 및 파일 경로 정의
API_KEY = os.environ.get('FSS_API_KEY') # GitHub Secrets에 저장된 API 키를 가져옵니다.
DATA_FILE = 'data.json' # 데이터 저장 파일명입니다.
FIN_GROUPS = ["020000", "030300"] # 020000: 시중은행, 030300: 저축은행 코드입니다.

# 2. 기존 데이터 로드 (금리 히스토리를 유지하기 위해 필요합니다)
if os.path.exists(DATA_FILE): # 파일이 존재하는지 확인합니다.
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        master_data = json.load(f) # 기존 데이터를 읽어옵니다.
else:
    master_data = [] # 파일이 없으면 빈 리스트로 시작합니다.

# 3. 데이터 수집 함수 (기존 로직에서 저축은행 및 히스토리 누적 로직 추가)
def update_product_data():
    today = datetime.now().strftime('%Y-%m-%d') # 오늘 날짜를 생성합니다 (예: 2024-05-21).
    updated_items = [] # 수동 관리 데이터를 제외한 최신 API 데이터를 담을 리스트입니다.
    
    # 파킹통장, CMA 등 수동 관리 항목은 미리 빼두어 보존합니다.
    manual_types = ['parking', 'cma', 'bill', 'els', 'bond']
    preserved_data = [item for item in master_data if item.get('type') in manual_types]

    for group in FIN_GROUPS: # 시중은행과 저축은행을 순차적으로 조회합니다.
        for p_type in ["deposit", "savings"]: # 예금과 적금을 각각 조회합니다.
            endpoint = "depositProductsSearch.json" if p_type == "deposit" else "savingProductsSearch.json"
            url = f"http://finlife.fss.or.kr/finlifeapi/{endpoint}?auth={API_KEY}&topFinGrpNo={group}&pageNo=1"
            
            res = requests.get(url) # API에 데이터를 요청합니다.
            if res.status_code != 200: continue # 연결 실패 시 다음으로 넘어갑니다.
            
            data = res.json().get('result', {})
            base_list = data.get('baseList', []) # 상품 기본 정보입니다.
            opt_list = data.get('optionList', []) # 금리 상세 정보입니다.

            # 금리 정보 매핑 (12개월 단리/복리 정보 포함)
            rate_map = {}
            for opt in opt_list:
                code = opt['fin_prdt_cd']
                if opt['save_trm'] == "12": # 12개월 기준 데이터만 필터링합니다.
                    rate_map[code] = {
                        "max": float(opt['intr_rate2'] or 0),
                        "base": float(opt['intr_rate'] or 0),
                        "intr_type": opt['intr_rate_type']
                    }

            # 상품 정보 결합 및 히스토리 업데이트
            for base in base_list:
                code = base['fin_prdt_cd']
                if code not in rate_map: continue # 금리 정보가 없으면 건너뜁니다.
                
                new_max = rate_map[code]['max']
                # 기존 데이터에서 해당 상품을 찾습니다.
                existing_item = next((i for i in master_data if i.get('id') == code), None)
                
                if existing_item:
                    # 기존 히스토리를 가져오고, 금리가 변했다면 새 데이터를 추가합니다.
                    history = existing_item.get('history', [])
                    if not history or history[-1]['rate'] != new_max:
                        history.append({"date": today, "rate": new_max})
                else:
                    # 처음 발견된 상품이면 현재 금리로 히스토리를 시작합니다.
                    history = [{"date": today, "rate": new_max}]

                updated_items.append({
                    "id": code, # 상품 식별을 위한 고유 코드입니다.
                    "bank": base['kor_co_nm'],
                    "name": base['fin_prdt_nm'],
                    "max": new_max,
                    "base": rate_map[code]['base'],
                    "intr_type": rate_map[code]['intr_type'],
                    "type": p_type,
                    "history": history # 누적된 금리 변동 기록입니다.
                })

    # 최종 병합 및 저장
    final_output = preserved_data + updated_items
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print(f"✅ 업데이트 완료: 총 {len(final_output)}개 상품 저장됨.")

update_product_data() # 함수를 실행합니다.
