import copy
import unittest
from datetime import date
from unittest.mock import Mock, patch

from collectors import CollectionError, fetch_fsb, fetch_fss, parse_fsb, parse_kb
from update_rates import merge_source, update

STAMP = '2026-11-08T19:00:00+09:00'


def product(id='one', rate=2):
    return {'id': id, 'bank': '은행', 'name': '상품', 'type': 'parking', 'base': rate, 'max': rate,
            'source_id': 'fsb', 'history': [{'date': '2026-11-07', 'rate': rate}],
            'last_checked_at': '2026-11-07T12:00:00+09:00', 'verification_status': 'verified'}


class PreservationTests(unittest.TestCase):
    def test_one_source_failure_preserves_previous_rates_other_source_publishes(self):
        old = product()
        def fail():
            raise TimeoutError('do not leak URL or API key')
        result, report = update([old], {}, {'fsb': fail, 'kb': lambda: [product('two')]}, STAMP)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['max'], 2)
        self.assertEqual(result[0]['last_checked_at'], old['last_checked_at'])
        self.assertEqual(result[0]['verification_status'], 'stale')
        self.assertNotIn('API key', report['sources']['fsb']['message'])
        self.assertEqual(report['sources']['kb']['status'], 'ok')

    def test_empty_or_duplicate_response_never_clears_catalog(self):
        for incoming in [[], [product(), product()]]:
            result, report = update([product()], {}, {'fsb': lambda: incoming}, STAMP)
            self.assertEqual(len(result), 1)
            self.assertEqual(report['sources']['fsb']['status'], 'failed')

    def test_source_merge_is_atomic_if_later_product_is_invalid(self):
        old = [product(), product('two')]
        bad = product('two', 40)
        result, _ = update(old, {}, {'fsb': lambda: [product(rate=3), bad]}, STAMP)
        self.assertEqual([p['max'] for p in result], [2, 2])
        self.assertEqual(old[0]['verification_status'], 'verified')

    def test_missing_product_kept_and_flagged(self):
        result, missing = merge_source([product(), product('two')], [product()], 'fsb', STAMP)
        self.assertEqual(missing, 1)
        self.assertEqual(result[1]['verification_status'], 'missing')

    def test_large_change_rejected_and_manual_review_can_accept(self):
        with self.assertRaises(CollectionError):
            merge_source([product()], [product(rate=6)], 'fsb', STAMP)
        result, _ = merge_source([product()], [product(rate=6)], 'fsb', STAMP, True)
        self.assertEqual(result[0]['max'], 6)

    def test_same_day_rerun_does_not_erase_history(self):
        first, _ = merge_source([product()], [product(rate=3)], 'fsb', STAMP)
        second, _ = merge_source(first, [product(rate=3)], 'fsb', STAMP)
        self.assertEqual(first[0]['history'], second[0]['history'])
        third, _ = merge_source(second, [product(rate=4)], 'fsb', STAMP)
        self.assertEqual(third[0]['history'], [{'date': '2026-11-07', 'rate': 2}, {'date': '2026-11-08', 'rate': 4}])

    def test_legacy_migration_is_company_and_type_specific(self):
        old = [dict(product('x'), bank='A', type='deposit'), dict(product('x'), bank='B', type='savings')]
        new = dict(product('FSS_deposit_A_x'), bank='A', type='deposit', legacy_id='x')
        result, _ = merge_source(old, [new], 'fss', STAMP)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]['bank'], 'B')
        self.assertEqual(len(result[0]['history']), 1)


class OfficialParserTests(unittest.TestCase):
    def kb(self):
        # Synthetic rates. Conflicting corporate/term fields must not be used.
        return {'cma100': '(기준일 : 2026/08/31, 세전)', 'cma111': '연 2.10%', 'cma112': '연 2.20%',
                'cma121': '연 9.9%', 'cma131': '연 8.8%', 'cma001': '31일단위 재투자', 'cma002': '1일단위 재투자'}

    def test_kb_personal_auto_investment_only(self):
        products = parse_kb(self.kb(), date(2026, 11, 8))
        self.assertEqual([p['max'] for p in products], [2.1, 2.2])
        self.assertEqual([p['subtype'] for p in products], ['RP', '발행어음'])
        self.assertTrue(all(p['deposit_protection'] is False for p in products))

    def test_kb_future_or_changed_markup_rejected(self):
        for data in [dict(self.kb(), cma100='(기준일 : 2027/01/01, 세전)'), dict(self.kb(), cma111='공시 중단')]:
            with self.assertRaises(CollectionError):
                parse_kb(data, date(2026, 11, 8))

    def row(self, id='A'):
        return {'BANK_NAME': '테스트', 'PRODUCT_NAME': '통장', 'FINAN_COMP_CODE': '001', 'FINAN_PROD_CODE': id,
                'RATE_LOW': '0.5', 'RATE_HIGH': '5', 'START_DATE': '20261101',
                'HGST_INTR_APL_AMT': '1000000', 'RNG_CODE': '2', 'SWEETENER': '마케팅 동의',
                'ETC_NOTE_MATTER': '100만원 이하분 5%\\n초과분 0.5%'}

    def test_fsb_preserves_conditions_without_guessing_balance_tiers(self):
        item = parse_fsb([self.row()])[0]
        self.assertEqual(item['max_rate_amount'], {'amount': 1000000, 'relation': '이하'})
        self.assertEqual(item['rate_model'], 'unverified_tiers')
        self.assertIn('\n초과분', item['rate_notes'])
        self.assertEqual(item['rate_tiers'], [])

    @patch('collectors.get_json')
    def test_fsb_collects_all_pages_and_rejects_truncation(self, get):
        get.side_effect = [dict(ANYM_REC=[dict(self.row(), CNT='2')]), dict(ANYM_REC=[dict(self.row('B'), CNT='2')])]
        self.assertEqual(len(fetch_fsb(Mock())), 2)
        get.side_effect = [dict(ANYM_REC=[dict(self.row(), CNT='2')]), dict(ANYM_REC=[])]
        with self.assertRaises(CollectionError):
            fetch_fsb(Mock())

    @patch('collectors.get_json')
    def test_fss_failure_on_later_page_does_not_return_partial_products(self, get):
        get.side_effect = [{'result': {'err_cd': '000', 'baseList': [], 'optionList': [], 'max_page_no': 2}}, TimeoutError()]
        with self.assertRaises(TimeoutError):
            fetch_fss(Mock(), 'deposit', '020000', 'synthetic-key')


if __name__ == '__main__':
    unittest.main()
