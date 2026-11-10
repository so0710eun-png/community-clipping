"""3시간마다 실행: 커뮤니티 인기글 수집 → 걸러내기 → 화제성 점수 → docs/posts.json 저장.

실행: python scripts/main.py   (API 키 등 필요 없음, 0원)
"""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filters import blocked_reason, is_junk  # noqa: E402
from sources import SOURCES  # noqa: E402
from topic import assign  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS_FILE = ROOT / "docs" / "posts.json"
KEEP_DAYS = 7  # 이보다 오래된 글은 정리


def post_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")
    db = json.loads(POSTS_FILE.read_text(encoding="utf-8")) if POSTS_FILE.exists() else {}
    posts: dict[str, dict] = {p["id"]: p for p in db.get("posts", [])}
    names = {key: label for key, label, _ in SOURCES}
    status = {}
    hidden = {}

    for key, label, fn in SOURCES:
        try:
            items = fn()
        except Exception as e:  # 한 커뮤니티가 실패해도 나머지는 계속
            print(f"[실패] {label}: {e}")
            status[key] = {"name": label, "ok": False, "count": 0}
            continue
        new = 0
        for it in items:
            if not it["title"] or not it["url"]:
                continue
            pid = post_id(it["url"])
            if pid in posts:  # 이미 있는 글은 조회·추천·댓글 수만 최신으로
                p = posts[pid]
                for k in ("views", "likes", "comments"):
                    p[k] = max(p.get(k, 0), it.get(k, 0))
                p["last_seen"] = now_iso
                continue
            posts[pid] = {
                "id": pid, "source": key, "board": it.get("board", ""),
                "title": it["title"], "url": it["url"],
                "views": it.get("views", 0), "likes": it.get("likes", 0), "comments": it.get("comments", 0),
                "published": it.get("published") or now_iso,
                "first_seen": now_iso, "last_seen": now_iso,
            }
            new += 1
        status[key] = {"name": label, "ok": True, "count": len(items)}
        print(f"  {label}: 목록 {len(items)}건, 새 글 {new}건")

    # 걸러내기 (기준이 바뀌면 이미 저장된 글에도 다시 적용) + 오래된 글 정리
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    kept = {}
    for pid, p in posts.items():
        if p["published"] < cutoff:
            continue
        reason = blocked_reason(p["title"]) or ("똥글" if is_junk(p["title"]) else None)
        if reason:
            hidden[reason] = hidden.get(reason, 0) + 1
            continue
        kept[pid] = p
    print(f"  걸러낸 글: {hidden}")

    assign(kept, names)
    out = sorted(kept.values(), key=lambda p: p["published"], reverse=True)
    POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSTS_FILE.write_text(json.dumps({
        "updated": now_iso, "sources": status, "hidden": hidden, "posts": out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료: {len(out)}건 저장")


if __name__ == "__main__":
    main()
