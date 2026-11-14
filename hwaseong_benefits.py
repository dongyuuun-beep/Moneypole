"""Registered official benefit pages, fetched daily; no copied amounts or dates.

Overview, insurance and discount pages never establish open grant applications.
Each registered section has its own identity and failure boundary.
"""
import copy
import re
from bs4 import BeautifulSoup
from support_collectors import CollectionError, clean, dates_from_period, fetch_html, record, text_lines

CITY = 'https://www.hscity.go.kr'
YOUTH = CITY + '/www/partInfo/femaleFamily/Welfare9/Welfare9_4.jsp'
BIRTH = CITY + '/www/partInfo/femaleFamily/Welfare1/Welfare1_2.jsp'
SCHOOL = CITY + '/www/partInfo/eduEmpymn/elechssdyInfo/elechssdyReqst.jsp'

# Only locations and section identities are registered; values come from HTML.
PAGES = [
    dict(url=YOUTH, section='화성시 청년 전·월세 보증금 대출이자 지원', category='주거'),
    dict(url=YOUTH, section='화성시 청년 월세 지원', category='주거'),
    dict(url=BIRTH, section='화성시 출산지원금', category='생활'),
    dict(url=SCHOOL, section='초등학생 입학축하금 지원사업 신청 안내', category='생활'),
    dict(url=CITY + '/hyohaeng/user/bbs/BD_selectBbs.do?q_bbsCode=1048&q_bbscttSn=20261029092828024',
         title='다자녀가구 주택자금 대출이자 지원', category='주거'),
    dict(url=CITY + '/town/user/bbs/BD_selectBbs.do?q_bbsCode=1048&q_bbscttSn=20260716194338594',
         title='결혼장려 연지곤지 통장', category='자산형성'),
    dict(url=CITY + '/www/user/bbs/BD_selectBbs.do?q_bbsCode=1019&q_bbscttSn=20260714105622247',
         title='시민안전보험', category='생활', benefit_type='insurance', summary_match='상해의료비'),
    dict(url=CITY + '/www/user/bbs/BD_selectBbs.do?q_bbsCode=1051&q_bbscttSn=20261113085553527',
         title='착한가격업소 지역화폐 캐시백', category='생활', benefit_type='discount', summary_match='시는 올해 10월부터'),
    dict(url='https://youth.gg.go.kr/gg/info/housing-welfare.do?arcNo=10054&mode=view', title='The 경기패스 교통비 환급',
         category='생활', benefit_type='discount', selector='.fr-view', summary_match='월 15회',
         coverage_label='경기도 공통 · 화성시민 포함'),
    dict(url='https://youth.gg.go.kr/gg/intro/notice.do?articleNo=9749&mode=view', title='경기 기후보험',
         category='생활', benefit_type='insurance', selector='.fr-view', summary_match='기후관련 질병',
         coverage_label='경기도 공통 · 화성시민 포함'),
]


def section_body(soup, title):
    headings = [h for h in soup.select('h3.subCon_title') if clean(h.get_text()) == title]
    if len(headings) != 1:
        raise CollectionError('화성 혜택 항목 누락 또는 중복')
    root = BeautifulSoup('<div></div>', 'html.parser').div
    for sibling in headings[0].next_siblings:
        if getattr(sibling, 'name', None) == 'h3':
            break
        root.append(copy.deepcopy(sibling))
    return root


def field_lines(body):
    lines = text_lines(copy.deepcopy(body))
    # Separate numbered/emoji labels without changing the official values.
    cleaned = [re.sub(r'^(?:\d{1,2}[.)]\s+|[○□🎯🗓️🎁👥🎀]+\s*)', '', line).strip() for line in lines]
    return list(dict.fromkeys(line for line in cleaned if line))


def section_value(body, labels):
    # H4 sections can hold multiple conditions; keep every list item together.
    for h in body.select('h4'):
        if clean(h.get_text()).replace(' ', '') in {x.replace(' ', '') for x in labels}:
            values = []
            for sibling in h.next_siblings:
                if getattr(sibling, 'name', None) in ('h3', 'h4'):
                    break
                if getattr(sibling, 'get_text', None):
                    values.append(clean(sibling.get_text(' ', strip=True)))
            return ' '.join(v for v in values if v)[:600]
    lines = field_lines(body)
    boundaries = re.compile(r'^(?:지원목적|지원대상|신청대상|지원내용|지원조건|지원기간|신청기간|모집기간|모집인원|신청방법|관련문의|제외대상|보험대상|계약기간|보험기간|보장항목|보장내용|신청안내|문의전화|신청서류|신청방법)\s*[:：]?')
    for i, line in enumerate(lines):
        match = re.match(r'^(?:' + '|'.join(map(re.escape, labels)) + r')(?:\s*[:：]\s*|\s*$)', line)
        if match:
            values = [line[match.end():]]
            for following in lines[i + 1:]:
                if boundaries.match(following):
                    break
                values.append(following)
            return ' '.join(v for v in values if v)[:600]
    return ''


def application_dates(period):
    # Korean official notices commonly omit the repeated year on the end date.
    # Resolve only same-year, non-decreasing ranges with a fully dated start.
    value = re.sub(r'\([월화수목금토일]\)', ' ', period)
    value = re.sub(r'(\d)\.\s*(?=\d{1,2}:)', r'\1 ', value)
    start, end = dates_from_period(value)
    if start and end:
        return start, end
    match = re.fullmatch(r'\s*(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})\.?\s*~\s*(\d{1,2})[./-]\s*(\d{1,2})\.?\s*', value)
    if not match:
        return None, None
    year, month, day, end_month, end_day = match.groups()
    return dates_from_period(f'{year}-{month}-{day} ~ {year}-{end_month}-{end_day}')


def parse_benefit(soup, config):
    url = config['url']
    if config.get('section'):
        body = section_body(soup, config['section'])
        title = config['section']
    else:
        bodies = soup.select(config.get('selector', '.txt'))
        body = max(bodies, key=lambda x: len(x.get_text()), default=None)
        if body is None and '/town/' in url:
            cells = soup.select('.table_write td')
            body = max(cells, key=lambda x: len(x.get_text()), default=None)
        title = config['title']
    if body is None or len(clean(body.get_text())) < 40:
        raise CollectionError('화성 혜택 본문 형식 변경')
    # Parsing operates on a copy because multiple benefits share one live page.
    body = copy.deepcopy(body)
    lines = field_lines(body)
    period = section_value(body, ['신청기간', '신청 기간', '모집기간', '접수기간'])
    target = section_value(body, ['지원대상', '지원 대상', '신청대상', '지급대상', '보험대상'])
    support = section_value(body, ['지원내용', '지원 내용', '지원금액', '지급방법', '보장항목', '보장내용'])
    if config.get('summary_match'):
        support = next((line for line in lines if config['summary_match'] in line), '')[:600]
    if not support:
        raise CollectionError('화성 혜택 지원내용 확인 불가')
    kind = config.get('benefit_type', 'grant')
    if kind == 'insurance':
        period = '보장기간: ' + section_value(body, ['계약기간', '보험기간']) + ' · 사고·질병 및 청구요건은 원문 확인'
    elif kind == 'discount':
        period = '이용 조건·운영 기간·예산 소진 여부는 공식 안내와 운영 앱에서 확인'
    state = '마감' if re.search(r'예산\s*소진으로.{0,15}마감|사업\s*마감|접수\s*종료', '\n'.join(lines)) else ''
    # Fragment identifies a section; the source link remains the real page URL.
    identity = url + ('#' + config['section'] if config.get('section') else '')
    item = record('hwaseong', title, identity, body, period, state, target=target, source_url=url)
    item.update(support_text=support, category=config['category'], source_name='경기도 공식 안내' if config.get('coverage_label') else '화성특례시 공식 안내',
                benefit_type=kind, coverage_label=config.get('coverage_label', '화성시'),
                period_kind='coverage' if kind == 'insurance' else 'usage' if kind == 'discount' else 'application')
    if kind == 'grant':
        item['application_start'], item['application_end'] = application_dates(period)
    else:
        item['application_start'] = item['application_end'] = None
    item['notice'] += ' 사업 소개·보험·할인 안내를 현재 지원금 접수 중으로 해석하지 마세요.'
    return item


def collect_benefits(client):
    cached, records, errors = {}, [], []
    for config in PAGES:
        url = config['url']
        if url not in cached:
            try:
                cached[url] = fetch_html(client, url)
            except Exception as exc:
                cached[url] = exc
        try:
            if isinstance(cached[url], Exception):
                raise cached[url]
            records.append(parse_benefit(cached[url], config))
        except Exception as exc:
            errors.append({'url': url, 'section': config.get('section'), 'error': type(exc).__name__})
    return records, errors, len(cached)
