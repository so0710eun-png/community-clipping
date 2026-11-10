"""커뮤니티별 인기글 목록 읽기.

각 함수는 [{title, url, board, views, likes, comments, published}] 목록을 돌려줍니다.
본문은 읽지 않고 '목록 화면'의 제목·링크·숫자만 씁니다.
사이트 화면 구조가 바뀌면 그 커뮤니티 함수만 고치면 됩니다.

2026-11-10 GitHub 서버에서 접속 시험:
  가능: 디시인사이드, 뽐뿌(RSS), 보배드림, 웃긴대학, 루리웹, 클리앙, 인스티즈
  불가: 에펨코리아(해외 서버 차단 430), 더쿠(목록을 스크립트로 불러와 읽을 수 없음),
        네이트판(robots.txt로 수집 금지)
"""
import html
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
USER_AGENT = ("Mozilla/5.0 (compatible; community-clipping/1.0; "
              "+https://github.com/so0710eun-png/community-clipping)")


def fetch(url: str, encoding: str = "utf-8") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode(encoding, "ignore")


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def num(s: str) -> int:
    d = re.sub(r"[^\d]", "", clean(s or ""))
    return int(d) if d else 0


def parse_kst(s: str) -> str | None:
    """여러 날짜 표기를 ISO(UTC)로. 시각만 있으면 오늘(미래면 어제)."""
    s = clean(s)
    now = datetime.now(KST)
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", s)
    if m:
        y, mo, d, h, mi = m.groups()
        dt = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=KST)
    elif (m := re.fullmatch(r"(\d{2})[-./](\d{1,2})[-./](\d{1,2})", s)):
        y, mo, d = m.groups()
        dt = datetime(2000 + int(y), int(mo), int(d), tzinfo=KST)
    elif (m := re.search(r"(\d{1,2})[-./](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", s)):
        mo, d, h, mi = m.groups()
        dt = datetime(now.year, int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=KST)
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=now.year - 1)
    elif (m := re.search(r"(\d{1,2}):(\d{2})", s)):
        dt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if dt > now + timedelta(minutes=5):
            dt -= timedelta(days=1)
    else:
        return None
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def split_board(title: str) -> tuple[str, str]:
    """'[싱갤] 제목' → ('싱갤', '제목')"""
    m = re.match(r"\[([^\]]{1,12})\]\s*", title)
    return (m.group(1), title[m.end():]) if m else ("", title)


# ── 커뮤니티별 ──────────────────────────────────────────────────
def dcinside() -> list[dict]:
    t = fetch("https://gall.dcinside.com/board/lists/?id=dcbest")
    out = []
    for row in t.split('<tr class="ub-content')[1:]:
        no = re.search(r'<td class="gall_num">(\d+)</td>', row)
        tit = re.search(r'<td class="gall_tit[^"]*">.*?<a\s[^>]*href="[^"]+"[^>]*>(.*?)</a>', row, re.S)
        if not (no and tit):
            continue  # 공지·설문 등
        inner = re.sub(r'<div class="thumimg">.*?</div>', "", tit.group(1), flags=re.S)
        board, title = split_board(clean(inner))
        reply = re.search(r'class="reply_num">\[(\d+)', row)
        date = re.search(r'<td class="gall_date" title="([^"]+)"', row)
        out.append({
            "title": title, "board": board,
            "url": f"https://gall.dcinside.com/board/view/?id=dcbest&no={no.group(1)}",
            "views": num(re.search(r'<td class="gall_count">([^<]*)', row).group(1)),
            "likes": num(re.search(r'<td class="gall_recommend">([^<]*)', row).group(1)),
            "comments": int(reply.group(1)) if reply else 0,
            "published": parse_kst(date.group(1)) if date else None,
        })
    return out


def bobaedream() -> list[dict]:
    t = fetch("https://www.bobaedream.co.kr/list?code=best")
    out = []
    for row in t.split('<tr itemscope')[1:]:
        a = re.search(r'class="bsubject"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        if not a:
            continue
        no = re.search(r"No=(\d+)", a.group(1))
        cat = re.search(r'<td class="category" title="([^"]*)"', row)
        reply = re.search(r'class="totreply">(\d+)', row)
        out.append({
            "title": clean(a.group(2)), "board": clean(cat.group(1)) if cat else "",
            "url": f"https://www.bobaedream.co.kr/view?code=best&No={no.group(1)}" if no else
                   "https://www.bobaedream.co.kr" + html.unescape(a.group(1)),
            "views": num((re.search(r'<td class="count"[^>]*>(.*?)</td>', row, re.S) or [None, ""])[1]),
            "likes": num((re.search(r'<td class="recomm">(.*?)</td>', row, re.S) or [None, ""])[1]),
            "comments": int(reply.group(1)) if reply else 0,
            "published": parse_kst((re.search(r'<td class="date"[^>]*>([^<]*)', row) or [None, ""])[1]),
        })
    return out


def humoruniv() -> list[dict]:
    t = fetch("https://web.humoruniv.com/board/humor/list.html?table=pds&st=day", "cp949")
    out = []
    for row in t.split('<tr id="li_chk_pds-')[1:]:
        no = re.match(r"(\d+)", row)
        tit = re.search(r'<span id="title_chk_pds-\d+">(.*?)</span>', row, re.S)
        if not (no and tit):
            continue
        und = re.findall(r'class="li_und"[^>]*>(.*?)</td>', row, re.S)
        reply = re.search(r'list_comment_num">\s*\[(\d+)\]', row)
        d = re.search(r'class="w_date">([^<]*)</span>\s*<span class="w_time">([^<]*)', row)
        out.append({
            "title": clean(tit.group(1)), "board": "웃긴자료",
            "url": f"https://web.humoruniv.com/board/humor/read.html?table=pds&number={no.group(1)}",
            "views": num(und[0]) if und else 0,
            "likes": num(und[1]) if len(und) > 1 else 0,
            "comments": int(reply.group(1)) if reply else 0,
            "published": parse_kst(f"{d.group(1)} {d.group(2)}") if d else None,
        })
    return out


def ruliweb() -> list[dict]:
    t = fetch("https://bbs.ruliweb.com/best/all")
    out = []
    for row in t.split('<tr class="table_body')[1:]:
        a = re.search(r'class="subject_link[^"]*"\s+href="([^"]+)"', row)
        tit = re.search(r'<(strong|span) class="text_over">(.*?)</\1>', row, re.S)
        if not (a and tit) or "notice" in row[:80]:
            continue
        reply = re.search(r'class="num_reply[^"]*">\s*\((\d+)\)', row)
        href = html.unescape(a.group(1))
        out.append({
            "title": clean(tit.group(2)), "board": "베스트",
            "url": href if href.startswith("http") else "https://bbs.ruliweb.com" + href,
            "views": num((re.search(r'<td class="hit">(.*?)</td>', row, re.S) or [None, ""])[1]),
            "likes": num((re.search(r'<td class="recomd">(.*?)</td>', row, re.S) or [None, ""])[1]),
            "comments": int(reply.group(1)) if reply else 0,
            "published": parse_kst(re.sub(r"<input[^>]*>", "",
                                          (re.search(r'<td class="time">(.*?)</td>', row, re.S) or [None, ""])[1])),
        })
    return out


def clien() -> list[dict]:
    t = fetch("https://www.clien.net/service/board/park")
    out = []
    for row in t.split('data-role="list-row"')[1:]:
        a = re.search(r'class="list_subject" href="(/service/board/park/(\d+))[^"]*"', row)
        tit = re.search(r'class="subject_fixed"[^>]*title="([^"]*)"', row)
        if not (a and tit):
            continue
        cm = re.search(r'data-comment-count=(\d+)', row) or re.search(r'class="rSymph\d+">(\d+)', row)
        ts = re.search(r'class="timestamp">([^<]+)', row)
        out.append({
            "title": clean(tit.group(1)), "board": "모두의공원",
            "url": "https://www.clien.net" + a.group(1),
            "views": num((re.search(r'<span class="hit">([^<]*)', row) or [None, ""])[1]),
            "likes": num((re.search(r'class="list_symph[^"]*"[^>]*><span>([^<]*)', row) or [None, ""])[1]),
            "comments": int(cm.group(1)) if cm else 0,
            "published": parse_kst(ts.group(1)) if ts else None,
        })
    return out


def instiz() -> list[dict]:
    t = fetch("https://www.instiz.net/pt?category=1")
    out, seen = [], set()
    pat = re.compile(
        r'listsubject"><a href="(https://www\.instiz\.net/pt/(\d+)[^"]*)">(.*?)</a></td>\s*'
        r'<td class="listno"[^>]*>([^<]*)</td>\s*<td class="listno"[^>]*>([^<]*)</td>\s*'
        r'<td class="listno"[^>]*>([^<]*)</td>', re.S)
    for m in pat.finditer(t):
        _, no, inner, date, views, likes = m.groups()
        if no in seen:
            continue
        seen.add(no)
        cmt = re.search(r'class="cmt3"[^>]*>(\d+)</span>', inner)
        title = clean(re.sub(r'<span class="cmt3".*?</span>', "", inner, flags=re.S))
        out.append({
            "title": title, "board": "이슈",
            "url": f"https://www.instiz.net/pt/{no}",
            "views": num(views), "likes": num(likes),
            "comments": int(cmt.group(1)) if cmt else 0,
            "published": parse_kst(date),
        })
    return out


def ppomppu() -> list[dict]:
    t = fetch("https://www.ppomppu.co.kr/rss.php?id=freeboard")
    out = []
    for item in re.findall(r"<item>(.*?)</item>", t, re.S):
        def tag(name: str) -> str:
            m = re.search(rf"<{name}>(.*?)</{name}>", item, re.S)
            return m.group(1) if m else ""
        hits = [int(x) for x in re.findall(r"\d+", tag("hits"))] + [0, 0, 0]
        no = re.search(r"no=(\d+)", tag("link"))
        try:
            pub = parsedate_to_datetime(tag("pubDate")).astimezone(timezone.utc).isoformat(timespec="seconds")
        except Exception:
            pub = None
        out.append({
            "title": clean(tag("title")), "board": "자유게시판",
            "url": f"https://www.ppomppu.co.kr/zboard/view.php?id=freeboard&no={no.group(1)}" if no
                   else html.unescape(tag("link")),
            "comments": hits[0], "views": hits[1], "likes": hits[2],
            "published": pub,
        })
    return out


# (이름, 표시 이름, 함수)
SOURCES = [
    ("dcinside", "디시인사이드", dcinside),
    ("bobaedream", "보배드림", bobaedream),
    ("humoruniv", "웃긴대학", humoruniv),
    ("ruliweb", "루리웹", ruliweb),
    ("clien", "클리앙", clien),
    ("instiz", "인스티즈", instiz),
    ("ppomppu", "뽐뿌", ppomppu),
]
