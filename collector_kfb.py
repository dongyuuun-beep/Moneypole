import requests
from bs4 import BeautifulSoup
import json
import re
import urllib3
import ssl

# [설정] SSL 인증서 경고 메시지 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# [디버깅] 오래된 서버(Legacy Server)와의 연결 호환성을 위한 커스텀 어댑터
class LegacyHttpAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # 💡 OP_LEGACY_SERVER_CONNECT (0x4): 보안 수준이 낮은 구형 서버 접속 허용
        ctx.options |= 0x4  
        ctx.check_hostname = False
        kwargs['ssl_context'] = ctx
        return super(LegacyHttpAdapter, self).init_poolmanager(*args, **kwargs)

def fetch_kfb_parking_rates():
    url = "https://portal.kfb.or.kr/compare/free_deposit_search_result_sort.php"
    
    # [설정] 실제 브라우저처럼 보이기 위한 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://portal.kfb.or.kr/compare/free_deposit.php",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # [데이터] 은행연합회 서버에 전달할 폼 데이터 (파킹통장 전체 검색)
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

    print("🚀 은행연합회 데이터 요청 시작 (Legacy Mode)...")
    
    # [디버깅] 세션 생성 및 커스텀 어댑터 장착 (보안 우회 핵심)
    session = requests.Session()
    session.mount("https://", LegacyHttpAdapter())
    
    try:
        # 1. HTTP 요청 및 응답 코드 확인
        response = session.post(url, headers=headers, data=payload, verify=False, timeout=30)
        print(f"📡 응답 상태 코드: {response.status_code}") # 200이면 성공

        if response.status_code != 200:
            print(f"❌ 서버 응답 에러: {response.status_code}")
            return []

        # 2. 인코딩 디버깅 (한글 깨짐 방지)
        response.encoding = response.apparent_encoding 
        print(f"🌐 탐색된 인코딩: {response.encoding}")

        # 3. 데이터 파싱 (BeautifulSoup)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [디버깅] 테이블 행(tr)이 실제로 존재하는지 확인
        rows = soup.select("#compare_list tbody tr")
        print(f"📊 검색된 행 개수: {len(rows)}개")

        if len(rows) == 0:
            # 💡 만약 0개라면 서버가 차단했거나 HTML 구조가 바뀐 것임
            print("⚠️ 데이터 행을 찾을 수 없습니다. HTML 본문 일부 출력:")
            print(response.text[:500]) # 본문 앞부분만 찍어서 확인

        parsed_data = []
        for i, row in enumerate(rows):
            cols = row.find_all("td")
            if len(cols) < 3: continue
            
            try:
                bank_name = cols[0].get_text(strip=True)
                product_name = cols[1].get_text(strip=True)
                rate_text = cols[2].get_text(strip=True)
                
                # 금리 숫자 추출
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
            except Exception as row_err:
                print(f"❌ {i}번째 행 파싱 중 에러: {row_err}")

        return parsed_data

    except requests.exceptions.SSLError as ssl_err:
        print(f"🔒 SSL 보안 연결 실패 (Handshake Error): {ssl_err}")
    except requests.exceptions.Timeout:
        print("⏰ 서버 응답 시간 초과 (Timeout)")
    except Exception as e:
        print(f"❌ 예상치 못한 에러 발생: {e}")
        import traceback
        print(traceback.format_exc()) # 에러가 발생한 지점을 상세히 출력
    
    return []

if __name__ == "__main__":
    data = fetch_kfb_parking_rates()
    print(f"✅ 최종 수집 완료: {len(data)}개의 상품")
