import requests
from bs4 import BeautifulSoup
import json
import re
import urllib3  # [수정: SSL 경고 제어를 위해 추가]

# [수정: verify=False 사용 시 뜨는 보안 경고 창을 끄기 위한 설정]
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_kfb_parking_rates():
    url = "https://portal.kfb.or.kr/compare/free_deposit_search_result_sort.php"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://portal.kfb.or.kr/compare/free_deposit.php",
        "Content-Type": "application/x-www-form-urlencoded"
    }

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
    
    try:
        # [수정: verify=False로 SSL 핸드쉐이크 에러 우회]
        # [수정: timeout=30으로 서버 응답 지연에 따른 에러 방지]
        response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
        
        # 은행연합회 데이터는 한국어 인코딩(euc-kr)일 수 있으므로 자동 설정 확인
        response.encoding = response.apparent_encoding 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select("#compare_list tbody tr")
        
        parsed_data = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3: continue
            
            bank_name = cols[0].get_text(strip=True)
            product_name = cols[1].get_text(strip=True)
            rate_text = cols[2].get_text(strip=True)
            
            # 숫자만 추출 (정규식 강화)
            rate_matches = re.findall(r"\d+\.\d+|\d+", rate_text)
            rate = float(rate_matches[0]) if rate_matches else 0.0
            
            parsed_data.append({
                "id": f"KFB_{bank_name}_{product_name[:3]}",
                "bank": bank_name,
                "name": product_name,
                "spcl_cnd": "상세내용 홈페이지 참조",
                "max": rate,
                "base": rate,
                "intr_type": "단리",
                "save_trm": 0,
                "type": "parking",
                "options": []
            })
        
        return parsed_data

    except Exception as e:
        print(f"❌ KFB 요청 중 상세 에러 발생: {e}")
        return []

if __name__ == "__main__":
    data = fetch_kfb_parking_rates()
    print(f"✅ 수집 완료: {len(data)}개의 상품을 찾았습니다.")
