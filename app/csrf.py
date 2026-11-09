# app/csrf.py
"""
CSRF 対策（ダブルサブミットクッキー方式）。

仕組み:
- 発行（CSRFMiddleware）: トークンを持たないリクエストには、
  secrets で生成したランダムなトークンを Cookie にセットする。
  同じトークンはリクエストの Cookie ヘッダーにも注入されるため、
  そのリクエストで描画するテンプレートからも request.cookies 経由で
  参照できる（base.html の meta タグと、フォームの hidden フィールド）。
- 検証（csrf_protect）: 状態を変えるメソッド（POST 等）では、
  「Cookie の値」と「X-CSRF-Token ヘッダー（HTMX 用）または
  フォームの csrf_token フィールド（通常フォーム用）」が
  一致するか、定数時間比較で確認する。不一致・欠落は 403。
  アプリ全体の依存性として main.py で登録する。
"""
import re
import secrets

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders

CSRF_COOKIE_NAME = "csrf_token"
# base.html の既存スクリプトは X-CSRFToken の綴りで送るため、
# ハイフンあり・なしの両方を受ける
CSRF_HEADER_NAMES = ("x-csrf-token", "x-csrftoken")
CSRF_FORM_FIELD = "csrf_token"

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,}$")
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


def generate_csrf_token() -> str:
    """推測できないランダムなトークンを生成する"""
    return secrets.token_urlsafe(32)


def _has_valid_format(token: str | None) -> bool:
    return bool(token) and bool(_TOKEN_RE.match(token))


def _tokens_match(a: str, b: str) -> bool:
    # 定数時間比較（タイミング攻撃の防止）。バイト列で比べ、
    # 非 ASCII 文字が来ても例外にならないようにする
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class CSRFMiddleware:
    """トークンの発行を担当するミドルウェア（純粋な ASGI 実装）"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 既存の Cookie ヘッダーからトークンを探す
        token = None
        for key, value in scope.get("headers", []):
            if key.lower() == b"cookie":
                for part in value.decode("latin-1").split(";"):
                    name, _, val = part.strip().partition("=")
                    if name == CSRF_COOKIE_NAME:
                        token = val
                break

        if _has_valid_format(token):
            await self.app(scope, receive, send)
            return

        # トークンが無い（または不正な形式）→ 新規発行する
        token = generate_csrf_token()

        # 下流（テンプレート・検証）からもこのリクエストの Cookie として
        # 見えるよう、Cookie ヘッダーに注入しておく
        new_headers = []
        injected = False
        for key, value in scope.get("headers", []):
            if key.lower() == b"cookie" and not injected:
                value = value + f"; {CSRF_COOKIE_NAME}={token}".encode("latin-1")
                injected = True
            new_headers.append((key, value))
        if not injected:
            new_headers.append(
                (b"cookie", f"{CSRF_COOKIE_NAME}={token}".encode("latin-1"))
            )
        scope = dict(scope)
        scope["headers"] = new_headers

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append(
                    "set-cookie",
                    f"{CSRF_COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=lax",
                )
            await send(message)

        await self.app(scope, receive, send_with_cookie)


async def csrf_protect(request: Request) -> None:
    """
    状態を変えるリクエストの CSRF 検証。
    main.py で FastAPI(dependencies=[...]) として全ルートに適用する。
    """
    if request.method in _SAFE_METHODS:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not _has_valid_format(cookie_token):
        raise HTTPException(status_code=403, detail="CSRFトークンがありません")

    # HTMX は base.html のスクリプトでヘッダーに載せて送る
    for header_name in CSRF_HEADER_NAMES:
        header_token = request.headers.get(header_name)
        if header_token and _tokens_match(header_token, cookie_token):
            return

    # 通常フォームは hidden フィールドで送る
    form = await request.form()
    form_token = form.get(CSRF_FORM_FIELD)
    if form_token and _tokens_match(str(form_token), cookie_token):
        return

    raise HTTPException(
        status_code=403, detail="CSRFトークンの検証に失敗しました"
    )
