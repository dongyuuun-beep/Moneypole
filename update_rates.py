"""Daily collection with independent source failures and atomic publication."""
import argparse
import copy
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import CollectionError, fetch_fsb, fetch_fss, fetch_kb, fetch_kakao, session

ROOT = Path(__file__).resolve().parent


def read_json(path, default):
    if not path.exists():
        return default
    # Corrupt existing data must stop a run rather than empty the catalog.
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def merge_source(existing, incoming, source_id, checked_at, accept_large_changes=False):
    if not incoming:
        raise CollectionError("수집 결과 없음 — 기존 데이터 보존")
    if len({p["id"] for p in incoming}) != len(incoming):
        raise CollectionError("상품 ID 중복")
    result = copy.deepcopy(existing)
    today = checked_at[:10]
    for item in incoming:
        if not item.get("bank") or not item.get("name") or not 0 <= item["base"] <= item["max"] <= 30:
            raise CollectionError("필수 상품 정보 또는 금리 범위 오류")
        if item.get("effective_from", today) > today:
            raise CollectionError("미래 적용일 금리")
        previous = next((p for p in result if p["id"] == item["id"]), None)
        if previous is None and item.get("legacy_id"):
            candidates = [p for p in result if p.get("type") == item["type"] and p.get("bank") == item["bank"]
                          and p.get("id") == item["legacy_id"]]
            if len(candidates) > 1:
                raise CollectionError("기존 상품 ID 매칭 모호함")
            previous = candidates[0] if candidates else None
        if previous and not accept_large_changes and any(abs(item[k] - previous.get(k, item[k])) > 3 for k in ("base", "max")):
            raise CollectionError("3%p 초과 금리 변동 — 공식 출처 검토 후 수동 승인 필요")
        history = [h for h in (previous or {}).get("history", []) if h["date"] != today]
        if not history or round(history[-1]["rate"], 4) != round(item["max"], 4):
            history.append({"date": today, "rate": item["max"]})
        fresh = {**item, "source_id": source_id, "last_checked_at": checked_at,
                 "verification_status": "verified", "history": history}
        fresh.pop("legacy_id", None)
        if previous:
            result[result.index(previous)] = fresh
        else:
            result.append(fresh)
    # An omitted product is not proof it has been discontinued.
    ids = {p["id"] for p in incoming}
    missing = 0
    for p in result:
        if p.get("source_id") == source_id and p["id"] not in ids:
            p["verification_status"] = "missing"
            missing += 1
    return result, missing


def update(data, previous_status, sources, checked_at, accept_large_changes=False):
    result = copy.deepcopy(data)
    report = {"checked_at": checked_at, "timezone": "Asia/Seoul", "sources": {},
              "coverage": {"bank_parking": "카카오뱅크 세이프박스 (개별 공식 페이지)", "savings_bank_parking": "FSB", "cma": "KB증권 개인 RP·발행어음형"}}
    for source_id, collect in sources.items():
        old_status = previous_status.get("sources", {}).get(source_id, {})
        try:
            incoming = collect()
            result, missing = merge_source(result, incoming, source_id, checked_at, accept_large_changes)
            report["sources"][source_id] = {"status": "partial" if missing else "ok", "count": len(incoming),
                "missing_count": missing, "last_success_at": checked_at,
                "message": "이전 목록 중 누락 상품 보존" if missing else "수집 완료"}
        except Exception as exc:
            # API keys can appear in request exception URLs; never print those.
            message = str(exc) if isinstance(exc, CollectionError) else f"{type(exc).__name__} — 응답·네트워크 확인 필요"
            report["sources"][source_id] = {"status": "failed", "count": 0,
                "last_success_at": old_status.get("last_success_at"), "message": message}
            for p in result:
                if p.get("source_id") == source_id:
                    p["verification_status"] = "stale"
    report["sources"]["kfb_parking"] = {"status": "unavailable", "count": 0,
        "message": "기존 은행연합회 URL 오류 응답 확인. 시중은행 통합 목록은 미지원.",
        "source_url": "https://portal.kfb.or.kr/compare/free_deposit.php"}
    return result, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--accept-large-changes", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = read_json(args.output_dir / "data.json", [])
    status = read_json(args.output_dir / "update_status.json", {})
    checked_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    with session() as client:
        sources = {f"fss_{kind}_{group}": (lambda k=kind, g=group: fetch_fss(client, k, g, os.getenv("FSS_API_KEY")))
                   for kind in ("deposit", "savings") for group in ("020000", "030300")}
        sources.update({"fsb_parking": lambda: fetch_fsb(client), "kb_cma": lambda: fetch_kb(client),
                        "kakao_parking": lambda: fetch_kakao(client)})
        data, report = update(data, status, sources, checked_at, args.accept_large_changes)
    atomic_json(args.output_dir / "data.json", data)
    atomic_json(args.output_dir / "update_status.json", report)
    lines = ["## MoneyPole 금리 수집", "", f"확인 시각: {checked_at}", "", "| 출처 | 상태 | 건수 | 설명 |", "|---|---|---:|---|"]
    for key, value in report["sources"].items():
        print(f"{key}: {value['status']} ({value['count']}) {value['message']}")
        lines.append(f"| {key} | {value['status']} | {value['count']} | {value['message']} |")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
    return 1 if any(s["status"] in ("failed", "partial") for s in report["sources"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
