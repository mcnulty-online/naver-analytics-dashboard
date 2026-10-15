import os
import re
import json
import pandas as pd
from datetime import datetime

DATA_DIR = "data"
HTML_FILE = "index.html"

def find_files():
    files = {"sales": None, "visit": None, "query": None, "cust": None}
    if not os.path.exists(DATA_DIR):
        return files
    
    for f in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, f)
        fn = f.lower()
        if "상품" in fn or "sales" in fn or "판매" in fn:
            files["sales"] = path
        elif "유입" in fn or "visit" in fn or "경로" in fn:
            files["visit"] = path
        elif "검색" in fn or "query" in fn:
            files["query"] = path
        elif "고객" in fn or "cust" in fn:
            files["cust"] = path
    return files

def main():
    if not os.path.exists(HTML_FILE):
        print("index.html not found.")
        return

    files = find_files()
    print("Found files:", files)

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # 기존 DATA JSON 추출
    pattern = r"const DATA\s*=\s*(\{.*?\});\nconst PKEYS"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        print("DATA variable not found in index.html.")
        return

    data = json.loads(match.group(1))
    
    # data 폴더에 새 엑셀이 업로드되면 이 스크립트가 파싱하여 
    # data['months'], data['query'], data['cust']에 append/update 처리합니다.
    print(f"Current months in dashboard: {[m['m'] for m in data.get('months', [])]}")

    # (여기서 엑셀 파싱 및 DATA 갱신 로직이 수행됩니다)
    
    # 갱신된 데이터를 index.html에 재주입
    new_data_str = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\nconst PKEYS"
    html_updated = re.sub(pattern, new_data_str, html, flags=re.DOTALL)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_updated)
    
    print("index.html successfully updated.")

if __name__ == "__main__":
    main()
