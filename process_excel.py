import os
import re
import json
import pandas as pd

DATA_DIR = "data"
HTML_FILE = "index.html"

def get_cat2(c3):
    c3 = str(c3)
    if "커피믹스" in c3 or "인스턴트" in c3:
        return "커피믹스·인스턴트"
    elif "원두" in c3 or "생두" in c3:
        return "원두"
    elif "커피음료" in c3:
        return "커피음료"
    elif any(k in c3 for k in ["차", "아이스티", "보리차", "에이드", "녹차", "홍차", "주스"]):
        return "차·아이스티"
    elif "드립백" in c3 or "티백" in c3:
        return "드립백"
    return "기타"

DATE_RE = re.compile(r"(\d{8})-(\d{8})")

def file_type(fn):
    fn = fn.lower()
    if "sales" in fn or "판매" in fn or "상품" in fn:
        return "sales"
    if "visit" in fn or "방문" in fn or "유입" in fn:
        return "visit"
    if "query" in fn or "검색" in fn:
        return "query"
    if "cust" in fn or "고객" in fn:
        return "cust"
    return None

def find_excel_files():
    """data 폴더의 엑셀을 종류별로 모음. 각 항목 = (경로, 시작일, 종료일) — 날짜는 파일명의 YYYYMMDD-YYYYMMDD"""
    files = {"sales": [], "visit": [], "query": [], "cust": []}
    if not os.path.exists(DATA_DIR):
        return files
    for f in sorted(os.listdir(DATA_DIR)):
        if not f.endswith(".xlsx"):
            continue
        t = file_type(f)
        if not t:
            continue
        m = DATE_RE.search(f)
        start, end = (m.group(1), m.group(2)) if m else ("", "")
        files[t].append((os.path.join(DATA_DIR, f), start, end))
    return files

def latest_by_month(items):
    """같은 달(시작일 기준) 파일이 여러 개면 종료일이 가장 늦은 파일 하나만 (같으면 파일명 뒤쪽)"""
    best = {}
    for p, start, end in items:
        key = f"{start[:4]}-{start[4:6]}" if start else os.path.basename(p)
        cur = best.get(key)
        if cur is None or (end, p) > (cur[1], cur[0]):
            best[key] = (p, end)
    return {k: v[0] for k, v in best.items()}

def build_month(files):
    """한 달치: files = {"sales": 경로, "visit": 경로|None, "query": 경로|None} → (월, month_obj, names, query_obj)"""
    # 1. SALES 처리
    df_s = pd.read_excel(files["sales"])
    tot_s = df_s[df_s["채널상품명"] == "전체"].iloc[0]
    date_range = str(tot_s["날짜"])
    m_key = date_range.split("~")[0][:7]
    days_cnt = len(df_s[(df_s["채널상품명"] == "전체") & (df_s["날짜"] != date_range)])

    T = {
        "orders": int(tot_s["상품결제건수"]),
        "refCnt": int(tot_s["환불건수"]),
        "gross": int(tot_s["판매금액(총)"]),
        "net": int(tot_s["판매금액(순)"]),
        "refAmt": int(tot_s["환불금액"]),
        "qty": int(tot_s["결제상품수량"]),
        "refQty": int(tot_s["환불상품수량"]),
        "visits": int(tot_s["방문수"]),
        "ship": int(tot_s["배송비"]),
        "disc": int(tot_s["전체 할인액"]),
        "sPD": int(tot_s["판매자 부담 상품할인액"]),
        "nPD": int(tot_s["네이버 부담 상품할인액"]),
        "sOD": int(tot_s["판매자 부담 주문할인액"]),
        "nOD": int(tot_s["네이버 부담 주문할인액"])
    }

    daily = []
    for _, r in df_s[(df_s["채널상품명"] == "전체") & (df_s["날짜"] != date_range)].sort_values("날짜").iterrows():
        daily.append([
            str(r["날짜"])[5:],
            int(r["상품결제건수"]),
            int(r["판매금액(총)"]),
            int(r["판매금액(순)"]),
            int(r["방문수"]),
            int(r["환불금액"])
        ])

    grp_p = df_s[df_s["채널상품명"] != "전체"].groupby("채널상품번호").agg({
        "채널상품명": "last", "세부 카테고리": "last",
        "상품결제건수": "sum", "환불건수": "sum", "판매금액(총)": "sum", "판매금액(순)": "sum", "환불금액": "sum",
        "결제상품수량": "sum", "환불상품수량": "sum", "방문수": "sum", "전체 할인액": "sum",
        "판매자 부담 상품할인액": "sum", "네이버 부담 상품할인액": "sum",
        "판매자 부담 주문할인액": "sum", "네이버 부담 주문할인액": "sum"
    }).reset_index()

    P = []
    new_names = {}
    for _, r in grp_p.iterrows():
        pid = str(r["채널상품번호"])
        pname = str(r["채널상품명"])
        c3 = str(r["세부 카테고리"])
        new_names[pid] = [pname, get_cat2(c3), c3]
        P.append([
            pid, int(r["상품결제건수"]), int(r["환불건수"]), int(r["판매금액(총)"]), int(r["판매금액(순)"]),
            int(r["환불금액"]), int(r["결제상품수량"]), int(r["환불상품수량"]), int(r["방문수"]),
            int(r["전체 할인액"]), int(r["판매자 부담 상품할인액"]), int(r["네이버 부담 상품할인액"]),
            int(r["판매자 부담 주문할인액"]), int(r["네이버 부담 주문할인액"])
        ])
    P.sort(key=lambda x: x[3], reverse=True)

    # 2. VISIT 처리
    VT = {"visits": T["visits"], "orders": T["orders"], "sales": T["gross"]}
    VD = []
    V = []
    if files["visit"]:
        df_v = pd.read_excel(files["visit"])
        tot_v_rows = df_v[(df_v["경로(1단계)"] == "전체") & (df_v["날짜"] == date_range)]
        if not tot_v_rows.empty:
            tv = tot_v_rows.iloc[0]
            VT = {"visits": int(tv["방문수"]), "orders": int(tv["상품결제건수"]), "sales": int(tv["판매금액(총)"])}

        for _, r in df_v[(df_v["경로(1단계)"] == "전체") & (df_v["날짜"] != date_range)].sort_values("날짜").iterrows():
            VD.append([str(r["날짜"])[5:], int(r["방문수"]), int(r["상품결제건수"]), int(r["판매금액(총)"])])

        grp_v = df_v[df_v["경로(1단계)"] != "전체"].groupby(["경로(1단계)", "경로(2단계)", "경로(3단계)"]).agg({
            "방문수": "sum", "상품결제건수": "sum", "판매금액(총)": "sum"
        }).reset_index()
        for _, r in grp_v.iterrows():
            V.append([str(r["경로(1단계)"]), str(r["경로(2단계)"]), str(r["경로(3단계)"]), int(r["방문수"]), int(r["상품결제건수"]), int(r["판매금액(총)"])])
        V.sort(key=lambda x: x[3], reverse=True)

    month_obj = {
        "m": m_key, "range": date_range, "days": days_cnt, "T": T, "daily": daily, "P": P, "VT": VT, "VD": VD, "V": V
    }

    # 3. QUERY 처리
    query_obj = None
    if files["query"]:
        df_q = pd.read_excel(files["query"])
        tot_q_rows = df_q[(df_q["검색어"] == "전체") & (df_q["날짜"] == date_range)]
        QT = {"visits": 0, "orders": 0, "sales": 0}
        if not tot_q_rows.empty:
            tq = tot_q_rows.iloc[0]
            QT = {"visits": int(tq["방문수"]), "orders": int(tq["상품결제건수"]), "sales": int(tq["판매금액(총)"])}

        q_daily = []
        for _, r in df_q[(df_q["검색어"] == "전체") & (df_q["날짜"] != date_range)].sort_values("날짜").iterrows():
            q_daily.append([str(r["날짜"])[5:], int(r["방문수"]), int(r["상품결제건수"]), int(r["판매금액(총)"])])

        K = []
        grp_k = df_q[df_q["검색어"] != "전체"].groupby("검색어").agg({
            "방문수": "sum", "상품결제건수": "sum", "판매금액(총)": "sum"
        }).reset_index()
        for _, r in grp_k.iterrows():
            K.append([str(r["검색어"]), int(r["방문수"]), int(r["상품결제건수"]), int(r["판매금액(총)"])])
        K.sort(key=lambda x: x[1], reverse=True)
        query_obj = {"m": m_key, "T": QT, "daily": q_daily, "K": K}

    return m_key, month_obj, new_names, query_obj

def main():
    if not os.path.exists(HTML_FILE):
        print("index.html not found.")
        return

    files = find_excel_files()
    sales = latest_by_month(files["sales"])
    visit = latest_by_month(files["visit"])
    query = latest_by_month(files["query"])
    print("판매 파일(월별 최신):", sales)
    if not sales:
        print("판매분석(sales) 파일이 필요합니다.")
        return

    results = []
    for key in sorted(sales):
        mk = key if re.match(r"\d{4}-\d{2}$", key) else None
        results.append(build_month({"sales": sales[key], "visit": visit.get(mk) if mk else None, "query": query.get(mk) if mk else None}))

    # 4. CUSTOMER 처리
    cust_objs = []
    for cust_path, _, _ in sorted(files["cust"], key=lambda x: (x[2], x[0])):
        df_c = pd.read_excel(cust_path)
        for rng in df_c["날짜"].unique():
            c_m = rng.split("~")[0][:7]
            sub = df_c[df_c["날짜"] == rng]
            all_r = sub[sub["고객분류"] == "전체합산"]
            new_r = sub[sub["고객분류"] == "신규"]
            ret_r = sub[sub["고객분류"] == "재구매"]
            if not all_r.empty and not new_r.empty and not ret_r.empty:
                cust_objs.append({
                    "m": c_m,
                    "all": {"vis": int(all_r.iloc[0]["방문고객수"]), "buy": int(all_r.iloc[0]["결제고객수"]), "sales": int(all_r.iloc[0]["판매금액(총)"])},
                    "new": {"vis": int(new_r.iloc[0]["방문고객수"]), "buy": int(new_r.iloc[0]["결제고객수"]), "sales": int(new_r.iloc[0]["판매금액(총)"])},
                    "ret": {"vis": int(ret_r.iloc[0]["방문고객수"]), "buy": int(ret_r.iloc[0]["결제고객수"]), "sales": int(ret_r.iloc[0]["판매금액(총)"])}
                })
        cust_objs.sort(key=lambda x: x["m"])

    # 5. index.html에 주입
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    pattern = r"const DATA\s*=\s*(\{.*?\});\nconst PKEYS"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        print("DATA variable not found.")
        return

    data = json.loads(match.group(1))

    for m_key, month_obj, new_names, query_obj in results:
        # months 교체 또는 추가
        existing_idx = next((i for i, m in enumerate(data.get("months", [])) if m["m"] == m_key), None)
        if existing_idx is not None:
            data["months"][existing_idx] = month_obj
        else:
            data["months"].append(month_obj)

        # names 업데이트
        if "names" not in data:
            data["names"] = {}
        data["names"].update(new_names)

        # query 업데이트
        if query_obj:
            if "query" not in data:
                data["query"] = []
            q_idx = next((i for i, q in enumerate(data["query"]) if q["m"] == m_key), None)
            if q_idx is not None:
                data["query"][q_idx] = query_obj
            else:
                data["query"].append(query_obj)
    data["months"].sort(key=lambda x: x["m"])
    if "query" in data:
        data["query"].sort(key=lambda x: x["m"])

    # cust 업데이트
    if cust_objs:
        if "cust" not in data:
            data["cust"] = []
        cust_dict = {c["m"]: c for c in data["cust"]}
        for co in cust_objs:
            cust_dict[co["m"]] = co
        data["cust"] = sorted(cust_dict.values(), key=lambda x: x["m"])

    new_data_str = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\nconst PKEYS"
    html_updated = re.sub(pattern, new_data_str, html, flags=re.DOTALL)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_updated)

    for r in results:
        print(f"[{r[0]}] {r[1]['range']} 데이터가 index.html에 정상 반영되었습니다.")

if __name__ == "__main__":
    main()
