"""results 폴더의 최신 CSV + ai_citations.csv 로 dashboard.html 을 만든다."""
import csv, glob, json, os, re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build(regions=None):
    files = sorted(glob.glob(os.path.join(BASE, "results", "keywords_*.csv")))
    if not files:
        print("결과 CSV가 없어서 대시보드를 만들지 못했어요.")
        return None
    rows = _read(files[-1])
    prev = set()
    if len(files) >= 2:
        prev = {r["키워드"] for r in _read(files[-2])}

    if not regions:
        seeds = {s.strip() for r in rows for s in r.get("씨앗", "").split(",") if s.strip()}
        regions = {re.sub(r"\s*(데이트)?\s*(맛집|카페|식당)$", "", s).replace(" ", "") for s in seeds}
    regions = sorted({g for g in regions if len(g) >= 2}, key=len, reverse=True)

    data = []
    for r in rows:
        kw = r["키워드"]
        reg = next((g for g in regions if g in kw), "")
        data.append({
            "k": kw, "v": int(r["총검색량"] or 0), "m": int(r["모바일비율"] or 0),
            "c": r["경쟁"], "s": r["추천"], "w": r["이미씀"] == "O", "f": r["음식관련"] == "O",
            "r": reg, "n": bool(prev) and kw not in prev,
        })

    cites = []
    cp = os.path.join(BASE, "ai_citations.csv")
    if os.path.exists(cp):
        for r in _read(cp):
            vals = list(r.values())
            if len(vals) >= 4 and vals[1]:
                cites.append({"d": vals[0], "k": vals[1], "b": (vals[2] or "").strip().upper(),
                              "c": (vals[3] or "").strip().upper(), "u": vals[4] if len(vals) > 4 else "",
                              "memo": vals[5] if len(vals) > 5 else ""})

    m = re.search(r"(\d{8})", os.path.basename(files[-1]))
    run_date = datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y.%m.%d") if m else ""
    payload = {"date": run_date, "rows": data, "cites": cites, "hasPrev": bool(prev),
               "prevFile": os.path.basename(files[-2]) if len(files) >= 2 else ""}

    with open(os.path.join(BASE, "dashboard_template.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False))
    out = os.path.join(BASE, "results", "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    p = build()
    if p:
        print("대시보드:", p)
