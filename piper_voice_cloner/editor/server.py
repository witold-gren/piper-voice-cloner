"""HTTP side of the editor: the page, its files, a JSON API over `service`, and the login.

Jobs are the same detached `pvc` runs as before (jobs.py): the server can restart while a
training goes on, and the command line does exactly what the page does.
"""

from __future__ import annotations

import html
import os
from pathlib import Path
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__, power
from ..jobs import JobBusy, JobManager
from . import api, service
from .auth import COOKIE, SESSION_DAYS, Guard, Login, Network, trusted
from .clone import add_clone_routes
from .poweroff import PowerOffTimer
from .routes import add_step_routes
from .settings import add_settings_routes

WWW = Path(__file__).parent / "www"
# the documentation site, when it is built (the Docker image: PVC_DOCS_DIR=/app/site; a checkout: site/)
DOCS_SITE = "https://witold-gren.github.io/piper-voice-cloner/"
SLOTS = ("current", "side")
# what may be fetched from the data folder (players, downloads); never voice.yaml or keys
SERVED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".zip", ".html", ".onnx", ".json", ".csv", ".png"}


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 400, **values) -> None:
        super().__init__(message or code)
        self.code, self.status, self.values = code, status, values


class NewVoice(BaseModel):
    name: str
    piper_name: str = ""
    workflow: str = "clone"


class Flag(BaseModel):
    value: bool


def create_app(
    root: Path,
    *,
    login: Login | None = None,
    pvc: list[str] | None = None,
    tensorboard_port: int | None = None,
    gpu: bool = True,
    docs_dir: Path | None = None,
    countdown: bool = True,
    trusted_networks: tuple[Network, ...] = (),
) -> FastAPI:
    root = Path(root)
    jobs = {slot: JobManager(root, pvc=pvc, slot=slot) for slot in SLOTS}
    app = FastAPI(title="Piper Voice Cloner", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.root, app.state.jobs = root, jobs
    guard = Guard()
    # looked up when the countdown ends, so tests and the demo can put a harmless one in its place
    timer = PowerOffTimer(jobs, lambda: power.power_off())
    app.state.power_timer = timer
    if countdown:
        timer.start()

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, err: ApiError):
        return JSONResponse({"error": err.code, "message": str(err), **err.values}, status_code=err.status)

    def from_trusted(request: Request) -> bool:
        """Only the address of the connection itself counts, never X-Forwarded-For or another header."""
        address = request.client.host if request.client else None
        return login is not None and trusted(address, trusted_networks)

    @app.middleware("http")
    async def need_login(request: Request, call_next):
        path = request.url.path
        open_paths = path in ("/login", "/api/health") or path.startswith(("/static/icon", "/favicon"))
        if login is None or open_paths or from_trusted(request) or login.valid(request.cookies.get(COOKIE)):
            return await call_next(request)
        if path.startswith(("/api/", "/docs")):
            return JSONResponse({"error": "login"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    # --- page and login ---------------------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__}

    @app.get("/")
    def index():
        return FileResponse(WWW / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/static/{name:path}")
    def static(name: str):
        path = (WWW / name).resolve()
        if not path.is_file() or WWW.resolve() not in path.parents:
            return Response(status_code=404)
        return FileResponse(path, headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.ico")
    def favicon():
        return FileResponse(WWW / "icon.svg", media_type="image/svg+xml")

    @app.get("/login")
    def login_page(request: Request, failed: int = 0):
        if from_trusted(request):
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(login_html(request.headers.get("accept-language", ""), failed))

    @app.post("/login")
    async def login_post(request: Request):
        form = await request.form()
        user, password = str(form.get("user", "")), str(form.get("password", ""))
        if login is None:
            return RedirectResponse("/", status_code=303)
        address = request.client.host if request.client else ""
        if guard.blocked(address):
            return RedirectResponse("/login?failed=2", status_code=303)
        if not login.check(user, password):
            guard.failed(address)
            time.sleep(0.5)  # slows down guessing
            return RedirectResponse("/login?failed=1", status_code=303)
        guard.passed(address)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE, login.token(), httponly=True, samesite="strict", max_age=SESSION_DAYS * 24 * 3600
        )
        return response

    @app.post("/logout")
    def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    # --- state ------------------------------------------------------------------------------------

    @app.get("/api/state")
    def state(request: Request):
        payload = api.state_payload(root, jobs, gpu=gpu)
        payload["tensorboard_port"] = tensorboard_port
        payload["login"] = login is not None
        payload["trusted"] = from_trusted(request)  # no login from this network: nothing to log out of
        # the machine's power and switching it off after a job: through Home Assistant
        payload["machine"] = app.state.machine.view()
        payload["can_power_off"] = app.state.machine.ready()
        timer.check()
        payload["power_off"] = timer.payload()
        payload["user"] = login.user if login else None
        payload["version"] = __version__
        return payload

    @app.post("/api/power-off/cancel")
    def power_off_cancel():
        return {"cancelled": timer.cancel()}

    @app.get("/api/jobs/{slot}")
    def job(slot: str):
        return api.job_payload(manager(slot))

    @app.post("/api/jobs/{slot}/stop")
    def stop(slot: str):
        return {"stopped": manager(slot).stop()}

    @app.post("/api/jobs/{slot}/poweroff")
    def poweroff(slot: str, flag: Flag):
        if not manager(slot).set_poweroff(flag.value):
            raise ApiError("job_poweroff_late", status=409)
        return {"poweroff": flag.value}

    def manager(slot: str) -> JobManager:
        if slot not in jobs:
            raise ApiError("unknown_slot", status=404)
        return jobs[slot]

    # --- voices -----------------------------------------------------------------------------------

    @app.post("/api/voices")
    def create_voice(voice: NewVoice):
        if voice.workflow not in ("clone", "import"):
            raise ApiError("bad_workflow")
        try:
            cfg = service.create_voice(root, voice.name, piper_name=voice.piper_name.strip() or None)
        except ValueError as err:
            raise ApiError("voice_create", str(err)) from err
        if voice.workflow != cfg.workflow:
            cfg.workflow = voice.workflow
            service.config_mod.save(service.voice_dir(root, cfg.name), cfg)
        service.remember_voice(root, cfg.name)
        return api.voice_summary(root, cfg.name)

    @app.get("/api/voices/{name}")
    def voice(name: str):
        need_voice(name)
        summary = api.voice_summary(root, name)
        summary["yaml"] = service.config_yaml(root, name)
        return summary

    @app.post("/api/voices/{name}/open")
    def open_voice(name: str):
        need_voice(name)
        service.remember_voice(root, name)
        return {"ok": True}

    def need_voice(name: str) -> None:
        if name not in service.list_voices(root):
            raise ApiError("unknown_voice", status=404, voice=name)

    # --- files ------------------------------------------------------------------------------------

    @app.get("/api/files/{rel:path}")
    def files(rel: str):
        path = (root / rel).resolve()
        if (
            root.resolve() not in path.parents
            or not path.is_file()
            or path.suffix.lower() not in SERVED_SUFFIXES
        ):
            return Response(status_code=404)
        return FileResponse(path)

    def start(
        kind: str, voice: str, args: list[str], *, slot: str = "current", poweroff: bool = False
    ) -> dict:
        try:
            manager(slot).start(kind, voice, args, poweroff=poweroff)
        except JobBusy as err:
            raise ApiError("job_busy", status=409, kind=err.kind, voice=err.voice) from err
        return api.job_payload(manager(slot))

    app.state.start = start

    # the guide: the built site inside the image, else the published one
    built = docs_dir or find_docs()
    if built is not None:
        app.mount("/docs", StaticFiles(directory=built, html=True), name="docs")
    else:

        @app.get("/docs/{rest:path}")
        def docs_online(rest: str = ""):
            return RedirectResponse(DOCS_SITE + rest)

    add_step_routes(app, root, need_voice, start, ApiError)
    add_clone_routes(app, root, need_voice, start, ApiError)
    app.state.machine = add_settings_routes(app, root, need_voice, start, ApiError)
    return app


def find_docs() -> Path | None:
    for candidate in (os.environ.get("PVC_DOCS_DIR"), Path(__file__).resolve().parents[2] / "site"):
        if candidate and (Path(candidate) / "index.html").is_file():
            return Path(candidate)
    return None


LOGIN_TEXTS = {
    "en": (
        "Piper Voice Cloner",
        "User",
        "Password",
        "Log in",
        "Wrong user or password.",
        "Too many wrong passwords: wait a minute.",
    ),
    "pl": (
        "Piper Voice Cloner",
        "Użytkownik",
        "Hasło",
        "Zaloguj",
        "Zły użytkownik albo hasło.",
        "Za dużo złych haseł: odczekaj minutę.",
    ),
}


def login_html(accept_language: str, failed: int = 0) -> str:
    lang = "pl" if accept_language.lower().startswith("pl") else "en"
    title, user, password, button, wrong, blocked = (html.escape(text) for text in LOGIN_TEXTS[lang])
    error = {1: wrong, 2: blocked}.get(failed, "")
    message = f'<p class="error" data-login-error>{error}</p>' if error else ""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><link rel="icon" href="/static/icon.svg">
<style>
:root {{ color-scheme: dark; --bg:#111318; --panel:#1b1e24; --line:#2f343c; --text:#e8eaed; --muted:#9aa0a6;
  --accent:#4f8cff; --field:#0d0f13; --red:#ff453a; }}
@media (prefers-color-scheme: light) {{ :root {{ color-scheme: light; --bg:#f2f3f7; --panel:#fff;
  --line:#d5d9e0; --text:#1d2026; --muted:#5f6670; --accent:#2f6fe4; --field:#fff; --red:#d0021b; }} }}
body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg); color:var(--text);
  font:14px/1.4 -apple-system,"SF Pro Text",Roboto,system-ui,sans-serif; }}
form {{ width:min(340px,calc(100vw - 32px)); display:grid; gap:12px; padding:24px; border-radius:14px;
  background:var(--panel); border:1px solid var(--line); }}
h1 {{ margin:0 0 4px; font-size:17px; display:flex; gap:10px; align-items:center; }}
h1 img {{ width:28px; height:28px; }}
label {{ display:grid; gap:4px; font-weight:600; }}
input {{ padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:var(--field);
  color:var(--text); font:inherit; }}
button {{ padding:9px 12px; border:0; border-radius:9px; background:var(--accent); color:#fff; font:inherit;
  font-weight:600; cursor:pointer; }}
.error {{ margin:0; color:var(--red); }}
</style></head>
<body><form method="post" action="/login" data-login>
<h1><img src="/static/icon.svg" alt="">{title}</h1>{message}
<label>{user}<input name="user" autocomplete="username" required autofocus></label>
<label>{password}<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">{button}</button>
</form></body></html>"""
