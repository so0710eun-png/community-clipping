"""화제성 점수.

1) 같은 이야기 묶기: 제목을 두 글자 단위로 쪼개 비교해서 비슷하면 한 묶음으로 봅니다.
   (외신 클리핑에서 실제 기사로 시험해 정한 방식·기준값을 그대로 씁니다)
2) 반응: 커뮤니티마다 조회·추천·댓글 규모가 달라서, 같은 커뮤니티 안에서 상위 몇 %인지로 비교합니다.
3) 화제 점수(1~5): 여러 커뮤니티에 동시에 올라온 이야기일수록, 반응이 클수록 높게.
   - 한 커뮤니티에만 있으면 최대 3점, 두 곳이면 4점, 세 곳 이상이면 5점
"""
import math
import re
from datetime import datetime, timedelta

SIM_THRESHOLD = 0.35
PAIR_HOURS = 48
LOW_PERCENTILE = 0.3   # 한 곳에만 있고 그 커뮤니티 안에서 하위 30%면 '반응 적은 글'

STOP_BIGRAMS = {
    "있습", "습니", "니다", "했다", "한다", "에서", "으로", "있다", "이다", "하는", "근황", "현재",
    "ㅋㅋ", "ㅎㅎ", "ㄷㄷ", "ㅠㅠ", "진짜", "오늘", "요즘", "jpg", "gif", "mp4", "webp",
}


def tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[가-힣]+|[A-Za-z0-9]{2,}", text):
        if re.fullmatch(r"[A-Za-z0-9]+", w):
            w = w.lower()
            if w not in STOP_BIGRAMS:
                out.add(w)
            continue
        for i in range(len(w) - 1):
            b = w[i:i + 2]
            if b not in STOP_BIGRAMS:
                out.add(b)
    return out


def engagement(p: dict) -> float:
    return p.get("views", 0) + 20 * p.get("likes", 0) + 10 * p.get("comments", 0)


def fmt(n: int) -> str:
    return f"{n / 10000:.1f}만" if n >= 10000 else f"{n:,}"


def assign(posts: dict[str, dict], names: dict[str, str]) -> None:
    items = sorted(posts.values(), key=lambda p: p["published"])
    n = len(items)
    if not n:
        return

    # 커뮤니티 안에서 반응 백분위 (0=하위, 1=상위)
    by_src: dict[str, list[dict]] = {}
    for p in items:
        by_src.setdefault(p["source"], []).append(p)
    for group in by_src.values():
        ranked = sorted(group, key=engagement)
        for i, p in enumerate(ranked):
            p["pct"] = round(i / max(1, len(ranked) - 1), 3) if len(ranked) > 1 else 0.5

    # 같은 이야기 묶기
    toks = [tokens(p["title"]) for p in items]
    times = [datetime.fromisoformat(p["published"]) for p in items]
    df: dict[str, int] = {}
    for t in toks:
        for b in t:
            df[b] = df.get(b, 0) + 1
    idf = {b: math.log((n + 1) / (c + 0.5)) for b, c in df.items()}
    weight = [sum(idf[b] for b in t) for t in toks]
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if times[j] - times[i] > timedelta(hours=PAIR_HOURS):
                break
            shared = toks[i] & toks[j]
            if len(shared) < 2:
                continue
            denom = min(weight[i], weight[j])
            if denom > 0 and sum(idf[b] for b in shared) / denom >= SIM_THRESHOLD:
                parent[find(j)] = find(i)

    groups: dict[int, list[dict]] = {}
    for i, p in enumerate(items):
        groups.setdefault(find(i), []).append(p)

    for members in groups.values():
        srcs = sorted({m["source"] for m in members})
        best = max(members, key=lambda m: m["pct"])
        heat = 2 * len(srcs) - 1 + 2 * best["pct"]   # 1곳: 1~3, 2곳: 3~5, 3곳: 5~7 ...
        if len(srcs) >= 3:
            score = 5
        elif len(srcs) == 2:
            score = 4
        else:
            score = 1 if best["pct"] < LOW_PERCENTILE else (2 if best["pct"] < 0.7 else 3)
        if len(srcs) > 1:
            reason = f"{len(srcs)}개 커뮤니티에서 화제 (" + " · ".join(names.get(s, s) for s in srcs) + ")"
        else:
            top = max(1, round((1 - best["pct"]) * 100))
            reason = (f"{names.get(best['source'], best['source'])} 상위 {top}% 반응 "
                      f"(조회 {fmt(best.get('views', 0))} · 추천 {fmt(best.get('likes', 0))} · "
                      f"댓글 {fmt(best.get('comments', 0))})")
        cluster = members[0]["id"]
        for m in members:
            m.update(cluster=cluster, heat=round(heat, 2), score=score, reason=reason,
                     low=(len(srcs) == 1 and best["pct"] < LOW_PERCENTILE))
