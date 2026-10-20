"""대시보드 index.html 암호화/복호화.

index.html = gate.html(비밀번호 화면) + 암호화된 대시보드 원본.
비밀번호는 환경변수 DASHBOARD_PASSWORD 에서 읽습니다 (GitHub Actions 에서는 저장소 Secret).

로컬에서 직접 고칠 때:
  DASHBOARD_PASSWORD=비밀번호 python page_crypt.py decrypt   # index.html → app.html (평문, 커밋 금지)
  DASHBOARD_PASSWORD=비밀번호 python page_crypt.py encrypt   # app.html → index.html
"""
import base64
import json
import os
import re
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

GATE_FILE = "gate.html"
ITERATIONS = 600_000
MARK = "/*PAYLOAD*/"
PAYLOAD_RE = re.compile(r"const PAYLOAD = /\*PAYLOAD\*/(\{.*?\});", re.DOTALL)


def get_password():
    pw = os.environ.get("DASHBOARD_PASSWORD", "")
    if not pw:
        sys.exit("DASHBOARD_PASSWORD 가 없습니다. GitHub 저장소 Settings → Secrets and variables → Actions 에 "
                 "DASHBOARD_PASSWORD 를 추가해 주세요.")
    return pw


def _key(pw, salt, iterations):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(pw.encode("utf-8"))


def is_encrypted(html):
    return PAYLOAD_RE.search(html) is not None


def encrypt_page(app_html, pw):
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(pw, salt, ITERATIONS)).encrypt(iv, app_html.encode("utf-8"), None)
    payload = {"v": 1, "iter": ITERATIONS,
               "salt": base64.b64encode(salt).decode(), "iv": base64.b64encode(iv).decode(),
               "ct": base64.b64encode(ct).decode()}
    with open(GATE_FILE, encoding="utf-8") as f:
        gate = f.read()
    if MARK + "null" not in gate:
        sys.exit("gate.html 의 PAYLOAD 자리를 찾지 못했습니다.")
    return gate.replace(MARK + "null", MARK + json.dumps(payload), 1)


def decrypt_page(index_html, pw):
    m = PAYLOAD_RE.search(index_html)
    if not m:
        raise ValueError("암호화된 index.html 이 아닙니다.")
    p = json.loads(m.group(1))
    key = _key(pw, base64.b64decode(p["salt"]), p["iter"])
    try:
        plain = AESGCM(key).decrypt(base64.b64decode(p["iv"]), base64.b64decode(p["ct"]), None)
    except Exception:
        sys.exit("비밀번호가 맞지 않아 index.html 을 열 수 없습니다. DASHBOARD_PASSWORD 를 확인해 주세요.")
    return plain.decode("utf-8")


def read_app(path="index.html"):
    """index.html 을 읽어 평문 대시보드 HTML 을 돌려줌 (암호화돼 있지 않으면 그대로)."""
    with open(path, encoding="utf-8") as f:
        html = f.read()
    return decrypt_page(html, get_password()) if is_encrypted(html) else html


def write_app(app_html, path="index.html"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(encrypt_page(app_html, get_password()))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "decrypt":
        with open("app.html", "w", encoding="utf-8") as f:
            f.write(read_app())
        print("app.html 에 풀었습니다 (커밋하지 마세요).")
    elif cmd == "encrypt":
        with open("app.html", encoding="utf-8") as f:
            write_app(f.read())
        print("index.html 을 암호화해 저장했습니다.")
    else:
        sys.exit("사용법: python page_crypt.py decrypt|encrypt")
