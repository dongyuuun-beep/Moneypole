import requests
from bs4 import BeautifulSoup
import json
import re
import urllib3  # [수정: SSL 경고 제거를 위해 추가]

# [수정: SSL 검증 생략 시 발생하는 경고 메시지를 무시하도록 설정]
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_kfb_parking_rates():
    url = "https://portal.kfb.or.kr/compare/free_deposit_search_result_sort.php"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://portal.kfb.or.kr/compare/free_deposit.php",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # 유저님이 제공해주신 진짜 데이터(Payload)
    payload = {
        "InterestType": "",
        "BankValue": "0010030|0013175|0011625|0010001|0010002|0013909|0010026|0010927|0010006|0014807|0010016|0010017|0010019|0010020|0010022|0010024|0014674|0015130|0017801",
        "InterestMonth": "",
        "MAX_INTEREST": "",
        "OrderByType": "ASC",
        "ASC": "",
        "JOIN_METHOD": "",
        "SortType": ""
    }

    print("🚀 은행연합회 데이터 요청 중...")
    
    # [수정: verify=False를 추가하여 SSL 핸드쉐이크 에러(보안 연결 설정 실패) 우회]
    # [수정: timeout=20을 추가하여 서버 응답이 늦어질 경우 무한 대기 방지]
    response = requests.post(url, headers=headers, data=payload, verify=False, timeout=20)
    
    # 은행연합회는 보통 euc-kr을 사용하므로 인코딩 설정
    response.encoding = 'utf-8' # 만약 한글이 깨지면 'euc-kr'로 변경하세요
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 결과 테이블의 행(tr)들을 찾음
    rows = soup.select("#compare_list tbody tr")
    
    parsed_data = []
    
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3: continue
        
        bank_name = cols[0].get_text(strip=True)
        product_name = cols[1].get_text(strip=True)
        # 금리 부분에서 숫자만 추출 (예: "3.50%" -> 3.5)
        rate_text = cols[2].get_text(strip=True)
        rate_matches = re.findall(r"\d+\.\d+|\d+", rate_text)
        rate = float(rate_matches[0]) if rate_matches else 0.0
        
        # MoneyPole data.json 형식에 맞게 구성
        item = {
            "id": f"KFB_{bank_name}_{product_name[:3]}", # 간단한 ID 생성
            "bank": bank_name,
            "name": product_name,
            "spcl_cnd": "상세내용 홈페이지 참조",
            "max": rate,
            "base": rate,
            "intr_type": "단리",
            "save_trm": 0, # 파킹통장은 0으로 설정
            "type": "parking",
            "options": []
        }
        parsed_data.append(item)
    
    return parsed_data

# 실행 및 저장 테스트
if __name__ == "__main__":
    data = fetch_kfb_parking_rates()
    with open('kfb_temp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ 수집 완료: {len(data)}개의 상품을 찾았습니다.")
