"""Public introduction only: no Gradio, identity, workflow or storage imports."""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import uvicorn

from week2.welcome import ROADMAP

ASSETS = Path(__file__).with_name("signin")
STYLE = (ASSETS / "screen.css").read_text(encoding="utf-8")
PAGE = (ASSETS / "index.html").read_text(encoding="utf-8").replace("<!-- roadmap -->", ROADMAP)


def app_url(value):
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and re.fullmatch(r"[a-z0-9-]+(?:\.a)?\.run\.app", parsed.hostname or "")
                 and parsed.port is None and parsed.username is None and parsed.password is None
                 and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("An exact HTTPS Cloud Run app URL is required")
    return value.rstrip("/") + "/"


def create_app(target=None):
    destination = app_url(os.environ.get("CRA2_APP_URL", "") if target is None else target)
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update({
            "Content-Security-Policy": "default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY", "X-Robots-Tag": "noindex, nofollow",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "public, max-age=300" if request.url.path in {"/", "/styles.css"} else "no-store"})
        return response

    @api.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def intro():
        return PAGE

    @api.get("/styles.css")
    def styles():
        return Response(STYLE, media_type="text/css")

    @api.api_route("/signin", methods=["GET", "HEAD"])
    def signin():
        return RedirectResponse(destination, status_code=303)

    @api.get("/healthz")
    def health():
        return {"status": "ok"}

    return api


def main():
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid runtime port")
    uvicorn.run(create_app(), host="0.0.0.0", port=port, workers=1,
                proxy_headers=False, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
