"""Public introduction only: no Gradio, identity, workflow or storage imports."""
import os
import re
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import uvicorn

from week2.welcome import INTRO, ROADMAP, CSS

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; background: #111621; color: #eef4f1; font-family: ui-sans-serif,system-ui,-apple-system,sans-serif; }
header,main,footer { max-width: 1180px; margin: auto; padding: 24px; }
header { display:flex; align-items:center; justify-content:space-between; gap:20px; }
header strong { font-size:18px; letter-spacing:-.03em; }
header a { color:#9fd4c4; text-decoration:none; font-size:14px; }
main { padding-top:8px; }
.intro-grid { display:grid; grid-template-columns:minmax(0,3fr) minmax(240px,1fr); gap:28px; align-items:start; }
.signin { background:#fff; color:#163a3a; border-radius:22px; padding:28px; }
.signin h2 { font-size:23px; line-height:1.25; margin:0 0 15px; }
.signin p { color:#49625c; font-size:14px; line-height:1.7; }
.signin a { display:block; background:#28765e; color:#fff; padding:15px 16px; border-radius:9px; font-weight:650; text-align:center; text-decoration:none; margin-top:24px; }
.signin small { display:block; margin-top:14px; color:#49625c; line-height:1.6; }
a:focus-visible { outline:3px solid #6bd8bb; outline-offset:5px; }
footer { color:#a8b9b1; font-size:12px; padding-top:0; }
@media (max-width:760px) { .intro-grid { grid-template-columns:1fr; } header,main,footer { padding:18px; } }
""" + CSS[CSS.index(".cra-welcome"):]

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Understand service changes with recorded incident evidence, dependencies and review checks.">
<title>CRA · Change Risk Advisor</title><link rel="stylesheet" href="/styles.css"></head><body>
<header><strong>CRA · Change Risk Advisor</strong><a href="/signin">Sign in →</a></header>
<main><div class="intro-grid">""" + INTRO + """
<aside class="signin"><h2>Start with the evidence.</h2>
<p>Bring a proposed service change. Explore the supporting records and the questions to resolve before deployment.</p>
<a href="/signin">Sign in with Google</a>
<small>Access is by invitation. The introduction is public; your review workspace requires an authorized Google account.</small>
</aside></div>""" + ROADMAP + """</main>
<footer>CRA Version 1 · Synthetic evidence · Human approval required</footer></body></html>"""


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
