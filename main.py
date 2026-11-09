# main.py（完成版）
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.csrf import CSRFMiddleware, csrf_protect
from app.accounts.router import router as accounts_router
from app.communities.router import router as communities_router
from app.posts.router import router as posts_router
from app.comments.router import router as comments_router

# csrf_protect を全体の依存性にすると、全ルートの状態変更リクエストが
# CSRF 検証の対象になる（第5章 5-9 を参照）
app = FastAPI(
    title="Reddit Clone",
    debug=settings.DEBUG,
    dependencies=[Depends(csrf_protect)],
)

# トークン発行ミドルウェア（検証は csrf_protect が担当する）
app.add_middleware(CSRFMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 の templates とカスタムフィルターは app/templating.py に集約し、
# 全 Router が共有する（第6章 6-15 を参照）

# Router の登録
app.include_router(accounts_router)
app.include_router(communities_router)
app.include_router(posts_router)
app.include_router(comments_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
