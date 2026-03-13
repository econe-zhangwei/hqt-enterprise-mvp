from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import re

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.services.policy_seed import seed_policies
from app.services.policy_structurer import sync_policies_from_knowledge_base


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_policies(session)
        sync_policies_from_knowledge_base(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _frontend_entry() -> str:
    react_index = static_dir / "react" / "index.html"
    if react_index.exists():
        return "/react-app"
    return "/static/login.html"


@app.get("/react-app")
def react_app_shell() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>惠企通 - 企业工作台</title>
    <style>
      html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #f7f7f8;
      }
      iframe {
        display: block;
        width: 100vw;
        height: 100vh;
        border: 0;
        background: #f7f7f8;
      }
    </style>
  </head>
  <body>
    <iframe src="/react-frame" title="惠企通应用" referrerpolicy="same-origin"></iframe>
  </body>
</html>
"""
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/react-frame")
def react_app() -> HTMLResponse:
    react_index = static_dir / "react" / "index.html"
    html = react_index.read_text(encoding="utf-8")

    def _asset_version(match: re.Match[str]) -> str:
        asset_path = match.group(1)
        file_path = static_dir / "react" / "assets" / Path(asset_path).name
        version = int(file_path.stat().st_mtime) if file_path.exists() else 0
        return f'{match.group(0)}?v={version}'

    html = re.sub(r"/static/react/assets/([^\"]+)", _asset_version, html)

    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url=_frontend_entry(), status_code=302)


@app.get("/app")
def app_shell() -> RedirectResponse:
    return RedirectResponse(url=_frontend_entry(), status_code=302)
