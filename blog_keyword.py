#!/usr/bin/env python3
"""옹굴 블로그 키워드 추천기
- 네이버 검색광고 API: 월간 검색량 / 연관 키워드 / 경쟁 정도
- 블로그 RSS: 이미 쓴 글 제목 → '아직 안 쓴 키워드' 판별
사용법: python3 blog_keyword.py
"""
import base64, csv, hashlib, hmac, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
BLOG_ID = "ourfourleaf"
API = "https://api.searchad.naver.com"

# 추천 기준 (seeds.txt 옆에서 언제든 수정 가능)
MIN_VOL, MAX_VOL = 300, 30000        # 월간 총검색량 범위
FOOD_WORDS = ["맛집", "식당", "카페", "디저트", "브런치", "술집", "고기", "횟집", "빵집", "베이커리",
              "파스타", "초밥", "오마카세", "국밥", "냉면", "갈비", "와인바", "이자카야", "데이트", "웨이팅", "메뉴"]


def load_env():
    """키는 환경변수(GitHub Secrets)에서 먼저 읽고, 없으면 같은 폴더의 .env에서 읽는다."""
    env = {}
    p = os.path.join(BASE, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for k in ("SEARCHAD_API_KEY", "SEARCHAD_SECRET_KEY", "SEARCHAD_CUSTOMER_ID"):
        if os.environ.get(k):
            env[k] = os.environ[k].strip()
        if not env.get(k) or env[k].startswith("여기에"):
            sys.exit(f"{k} 값이 없어요. GitHub 저장소 Settings > Secrets 를 확인해주세요.")
    return env


def sign(ts, method, uri, secret):
    msg = f"{ts}.{method}.{uri}".encode()
    return base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()


def keywordstool(env, hints):
    uri = "/keywordstool"
    ts = str(int(time.time() * 1000))
    q = urllib.parse.urlencode({"hintKeywords": ",".join(h.replace(" ", "") for h in hints), "showDetail": "1"})
    req = urllib.request.Request(f"{API}{uri}?{q}", headers={
        "X-Timestamp": ts,
        "X-API-KEY": env["SEARCHAD_API_KEY"],
        "X-Customer": env["SEARCHAD_CUSTOMER_ID"],
        "X-Signature": sign(ts, "GET", uri, env["SEARCHAD_SECRET_KEY"]),
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode()).get("keywordList", [])


def num(v):
    # "< 10" 같은 값은 5로 처리
    if isinstance(v, (int, float)):
        return int(v)
    return 5 if "<" in str(v) else int(re.sub(r"\D", "", str(v)) or 0)


def my_titles():
    url = f"https://rss.blog.naver.com/{BLOG_ID}.xml"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            root = ET.fromstring(r.read())
        return [i.findtext("title", "") for i in root.iter("item")]
    except Exception as e:
        print(f"[알림] RSS를 못 읽었어요({e}). '이미 씀' 판별 없이 진행합니다.")
        return []


def norm(s):
    return re.sub(r"\s+", "", s).lower()


def seeds_from(titles):
    # 글 제목에서 '지역 + 맛집' 형태를 뽑아 자동 씨앗으로 사용
    out = []
    for t in titles:
        m = re.search(r"([가-힣]{2,6})\s?(맛집|카페|식당)", t)
        if m:
            out.append(m.group(1) + " " + m.group(2))
    return out


def read_seeds():
    p = os.path.join(BASE, "seeds.txt")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def main():
    env = load_env()
    titles = my_titles()
    written = [norm(t) for t in titles]
    seeds = list(dict.fromkeys(read_seeds() + seeds_from(titles)))[:40]
    if not seeds:
        sys.exit("seeds.txt 에 씨앗 키워드를 1개 이상 적어주세요. (예: 성수 맛집)")
    print(f"씨앗 키워드 {len(seeds)}개로 조회합니다: {', '.join(seeds[:10])}{' ...' if len(seeds) > 10 else ''}")

    rows = {}
    for i in range(0, len(seeds), 5):           # API는 한 번에 최대 5개
        batch = seeds[i:i + 5]
        try:
            res = keywordstool(env, batch)
        except urllib.error.HTTPError as e:
            sys.exit(f"API 오류 {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            sys.exit(f"네이버 서버에 접속하지 못했어요({e.reason}). 인터넷 연결이나 허용 도메인 설정을 확인해주세요.")
        for k in res:
            kw = k["relKeyword"]
            pc, mo = num(k.get("monthlyPcQcCnt")), num(k.get("monthlyMobileQcCnt"))
            rows[kw] = {
                "키워드": kw, "PC": pc, "모바일": mo, "총검색량": pc + mo,
                "모바일비율": round(mo / (pc + mo) * 100) if pc + mo else 0,
                "경쟁": k.get("compIdx", ""), "씨앗": ",".join(batch),
            }
        time.sleep(0.5)

    # 씨앗에서 지역/주제 단어만 뽑아, 그 단어가 들어간 키워드만 추천 (엉뚱한 지역 제외)
    regions = {re.sub(r"\s*(데이트)?\s*(맛집|카페|식당)$", "", sd).replace(" ", "") for sd in seeds}
    regions = {g for g in regions if len(g) >= 2}

    out = []
    for r in rows.values():
        kn = norm(r["키워드"])
        r["음식관련"] = "O" if any(w in r["키워드"] for w in FOOD_WORDS) else ""
        r["이미씀"] = "O" if any(kn in t for t in written) else ""
        r["내지역"] = "O" if any(g in r["키워드"] for g in regions) else ""
        good = (r["음식관련"] and r["내지역"] and not r["이미씀"] and MIN_VOL <= r["총검색량"] <= MAX_VOL
                and r["경쟁"] in ("낮음", "중간"))
        r["추천"] = "★" if good and r["경쟁"] == "낮음" else ("☆" if good else "")
        out.append(r)
    out.sort(key=lambda r: ({"★": 0, "☆": 1}.get(r["추천"], 2), -r["총검색량"]))

    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    path = os.path.join(BASE, "results", f"keywords_{date.today():%Y%m%d}.csv")
    cols = ["추천", "키워드", "총검색량", "PC", "모바일", "모바일비율", "경쟁", "음식관련", "내지역", "이미씀", "씨앗"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(out)

    star = [r for r in out if r["추천"]]
    print(f"\n총 {len(out)}개 키워드 · 추천 {len(star)}개 (★경쟁 낮음 / ☆경쟁 중간)")
    for r in star[:20]:
        print(f" {r['추천']} {r['키워드']:<18} 월 {r['총검색량']:>6,}회  경쟁 {r['경쟁']}  모바일 {r['모바일비율']}%")
    print(f"\n전체 결과: {path}")
    try:
        import dashboard
        dp = dashboard.build(regions)
        if dp:
            print(f"대시보드: {dp}")
    except Exception as e:
        print(f"[알림] 대시보드를 만들지 못했어요({e})")


if __name__ == "__main__":
    main()
