"""Official public-page data. These endpoints are not contracted public APIs."""
import hashlib
import json
import re
from datetime import date, datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FSB_PAGE = "https://www.fsb.or.kr/ratanym_0100.act"
KB_PAGE = "https://m.kbsec.com/go.able?linkcd=s010300010005"
KB_DATA = "https://m.kbsec.com/ndatatopweb/www/json/main/rate_manage_cma.json"
KAKAO_PAGE = "https://www.kakaobank.com/products/safeboxes"


class CollectionError(ValueError):
    pass


def session():
    client = requests.Session()
    client.headers.update({"User-Agent": "MoneyPole/1.0 (daily public rate comparison)"})
    client.mount("https://", HTTPAdapter(max_retries=Retry(
        total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"], respect_retry_after_header=False)))
    return client


def get_json(client, url, **kwargs):
    response = client.request(kwargs.pop("method", "GET"), url, timeout=(10, 30), **kwargs)
    response.raise_for_status()
    return response.json()


def text(value):
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True).replace("\\n", "\n")


def number(value):
    if value is None or str(value).strip() == "":
        raise CollectionError("금리 누락")
    result = float(value)
    if not 0 <= result <= 30:
        raise CollectionError("금리 범위 오류")
    return result


def iso_date(value):
    value = str(value).replace("/", "-")
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return date.fromisoformat(value).isoformat()


def parse_kb(data, today=None):
    today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    match = re.search(r"기준일\s*:\s*(\d{4}/\d{2}/\d{2})", text(data.get("cma100")))
    if not match:
        raise CollectionError("KB CMA 기준일 형식 변경")
    effective = iso_date(match[1])
    if date.fromisoformat(effective) > today:
        raise CollectionError("KB CMA 미래 적용 금리는 적용일 이후 반영")
    products = []
    # Personal auto-investment only. Corporate and term RP use different keys.
    for key, subtype, note in [("cma111", "RP", "cma001"), ("cma112", "발행어음", "cma002")]:
        rate_match = re.fullmatch(r"연\s*(\d+(?:\.\d+)?)\s*%", text(data.get(key)))
        if not rate_match or not text(data.get(note)):
            raise CollectionError("KB CMA 수익률 또는 재투자 정보 형식 변경")
        rate = number(rate_match[1])
        products.append({
            "id": f"KB_CMA_{key}", "bank": "KB증권", "name": f"KB CMA {subtype}형",
            "type": "cma", "subtype": subtype, "base": rate, "max": rate,
            "intr_type": "약정수익률", "rate_kind": "contractual", "save_trm": 0, "options": [],
            "rate_model": "flat", "rate_tiers": [{"from": 0, "to": None, "base": rate, "max": rate}],
            "spcl_cnd": "개인 자동투자상품 기준. 신규 입금·재투자 시 적용 수익률은 공식 안내 확인.",
            "reinvestment": text(data[note]), "deposit_protection": False,
            "effective_from": effective, "source_url": KB_PAGE, "source_data_url": KB_DATA,
        })
    return products


def fetch_kb(client):
    return parse_kb(get_json(client, KB_DATA))


def parse_kakao(html):
    soup = BeautifulSoup(html, "html.parser")

    def field(container, label):
        section = soup.select_one(container)
        headings = section.find_all("strong", string=label) if section else []
        if len(headings) != 1:
            raise CollectionError("카카오뱅크 상품 안내 형식 변경")
        parts = []
        for sibling in headings[0].find_next_siblings():
            if sibling.name == "strong":
                break
            parts.append(sibling.get_text(" ", strip=True))
        return "\n".join(parts)

    rate_text = field(".pop-rate .g__pop-content", "기본금리")
    rate_match = re.fullmatch(r"(\d{4}\.\d{2}\.\d{2}) 기준, 세금공제 전 연\s*(\d+(?:\.\d+)?)%", rate_text)
    if not rate_match:
        raise CollectionError("카카오뱅크 기본금리 형식 변경")
    reference_date = iso_date(rate_match[1].replace(".", "-"))
    if reference_date > datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat():
        raise CollectionError("카카오뱅크 미래 조회기준일")
    rate = number(rate_match[2])
    limit_text = field(".pop-product-info .g__pop-content", "입금한도")
    limit_match = re.search(r"증액한도\s*:\s*(\d+(?:\.\d+)?)억원", limit_text)
    formula = field(".pop-rate .g__pop-content", "이자계산방법")
    if not limit_match or formula != "매일의 최종 잔액에 약정금리를 적용하여 합산한 이자를 이자지급일에 지급":
        raise CollectionError("카카오뱅크 입금한도 또는 잔액 계산 방식 변경")
    limit = float(limit_match[1]) * 100000000
    return [{"id": "KAKAO_SAFEBOX", "bank": "카카오뱅크", "name": "세이프박스", "type": "parking",
             "base": rate, "max": rate, "rate_scope": "base_excluding_coupons", "save_trm": 0, "options": [],
             "intr_type": "공시 기본금리", "rate_model": "flat", "deposit_limit": limit,
             "rate_tiers": [{"from": 0, "to": limit, "base": rate, "max": rate}],
             "spcl_cnd": "금리쿠폰 우대는 표시 금리·계산에서 제외. " + field(".pop-rate .g__pop-content", "금리쿠폰"),
             "join_target": field(".pop-product-info .g__pop-content", "가입대상") + "\n" + field(".pop-product-info .g__pop-content", "가입제한"),
             "rate_notes": limit_text + "\n" + formula,
             "payment_cycle": field(".pop-rate .g__pop-content", "이자지급방법"),
             "reference_date": reference_date, "source_url": KAKAO_PAGE, "product_url": KAKAO_PAGE}]


def fetch_kakao(client):
    response = client.get(KAKAO_PAGE, timeout=(10, 30))
    response.raise_for_status()
    response.encoding = "utf-8"
    return parse_kakao(response.text)


def parse_fsb(rows):
    if not rows:
        raise CollectionError("저축은행 입출금자유예금 목록 없음")
    products = []
    for row in rows:
        bank, name = text(row.get("BANK_NAME")), text(row.get("PRODUCT_NAME"))
        company, product = row.get("FINAN_COMP_CODE"), row.get("FINAN_PROD_CODE")
        if not all([bank, name, company, product]):
            raise CollectionError("저축은행 상품 식별자 누락")
        base, highest = number(row.get("RATE_LOW")), number(row.get("RATE_HIGH"))
        if base > highest:
            raise CollectionError("저축은행 기본/최고금리 역전")
        details = {key: row.get(key) for key in [
            "RATE_LOW", "RATE_HIGH", "SWEETENER", "ETC_NOTE_MATTER", "HGST_INTR_APL_AMT", "RNG_CODE"]}
        products.append({
            "id": f"FSB_{company}_{product}", "bank": bank + "저축은행", "name": name,
            "type": "parking", "base": base, "max": highest, "save_trm": 0, "options": [],
            "intr_type": "공시금리", "rate_model": "unverified_tiers", "rate_tiers": [],
            "spcl_cnd": text(row.get("SWEETENER")) or "공시된 우대조건 없음",
            "rate_notes": text(row.get("ETC_NOTE_MATTER")),
            "max_rate_amount": {"amount": float(row.get("HGST_INTR_APL_AMT") or 0),
                                "relation": {"1": "이상", "2": "이하", "3": "초과", "4": "미만", "5": "제한없음"}.get(str(row.get("RNG_CODE")), "확인 필요")},
            "join_target": text(row.get("JOIN_TARGET")),
            "payment_cycle": ", ".join({"1": "수시지급", "2": "월지급", "3": "분기지급", "4": "반기지급", "5": "연지급", "6": "기타"}.get(c, "확인 필요") for c in str(row.get("DEPO_INTS_PRVS_MTHD_CD", "")).split(",")),
            "disclosed_on": iso_date(row["START_DATE"]), "source_url": FSB_PAGE,
            "product_url": row.get("PRODUCT_URL") or row.get("URL"),
            "conditions_hash": hashlib.sha256(json.dumps(details, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        })
    return products


def fetch_fsb(client):
    rows, expected, start = [], None, 1
    while True:
        payload = {"ORDERBY": "RATE_HIGH DESC", "RATE_HIGH": "0", "RATE_HIGH_UPPER": "true",
                   "DEPO_INTS_PRVS_MTHD_CD": "1|2|3|4|5|6", "JOIN_LOCATION": "1|2|3|4|5|9",
                   "START_NUM": str(start), "END_NUM": str(start + 99),
                   "SEARCH_SELECT_IN": "", "SEARCH_TEXT_IN": ""}
        # Match encodeURIComponent + form encoding used by FSB's own JEX client.
        data = get_json(client, "https://www.fsb.or.kr/ratanym_0100.jct", method="POST",
                        data={"_JSON_": quote(json.dumps(payload), safe="~()*!.'")},
                        headers={"Referer": FSB_PAGE, "X-Requested-With": "XMLHttpRequest"})
        page = data.get("ANYM_REC", [])
        if data.get("COMMON_HEAD", {}).get("ERROR") or not page:
            raise CollectionError("저축은행 목록 수집 불완전")
        count = int(page[0]["CNT"])
        if expected is not None and count != expected:
            raise CollectionError("수집 도중 저축은행 목록 건수 변경")
        expected = count
        rows.extend(page)
        if len(rows) >= expected:
            break
        start += 100
        if start > 10000:
            raise CollectionError("저축은행 페이지 제한 초과")
    products = parse_fsb(rows)
    if len(products) != expected or len({p["id"] for p in products}) != expected:
        raise CollectionError("저축은행 목록 건수 또는 상품 중복 오류")
    return products


class CollectedProducts(list):
    """Usable rates plus explicit reasons for excluded official base records."""
    def __init__(self):
        super().__init__()
        self.excluded = {}


def fetch_fss(client, kind, group, api_key):
    if not api_key:
        raise CollectionError("FSS_API_KEY 미설정 — 기존 데이터 보존")
    endpoint = "depositProductsSearch.json" if kind == "deposit" else "savingProductsSearch.json"
    products = CollectedProducts()
    for page in range(1, 101):
        data = get_json(client, f"https://finlife.fss.or.kr/finlifeapi/{endpoint}",
                        params={"auth": api_key, "topFinGrpNo": group, "pageNo": page}).get("result", {})
        if str(data.get("err_cd")) != "000":
            raise CollectionError("금감원 API 오류 또는 응답 형식 변경")
        bases, options = data["baseList"], data["optionList"]
        for row in bases:
            # FSS option joins need company + product, not just product code.
            opts = [{"save_trm": int(o["save_trm"]), "intr_rate": number(o["intr_rate"]),
                     "intr_rate2": number(o["intr_rate2"]), "intr_type": o["intr_rate_type_nm"],
                     "rsrv_type": o.get("rsrv_type_nm", "")}
                    for o in options if (o["fin_co_no"], o["fin_prdt_cd"]) == (row["fin_co_no"], row["fin_prdt_cd"])
                    and o.get("intr_rate") is not None and o.get("intr_rate2") is not None]
            if not opts:
                products.excluded[f"FSS_{kind}_{row['fin_co_no']}_{row['fin_prdt_cd']}"] = "공식 목록에 있으나 유효한 기간별 금리 없음"
                continue
            selected = min(opts, key=lambda o: ([12, 24, 6].index(o["save_trm"]) if o["save_trm"] in [12, 24, 6] else 3, -o["save_trm"], o["intr_type"] != "단리"))
            products.append({"id": f"FSS_{kind}_{row['fin_co_no']}_{row['fin_prdt_cd']}",
                             "legacy_id": row["fin_prdt_cd"], "bank": row["kor_co_nm"].strip(),
                             "name": row["fin_prdt_nm"].strip(), "type": kind,
                             "base": selected["intr_rate"], "max": selected["intr_rate2"],
                             "intr_type": selected["intr_type"], "save_trm": selected["save_trm"],
                             "options": opts, "spcl_cnd": (row.get("spcl_cnd") or "").strip(),
                             "join_target": row.get("join_member", ""), "source_url": "https://finlife.fss.or.kr/",
                             "disclosed_on": row.get("dcls_strt_day") and iso_date(row["dcls_strt_day"])})
        if page >= int(data["max_page_no"]):
            return products
    raise CollectionError("금감원 페이지 제한 초과")
