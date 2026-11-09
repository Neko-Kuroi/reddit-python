# app/templating.py
"""
Jinja2 テンプレートの共有モジュール。

全 Router はここで作る1つの templates オブジェクトを共有する。
カスタムフィルターもここに登録する
（Router ごとに Jinja2Templates を作ると、描画側にフィルターが届かない）。
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def time_ago(dt: datetime) -> str:
    diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    if diff < 60:       return "たった今"
    elif diff < 3600:   return f"{diff // 60}分前"
    elif diff < 86400:  return f"{diff // 3600}時間前"
    elif diff < 86400 * 30: return f"{diff // 86400}日前"
    else:               return f"{diff // (86400 * 30)}ヶ月前"


def urlparse_host(url: str) -> str:
    try:    return urlparse(url).hostname or url
    except: return url


templates.env.filters["time_ago"] = time_ago
templates.env.filters["urlparse_host"] = urlparse_host


# === 第7章で追加 ===

def format_karma(karma: int) -> str:
    """1000以上は k 表記にする"""
    if karma >= 1000:
        return f"{karma / 1000:.1f}k"
    return str(karma)


templates.env.filters["format_karma"] = format_karma

# 報告理由の共通データ。
# 値の正本は app/reports/services.py の VALID_REASONS。
# ここでは表示ラベルと対応づけてテンプレート全体から使えるようにする。
from app.reports.services import VALID_REASONS

REPORT_REASON_LABELS = {
    "spam": "スパム",
    "harassment": "嫌がらせ・ハラスメント",
    "hate_speech": "ヘイトスピーチ",
    "misinformation": "誤情報",
    "other": "その他",
}

templates.env.globals["report_reasons"] = [
    (value, REPORT_REASON_LABELS[value]) for value in VALID_REASONS
]
