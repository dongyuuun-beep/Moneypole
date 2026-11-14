import unittest
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup
from hwaseong_benefits import application_dates, parse_benefit, collect_benefits
from collectors import CollectionError


class HwaseongBenefitsTests(unittest.TestCase):
    def soup(self, html):
        return BeautifulSoup(html, 'html.parser')

    def test_distinct_shared_sections_never_mix_amounts_and_preserve_rechecks(self):
        soup = self.soup('''<h3 class="subCon_title">월세 지원</h3><div><ul>
          <li>지원대상: 무주택 청년으로 상세 소득 조건은 별도 확인 필요</li><li>지원내용: 월 15만원, 최대 6개월 지원</li></ul></div>
          <h3 class="subCon_title">출산 지원</h3><div><h4>지원내용</h4><ul><li>첫째 100만원 지급. 거주기간 등 세부 자격과 신청서류는 원문을 확인하세요.</li></ul></div>''')
        config = dict(url='https://www.hscity.go.kr/info', section='월세 지원', category='주거')
        first = parse_benefit(soup, config)
        self.assertIn('15만원', first['support_text'])
        self.assertNotIn('100만원', first['excerpt'])
        second = parse_benefit(soup, dict(config, section='출산 지원'))
        self.assertNotEqual(first['id'], second['id'])
        self.assertIn('100만원', second['support_text'])
        self.assertEqual(first, parse_benefit(soup, config))
        self.assertIsNone(first['application_start'])

    def test_korean_weekdays_keep_exact_deadline_time_and_no_cross_year_guess(self):
        self.assertEqual(application_dates('2026. 3. 3. (화) 9:00 ~ 2026. 11. 27. (금) 23:50'),
                         ('2026-03-03T09:00+09:00', '2026-11-27T23:50+09:00'))
        self.assertEqual(application_dates('2026. 11. 2.(월) ~ 11. 20.(금)')[1], '2026-11-20T23:59+09:00')
        for value in ['2026.12.1 ~ 1.2', '출생일로부터 1년 이내', '2026.2.1 ~ 2.30']:
            self.assertEqual(application_dates(value), (None, None))

    def test_insurance_coverage_dates_are_not_application_dates(self):
        soup = self.soup('''<div class="txt"><p>○ 보험대상: 화성시 모든 시민</p>
          <p>○ 계약기간: 2026. 1. 1. ~ 2026. 12. 31.</p><p>○ 보장항목</p><strong>보장항목</strong>
          <p>- 상해의료비 100만원 한도, 자기부담금 3만원</p></div>''')
        item = parse_benefit(soup, dict(url='https://www.hscity.go.kr/insurance', title='시민안전보험',
            category='생활', benefit_type='insurance'))
        self.assertIsNone(item['application_end'])
        self.assertIn('2026. 1. 1.', item['application_period_text'])
        self.assertIn('100만원', item['support_text'])
        self.assertEqual(item['target_text'], '화성시 모든 시민')

    def test_conditional_budget_warning_does_not_mean_closed(self):
        config = dict(url='https://www.hscity.go.kr/cashback', title='캐시백', category='생활',
                      benefit_type='discount', summary_match='5%')
        soup = self.soup('<div class="txt"><p>지역화폐로 결제하면 5% 캐시백을 지원합니다. 예산 소진 시 조기 마감됩니다.</p></div>')
        item = parse_benefit(soup, config)
        self.assertEqual(item['source_state'], '')
        self.assertIsNone(item['application_end'])
        soup = self.soup('<div class="txt"><p>지역화폐 결제 5% 캐시백 사업 안내입니다. 예산 소진으로 사업 마감되었습니다.</p></div>')
        self.assertEqual(parse_benefit(soup, config)['source_state'], '마감')

    def test_policy_text_is_used_instead_of_image_panel(self):
        soup = self.soup('''<div class="fr-view"><img src="poster.png"></div>
          <div class="fr-view"><ul><li>지원내용: 월 15회 이상 대중교통 이용 시 일반 20% 환급.
          소득 및 연령에 따른 차등 혜택은 운영 안내 확인.</li></ul></div>''')
        item = parse_benefit(soup, dict(url='https://youth.gg.go.kr/info', title='교통비 환급',
            category='생활', benefit_type='discount', selector='.fr-view', summary_match='월 15회'))
        self.assertIn('20%', item['support_text'])
        self.assertIsNone(item['application_end'])

    @patch('hwaseong_benefits.fetch_html')
    def test_missing_section_isolated_and_shared_page_fetched_once(self, fetch):
        fetch.return_value = self.soup('''<h3 class="subCon_title">지원 A</h3>
          <div><p>지원내용: 생활비 최대 10만원을 지원합니다. 자격조건과 예산은 원문을 확인하세요.</p></div>''')
        configs = [dict(url='https://www.hscity.go.kr/info', section=title, category='생활') for title in ['지원 A', '지원 B']]
        with patch('hwaseong_benefits.PAGES', configs):
            items, errors, pages = collect_benefits(Mock())
        self.assertEqual(len(items), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(pages, 1)
        fetch.assert_called_once()
        with self.assertRaises(CollectionError):
            parse_benefit(self.soup('<div>서비스 오류</div>'), configs[0])
