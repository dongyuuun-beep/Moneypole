"""Daily public HTML collection. No API credentials, no eligibility inference."""
import argparse
import copy
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import CollectionError, session
from support_collectors import REGIONS, collect_region
from update_rates import atomic_json, read_json

ROOT = Path(__file__).resolve().parent


def merge_records(previous, incoming, checked_at):
    result = {item['id']: copy.deepcopy(item) for item in previous}
    for item in incoming:
        if not item.get('title') or not item.get('source_url') or not item.get('content_hash'):
            raise ValueError('지원 공고 필수 필드 누락')
        before = result.get(item['id'], {})
        if not item.get('source_state') and before.get('source_state') in ('마감', '종료', '접수완료'):
            item = {**item, 'source_state': before['source_state']}
        changed = before and before.get('content_hash') != item['content_hash']
        result[item['id']] = {**item, 'first_seen_at': before.get('first_seen_at', checked_at),
                             'last_checked_at': checked_at, 'verification_status': 'collected',
                             'changed_at': checked_at if changed else before.get('changed_at'),
                             'review_status': '원문 확인 필요'}
    return list(result.values())


def run(previous, previous_report, collect, checked_at):
    result = copy.deepcopy(previous)
    report = {'checked_at': checked_at, 'timezone': 'Asia/Seoul', 'sources': {},
              'collection_method': '공식 홈페이지 HTML · API 키 불필요',
              'scope_note': '등록된 공식 게시판의 제한된 검색 범위입니다. 각 지역의 모든 지원사업을 포함하지 않으며 수급 자격을 판정하지 않습니다.'}
    with ThreadPoolExecutor(max_workers=5) as executor:
        pending = {executor.submit(collect, key, previous): key for key in REGIONS}
        for future in as_completed(pending):
            key = pending[future]
            config = REGIONS[key]
            old = previous_report.get('sources', {}).get(key, {})
            meta = {'name': config['name'], 'source_name': config['source_name'], 'url': config['url'], 'scope': config['scope']}
            try:
                incoming, errors, pages = future.result()
                if len({p['id'] for p in incoming}) != len(incoming):
                    raise ValueError('지원 공고 ID 중복')
                result = merge_records(result, incoming, checked_at)
                ids = {p['id'] for p in incoming}
                for item in result:
                    if item['region'] == key and item['id'] not in ids:
                        item['verification_status'] = 'stale'
                report['sources'][key] = {**meta, 'status': 'partial' if errors else 'ok',
                    'last_success_at': checked_at if not errors else old.get('last_success_at'),
                    'count': len(incoming), 'pages_checked': pages, 'detail_failures': len(errors),
                    'message': '일부 원문 확인 실패 · 이전 값 보존' if errors else '공식 페이지 수집 완료'}
            except Exception as exc:
                for item in result:
                    if item['region'] == key:
                        item['verification_status'] = 'stale'
                reason = str(exc) if isinstance(exc, CollectionError) else type(exc).__name__
                report['sources'][key] = {**meta, 'status': 'failed', 'count': 0,
                    'last_success_at': old.get('last_success_at'),
                    'message': f'{reason}: 공식 페이지 확인 실패 · 이전 값 보존'}
    # Stable report order and item order make diffs easier to inspect.
    report['sources'] = {key: report['sources'][key] for key in REGIONS}
    return sorted(result, key=lambda x: (x['region'], x['id'])), report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = read_json(args.output_dir / 'support.json', [])
    old = read_json(args.output_dir / 'support_status.json', {})
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')

    def collect(key, previous):
        with session() as client:
            return collect_region(client, key, previous)

    result, report = run(data, old, collect, stamp)
    atomic_json(args.output_dir / 'support.json', result)
    atomic_json(args.output_dir / 'support_status.json', report)
    summary = ['## 지역 지원 공고 확인', '', f'확인 시각: {stamp}', '', '| 지역 | 상태 | 공고 수 |', '|---|---|---:|']
    for key, value in report['sources'].items():
        print(f"{value['name']}: {value['status']} ({value['count']}) {value['message']}")
        summary.append(f"| {value['name']} | {value['status']} | {value['count']} |")
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('\n'.join(summary) + '\n')
    return int(any(v['status'] != 'ok' for v in report['sources'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
