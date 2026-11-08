import unittest
from copy import deepcopy
from bs4 import BeautifulSoup

from support_collectors import (CollectionError, dates_from_period, parse_busan, parse_seoul_list,
    parse_yongin_detail, parse_hwaseong_detail, relevant)
from update_support import merge_records, run

STAMP='2026-11-08T20:00:00+09:00'

def notice(region='seoul', hash='same'):
    return {'id':region+'_1','region':region,'title':'개인 지원금 공고','source_url':'https://example.go.kr/',
            'detail_url':'https://example.go.kr/notice/1','content_hash':hash,'source_state':'',
            'last_checked_at':'2026-11-07T12:00:00+09:00','verification_status':'collected'}

class SupportTests(unittest.TestCase):
    def test_only_complete_labeled_ranges_produce_dates(self):
        self.assertEqual(dates_from_period('2026-11-02 09:00 ~ 2026-12-01 18:00'),
                         ('2026-11-02T09:00+09:00','2026-12-01T18:00+09:00'))
        for text in ['작성일 2026-11-01', '2026.11.02 ~ 12.01', '2026-12-31 ~ 2026-01-01', '2026-02-30 ~ 2026-03-02']:
            self.assertEqual(dates_from_period(text),(None,None))

    def test_date_only_end_is_end_of_day_in_korea(self):
        self.assertEqual(dates_from_period('2026-11-01 ~ 2026-11-08')[1],'2026-11-08T23:59+09:00')

    def test_job_and_provider_procurement_are_not_personal_grants(self):
        for title in ['지원금 지급 기간제근로자 채용','청년 지원사업 수행기관 모집','청년위원 모집','지원금 환수 공시송달']:
            self.assertFalse(relevant(title))
        self.assertTrue(relevant('청년 월세 지원사업 신청 안내'))

    def test_source_closed_label_not_title_word_controls_state(self):
        soup=BeautifulSoup('''<div class="feed-item"><a onclick="goView('123');">마감 임박 지원금</a>
             <div class="name">마감 임박 지원금</div><span class="state">모집중</span></div>''','html.parser')
        self.assertEqual(parse_seoul_list(soup)[0][2],'모집중')
        self.assertEqual(parse_seoul_list(BeautifulSoup('<div class="category-feed"></div>','html.parser')),[])
        with self.assertRaises(CollectionError):
            parse_seoul_list(BeautifulSoup('<p>접속 오류</p>','html.parser'))

    def test_yongin_preserves_early_closed_even_before_deadline(self):
        soup=BeautifulSoup('''<div class="board-view"><span class="progress-label">마감</span>
          <ul class="board-info"><li><div class="cate">신청기간</div><div class="info">2026-11-01 ~ 2026-12-01</div></li></ul>
          <div class="view-box"><div class="guide-box"><h4>지원내용</h4><p>교통비 최대 10만원 지원. 조건은 원문 확인.</p></div></div></div>''','html.parser')
        result=parse_yongin_detail(soup,'교통비 지원','https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=test','모집중')
        self.assertEqual(result['source_state'],'마감')
        self.assertIn('최대 10만원',result['support_text'])

    def test_posted_date_does_not_become_application_date(self):
        soup=BeautifulSoup('''<div class="boardView"><div class="title">작성일 : 2026-11-01</div>
          <div class="writebx"><p>지원사업 모집 공고입니다. 자세한 신청기간과 자격은 첨부 공고문을 확인하세요.</p></div></div>''','html.parser')
        item=parse_hwaseong_detail(soup,'지원금','https://youthjob.hscity.go.kr/board/notice_view.jsp?private_code=test','')
        self.assertEqual(item['published_on'],'2026-11-01')
        self.assertIsNone(item['application_end'])

    def test_busan_business_overview_is_not_marked_open(self):
        soup=BeautifulSoup('''<footer>부산경제진흥원</footer><div class="m-policy__lst">
         <a class="card" href="https://example.go.kr"><div class="tit">부산청년 디딤돌카드</div><div class="cont">월 10만원씩 최대 3개월 지원, 세부 조건은 개별 공고 확인</div></a>
         <a class="card" href="https://example.go.kr/company"><div class="tit">기업 채용지원금</div><div class="cont">기업당 채용 보조금 지원</div></a></div>''','html.parser')
        items=parse_busan(soup)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['source_state'],'')
        self.assertIsNone(items[0]['application_end'])

    def test_failed_region_preserves_old_data_other_regions_publish(self):
        old=notice()
        def collect(region, previous):
            if region=='seoul':raise TimeoutError('do not log arbitrary network response')
            return [notice(region)],[],1
        data,status=run([old],{},collect,STAMP)
        self.assertEqual(len(data),5)
        previous=next(p for p in data if p['region']=='seoul')
        self.assertEqual(previous['last_checked_at'],old['last_checked_at'])
        self.assertEqual(previous['verification_status'],'stale')
        self.assertEqual(status['sources']['seoul']['status'],'failed')
        self.assertEqual(status['sources']['busan']['status'],'ok')
        self.assertEqual(old['verification_status'],'collected')

    def test_changed_content_and_rerun_keep_first_seen(self):
        first=merge_records([], [notice()],STAMP)
        second=merge_records(first,[notice(hash='new')],'2026-11-09T20:00:00+09:00')
        self.assertEqual(second[0]['first_seen_at'],STAMP)
        self.assertEqual(second[0]['changed_at'],'2026-11-09T20:00:00+09:00')
        third=merge_records(second,[notice(hash='new')],'2026-11-10T20:00:00+09:00')
        self.assertEqual(third[0]['changed_at'],second[0]['changed_at'])

    def test_unknown_new_state_cannot_reopen_an_explicitly_closed_notice(self):
        old=notice();old['source_state']='마감'
        self.assertEqual(merge_records([old],[notice()],STAMP)[0]['source_state'],'마감')

    def test_missing_from_discovery_is_preserved_and_stale(self):
        def collect(region, previous):return [],[],1
        data,status=run([notice()],{},collect,STAMP)
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['verification_status'],'stale')
        self.assertEqual(status['sources']['seoul']['status'],'ok')
