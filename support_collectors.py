"""No-key HTML collectors for five official local support sources.

A listing is discovery, not proof of eligibility or an open application window.
Only labeled application dates and explicit source status drive application state.
"""
import hashlib
import html
import re
from datetime import timedelta
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from collectors import CollectionError

REGIONS = {
    'seoul': {'name': '서울시', 'source_name': '서울시 청년몽땅정보통',
              'url': 'https://youth.seoul.go.kr/infoData/sprtInfo/list.do?key=2309130006',
              'scope': '공식 포털의 지원금·월세·응시료·이사비 검색 공고. 자치구별 거주 조건 별도 확인.'},
    'hwaseong': {'name': '화성시', 'source_name': '화성시 청년취업끝까지지원센터',
                 'url': 'https://youthjob.hscity.go.kr/board/notice_list.jsp',
                 'scope': '시 공식 센터 공지의 개인 대상 비용·수당 지원 공고.'},
    'yongin': {'name': '용인시', 'source_name': '용인청년포털 청년e랑',
               'url': 'https://youth.yongin.go.kr/web/main/youthPolicy/list',
               'scope': '시 청년 지원사업 목록 중 개인 대상 비용·수당·자산형성 지원.'},
    'busan': {'name': '부산시', 'source_name': '부산경제진흥원 부산일자리정보망',
              'url': 'https://www.busanjob.net/',
              'scope': '공식 수행기관 포털의 개인 지원정책 안내. 신청기간은 개별 공고 확인 필요.'},
    'buan': {'name': '부안군', 'source_name': '부안군 고시·공고·입법예고',
             'url': 'https://www.buan.go.kr/board/list.buan?boardId=BBS_0000054&menuCd=DOM_000000103001003000',
             'scope': '군 공식 고시·공고의 지원 공고 검색. 개인 대상 후보이며 세부 지원대상은 원문 확인.'},
}

POSITIVE = re.compile(r'지원금|응원금|수당|기본소득|월세|주거비|이사비|중개보수|보증료|이자\s*지원|응시료|구입비|장학금|생활비|교통비|기쁨두배|디딤돌|취업성공풀|내일저축|누림통장|지원사업')
NEGATIVE = re.compile(r'채용|기간제|위원\s*모집|위원회|운영기관|수행기관|민간위탁|입찰|용역|공사\s*공고|기업\s*모집|대상기업|단체\s*모집|사업자\s*모집|선정\s*결과|선발\s*결과|합격자|지급신청|제출\s*서류\s*안내|활동가\s*모집|커뮤니티|공시송달|독촉|환수|지방보조금|희망업소|학교체육시설')


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(html.unescape(str(value or '')))).strip()


def safe_link(url, base):
    parsed = urlsplit(urljoin(base, url))
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))


def fetch_html(client, url):
    host = urlsplit(url).hostname
    allowed = {urlsplit(v['url']).hostname for v in REGIONS.values()} | {'busanjob.net'}
    if host not in allowed:
        raise CollectionError('지원금 출처 호스트 불일치')
    # Do not follow arbitrary links/redirects from scraped content.
    for _ in range(4):
        response = client.get(url, timeout=(10, 25), allow_redirects=False)
        if response.is_redirect:
            target = safe_link(response.headers.get('Location', ''), url)
            if not target or urlsplit(target).hostname not in allowed:
                raise CollectionError('공식 출처 외부 리다이렉트')
            url = target
            continue
        response.raise_for_status()
        if len(response.content) > 3_000_000:
            raise CollectionError('공고 HTML 크기 제한 초과')
        soup = BeautifulSoup(response.content, 'html.parser')
        if len(soup.get_text(strip=True)) < 100:
            raise CollectionError('공고 대신 오류·리다이렉트 페이지 수신')
        return soup
    raise CollectionError('공고 리다이렉트 횟수 초과')


def dates_from_period(value):
    """No inferred years or generic page dates: only complete labeled ranges."""
    matches = re.findall(r'(20\d{2})[-./]\s*(\d{1,2})[-./]\s*(\d{1,2})(?:\s+(\d{1,2})\s*:\s*(\d{2}))?', value or '')
    if len(matches) != 2:
        return None, None
    result = []
    try:
        for i, (year, month, day, hour, minute) in enumerate(matches):
            h, m = (int(hour), int(minute)) if hour else ((0, 0) if i == 0 else (23, 59))
            result.append(datetime(int(year), int(month), int(day), h, m, tzinfo=ZoneInfo('Asia/Seoul')).isoformat(timespec='minutes'))
        if result[1] < result[0]:
            return None, None
    except ValueError:
        return None, None
    return tuple(result)


def relevant(title):
    years = [int(value) for value in re.findall(r'(20\d{2})년', title)]
    year = datetime.now(ZoneInfo('Asia/Seoul')).year
    return bool(POSITIVE.search(title)) and not NEGATIVE.search(title) and (not years or max(years) >= year)


def category(title):
    for name, pattern in [('주거', r'월세|주거|이사|중개|보증|임차'), ('취업·교육', r'취업|구직|응시|자격|교육|디딤돌|응원금'),
                          ('자산형성', r'저축|통장|예금|기본소득'), ('생활', r'생활|교통|수당|장학|출발|지원금')]:
        if re.search(pattern, title):
            return name
    return '기타 지원'


def canonical(url, keys):
    p = urlsplit(url)
    query = parse_qs(p.query)
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode({k: query[k][0] for k in keys if query.get(k)}), ''))


def text_lines(root):
    for tag in root.select('script,style,button,.book_mark,.btn-group'):
        tag.decompose()
    lines = []
    for tag in root.find_all(['p', 'li', 'tr', 'h3', 'h4', 'strong']):
        value = clean(tag.get_text(' ', strip=True))
        if value and value not in lines and len(value) < 3000:
            lines.append(value)
    return lines or [clean(root.get_text(' ', strip=True))]


def labeled_lines(lines, labels):
    for i, line in enumerate(lines):
        if any(line.startswith(label) for label in labels):
            value = re.sub(r'^(?:' + '|'.join(map(re.escape, labels)) + r')\s*[:：]?\s*', '', line)
            if value:
                return value[:600]
            if i + 1 < len(lines):
                return lines[i + 1][:600]
    return ''


def record(region, title, url, body, period='', source_state='', published=None, target='', source_url=None, attachments=None):
    if len(clean(body.get_text(' ', strip=True))) < 10:
        if body.select_one('img'):
            note = BeautifulSoup('<p>본문은 이미지로 제공됩니다. 지원내용·신청기간은 공식 원문과 첨부파일에서 확인하세요.</p>', 'html.parser')
            body.append(note)
        else:
            raise CollectionError('공고 본문 누락')
    lines = text_lines(body)
    excerpt = '\n'.join(lines)[:12000]
    start, end = dates_from_period(period)
    # Keep support wording intact; never calculate a benefit total from loose numbers.
    support = labeled_lines(lines, ['지원내용', '지원금액', '지원 내용', '지원 금액'])
    if not support or not re.search(r'만원|만\s*원|원\b|매칭|감면|비용|수당|지원', support):
        support = ''
    target = target or labeled_lines(lines, ['지원대상', '지원 대상', '신청자격', '신청 자격'])
    fingerprint = hashlib.sha256((title + excerpt + period + source_state).encode()).hexdigest()
    return {'id': f"{region}_" + hashlib.sha256(url.encode()).hexdigest()[:16], 'region': region,
            'region_name': REGIONS[region]['name'], 'title': clean(title), 'category': category(title),
            'support_text': support, 'target_text': target, 'application_period_text': clean(period),
            'application_start': start, 'application_end': end, 'source_state': clean(source_state),
            'published_on': published, 'source_name': REGIONS[region]['source_name'],
            'source_url': source_url or url, 'detail_url': url, 'excerpt': excerpt,
            'attachments': attachments or [], 'content_hash': fingerprint,
            'notice': '공식 페이지 자동 수집 정보입니다. 세부 거주지·소득·중복수급·예산소진 여부와 신청 자격은 원문에서 확인하세요.'}


def parse_seoul_list(soup):
    nodes = soup.select('.feed-item a[onclick*="goView"]')
    if not nodes:
        if soup.select_one('.category-feed'):
            return []
        raise CollectionError('서울 지원정보 목록 형식 변경')
    found = []
    for a in nodes:
        match = re.fullmatch(r"goView\('(\d+)'\);?", a.get('onclick', '').strip())
        if not match:
            continue
        item = a.find_parent(class_='feed-item')
        title_node = item.select_one('.name, .tit')
        title = clean(title_node.get_text(' ', strip=True) if title_node else a.get_text())
        title = re.sub(r'\s*\.{3,}\d+$', '', title)
        status_node = item.select_one('.state')
        state = clean(status_node.get_text()) if status_node else ''
        url = 'https://youth.seoul.go.kr/infoData/sprtInfo/view.do?' + urlencode({'key': '2309130006', 'sprtInfoId': match[1]})
        found.append((title, url, state))
    return found


def parse_seoul_detail(soup, title, url, state):
    body = soup.select_one('.feed-view')
    if not body:
        raise CollectionError('서울 지원정보 본문 형식 변경')
    period = ''
    for li in body.select('.overview .info li'):
        heading = li.select_one('em')
        if heading and clean(heading.get_text()) == '신청기간':
            period = clean(li.get_text(' ', strip=True)).removeprefix('신청기간').strip()
    actual = body.select_one('.overview .tit strong')
    return record('seoul', actual.get_text() if actual else title, url, body, period, state)


def parse_yongin_list(soup):
    nodes = soup.select('a[href*="/youthPolicy/view?bizId="]')
    if not nodes:
        raise CollectionError('용인 지원사업 목록 형식 변경')
    result = []
    for a in nodes:
        title = a.select_one('.tit')
        state = a.select_one('.progress-label')
        if title:
            result.append((clean(title.get_text()), canonical(urljoin(REGIONS['yongin']['url'], a['href']), ['bizId']), clean(state.get_text()) if state else ''))
    return result


def parse_yongin_detail(soup, title, url, state):
    body = soup.select_one('.board-view')
    if not body:
        raise CollectionError('용인 지원사업 본문 형식 변경')
    period = ''
    for li in body.select('.board-info > li'):
        label, value = li.select_one('.cate'), li.select_one('.info')
        if label and value and clean(label.get_text()) == '신청기간':
            period = clean(value.get_text(' ', strip=True))
    status_node = body.select_one('.progress-label')
    if status_node:
        state = clean(status_node.get_text())
    support_text = ''
    for heading in body.select('.view-box h4'):
        if clean(heading.get_text()) == '지원내용':
            support_text = clean(heading.parent.get_text(' ', strip=True)).removeprefix('지원내용').strip()
    item = record('yongin', title, url, body, period, state)
    if support_text:
        # A source section can include conditions as well as an amount. Keep it verbatim.
        item['support_text'] = support_text[:600]
    return item


def parse_hwaseong_list(soup):
    nodes = soup.select('a[href*="notice_view.jsp?private_code="]')
    if not nodes:
        raise CollectionError('화성 센터 공지 목록 형식 변경')
    return [(clean(a.get_text()), canonical(urljoin(REGIONS['hwaseong']['url'], a['href']), ['private_code']), '') for a in nodes]


def parse_hwaseong_detail(soup, title, url, state):
    body = soup.select_one('.boardView .writebx')
    if not body:
        raise CollectionError('화성 공지 본문 형식 변경')
    # Image/HWP-only application dates remain unknown, never taken from post dates.
    date_match = re.search(r'작성일\s*:\s*(\d{4}-\d{2}-\d{2})', soup.select_one('.boardView .title').get_text(' ', strip=True))
    return record('hwaseong', title, url, body, published=date_match[1] if date_match else None)


def parse_buan_list(soup):
    nodes = soup.select('td.title a[href*="/board/view.buan?"]')
    if not nodes:
        raise CollectionError('부안 공고 목록 형식 변경')
    return [(clean(a.get_text()), canonical(urljoin(REGIONS['buan']['url'], a['href']), ['boardId', 'menuCd', 'dataSid']), '') for a in nodes]


def parse_buan_detail(soup, title, url, state):
    body = soup.select_one('.bbs_view .bbs_con')
    if not body:
        raise CollectionError('부안 공고 본문 형식 변경')
    attachments = []
    for a in soup.select('.bbs_filedown a[href*="download.buan"]'):
        href = safe_link(a['href'], url)
        if href:
            attachments.append({'name': clean(a.get_text()), 'url': href})
    date_match = re.search(r'작성일\s*:\s*(\d{4}\.\d{2}\.\d{2})', soup.select_one('.bbs_vtop').get_text(' ', strip=True))
    return record('buan', title, url, body, published=date_match[1].replace('.', '-') if date_match else None, attachments=attachments)


def parse_busan(soup):
    nodes = soup.select('.m-policy__lst a.card')
    if not nodes or '부산경제진흥원' not in soup.get_text():
        raise CollectionError('부산 공식 포털 정책 목록 형식 변경')
    result = []
    for a in nodes:
        title, body = a.select_one('.tit'), a.select_one('.cont')
        if not title or not body:
            continue
        name = clean(title.get_text())
        # This portal also lists employer grants: select personal cash/asset aid.
        if not re.search(r'디딤돌|기쁨두배통장|취업성공풀|청년도전', name):
            continue
        destination = safe_link(a.get('href', ''), REGIONS['busan']['url'])
        if not destination:
            continue
        item = record('busan', name, destination, body, source_url=REGIONS['busan']['url'])
        item['support_text'] = clean(body.get_text(' ', strip=True))[:600]
        item['notice'] += ' 공식 수행기관의 사업 안내이며 모집 중임을 뜻하지 않습니다. 개별 신청 공고의 기간을 확인하세요.'
        result.append(item)
    if not result:
        raise CollectionError('부산 개인 지원정책 안내 없음')
    return result


PARSERS = {'seoul': (parse_seoul_list, parse_seoul_detail), 'hwaseong': (parse_hwaseong_list, parse_hwaseong_detail),
           'yongin': (parse_yongin_list, parse_yongin_detail), 'buan': (parse_buan_list, parse_buan_detail)}


def collect_region(client, region, previous):
    """Bounded rolling discovery, plus rechecking known details. No completeness claim."""
    config = REGIONS[region]
    if region == 'busan':
        return parse_busan(fetch_html(client, config['url'])), [], 1
    candidates = {}
    pages_checked = 0
    listing, detail = PARSERS[region]
    if region == 'seoul':
        urls = [config['url'] + '&' + urlencode({'sw': word, 'pageIndex': page})
                for word in ['지원금', '월세', '응시료', '이사비'] for page in [1, 2]]
    elif region == 'hwaseong':
        urls = [config['url'] + f'?pg={page}' for page in [1, 2, 3]]
    elif region == 'yongin':
        urls = [config['url'] + f'?cp={page}&pageSize=12' for page in [1, 2, 3]]
    else:
        urls = [config['url'] + '&' + urlencode({'keyword': word, 'searchType': 'DATA_TITLE', 'startPage': page})
                for word in ['청년', '지원금', '지원사업'] for page in [1, 2]]
    for url in urls:
        soup = fetch_html(client, url)
        try:
            rows = listing(soup)
        except CollectionError:
            # Empty search pages are valid only with an explicit no-results message.
            if any(x in soup.get_text() for x in ['검색된 결과가 없습니다', '게시물이 없습니다', '등록된 게시물이 없습니다', '등록된 데이터가 없습니다']):
                pages_checked += 1
                continue
            raise
        pages_checked += 1
        for title, href, state in rows:
            if relevant(title):
                candidates[href] = (title, href, state)
    # Refresh previous detail pages too, even after they fall off a listing page.
    for old in previous:
        if old['region'] == region:
            candidates.setdefault(old['detail_url'], (old['title'], old['detail_url'], ''))
    records, errors = [], []
    for title, url, state in list(candidates.values())[:45]:
        try:
            item = detail(fetch_html(client, url), title, url, state)
            cutoff = (datetime.now(ZoneInfo('Asia/Seoul')) - timedelta(days=365)).date().isoformat()
            if item.get('published_on') and item['published_on'] < cutoff:
                continue
            records.append(item)
        except Exception as exc:
            errors.append({'url': url, 'error': type(exc).__name__})
    if len(candidates) > 45:
        errors.append({'error': 'DetailLimit', 'remaining': len(candidates) - 45})
    return records, errors, pages_checked
