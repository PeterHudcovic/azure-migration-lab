import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

import db
import k8s_ops
from config import cfg

STATIC = Path(__file__).parent / "static"
subscribers = set()


def broadcast(event):
    event.setdefault("at", datetime.now(timezone.utc).strftime("%H:%M:%S"))
    for q in list(subscribers):
        q.put_nowait(event)


async def _pump():
    q = asyncio.Queue()
    task = asyncio.create_task(k8s_ops.watch_pods(q))
    try:
        while True:
            broadcast(await q.get())
    finally:
        task.cancel()


async def _demo_scheduler():
    while True:
        try:
            tick = await db.claim_demo_tick()
            if tick:
                msg = k8s_ops.restart("demo-mode")
                actor = tick.get("started_by") or "demo"
                await db.record(actor, "demo_rollout", cfg.TARGET_DEPLOYMENT, msg)
                broadcast({"kind": "demo", "message": f"Demo Mode: {msg}"})
        except Exception as exc:
            print(f"[demo] scheduler error: {exc}")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_):
    k8s_ops.init()
    await db.connect()
    pump = asyncio.create_task(_pump())
    demo = asyncio.create_task(_demo_scheduler())
    yield
    pump.cancel()
    demo.cancel()
    await db.disconnect()


app = FastAPI(
    title="Azure Migration Lab - Kubernetes Operations Console",
    version=cfg.APP_VERSION,
    lifespan=lifespan,
)
bearer = HTTPBearer(auto_error=False)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), display-capture=(), fullscreen=(), "
        "geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()"
    )
    return response


class LoginBody(BaseModel):
    identity: str = Field(min_length=1, max_length=120)
    password: str


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email_to_none(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v or None


class ScaleBody(BaseModel):
    replicas: int = Field(ge=1, le=50)


class CommandBody(BaseModel):
    command: str = Field(min_length=1, max_length=300)


def issue_token(username, role):
    exp = datetime.now(timezone.utc) + timedelta(minutes=cfg.SESSION_MINUTES)
    token = jwt.encode(
        {"sub": username, "role": role, "exp": exp, "jti": secrets.token_hex(8)},
        cfg.JWT_SECRET,
        algorithm="HS256",
    )
    return token, int(exp.timestamp())


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if creds is None:
        raise HTTPException(401, "Authentication required.")
    try:
        claims = jwt.decode(creds.credentials, cfg.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, f"Session expired after {cfg.SESSION_MINUTES} minutes.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid authentication token.")
    return {"name": claims["sub"], "role": claims.get("role", "guest")}


def require(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role is not permitted to perform this operation.")
        return user
    return dep


@app.post("/api/register")
async def register(body: RegisterBody):
    try:
        await db.register(body.username, body.email, body.password)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    await db.record(body.username, "register", body.email)
    return {"message": "Registration complete. You can now sign in."}


@app.post("/api/login")
async def login(body: LoginBody):
    identity = body.identity.strip()
    if identity.lower() == "guest" and secrets.compare_digest(body.password, "guest"):
        user = {"username": "guest", "role": "guest"}
    elif identity.lower() == "admin" and secrets.compare_digest(body.password, cfg.LOGIN_PASSWORD):
        user = {"username": "admin", "role": "admin"}
    else:
        user = await db.verify_user(identity, body.password)
        if not user:
            raise HTTPException(401, "Invalid username/email or password.")
    token, exp = issue_token(user["username"], user["role"])
    await db.record(user["username"], "login", user["role"])
    return {
        "token": token,
        "expires_at": exp,
        "minutes": cfg.SESSION_MINUTES,
        "username": user["username"],
        "role": user["role"],
    }


@app.get("/api/state")
async def state(user=Depends(current_user)):
    return k8s_ops.deployment_state()


@app.get("/api/terminal/{command}")
async def terminal_button(command: str, user=Depends(current_user)):
    try:
        return {"output": k8s_ops.command_output(command)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/terminal")
async def terminal_typed(body: CommandBody, user=Depends(current_user)):
    try:
        output = k8s_ops.parse_readonly_command(body.command)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await db.record(user["name"], "terminal", cfg.TARGET_NAMESPACE, body.command[:250])
    return {"output": output}


@app.get("/api/check")
async def check(user=Depends(current_user)):
    return k8s_ops.health_summary(db.is_up())


@app.get("/api/logs/{workload}")
async def pod_logs(
    workload: str,
    tail: int = Query(100, ge=1, le=200),
    user=Depends(require("user", "admin")),
):
    try:
        return k8s_ops.pod_logs(workload, tail)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/pods/{name}")
async def kill(name: str, user=Depends(require("admin"))):
    try:
        msg = k8s_ops.kill_pod(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await db.record(user["name"], "kill_pod", name)
    broadcast({"kind": "action", "message": f"{user['name']}: {msg}"})
    return {"message": msg}


@app.post("/api/scale")
async def scale(body: ScaleBody, user=Depends(require("user", "admin"))):
    try:
        msg = k8s_ops.scale(body.replicas)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await db.record(user["name"], "scale", cfg.TARGET_DEPLOYMENT, str(body.replicas))
    broadcast({"kind": "action", "message": f"{user['name']}: {msg}"})
    return {"message": msg}


@app.post("/api/restart")
async def restart(user=Depends(require("user", "admin"))):
    msg = k8s_ops.restart("manual")
    await db.record(user["name"], "restart", cfg.TARGET_DEPLOYMENT)
    broadcast({"kind": "action", "message": f"{user['name']}: {msg}"})
    return {"message": msg}


@app.get("/api/demo")
async def demo_status(user=Depends(current_user)):
    return await db.demo_status()


@app.post("/api/demo/start")
async def demo_start(user=Depends(require("user", "admin"))):
    status = await db.start_demo(user["name"])
    await db.record(user["name"], "demo_start", cfg.TARGET_DEPLOYMENT, f"{cfg.DEMO_MINUTES} minutes")
    broadcast({"kind": "demo", "message": f"{user['name']} started Demo Mode for {cfg.DEMO_MINUTES} minutes"})
    return status


@app.post("/api/demo/stop")
async def demo_stop(user=Depends(require("user", "admin"))):
    status = await db.stop_demo()
    await db.record(user["name"], "demo_stop", cfg.TARGET_DEPLOYMENT)
    broadcast({"kind": "demo", "message": f"{user['name']} stopped Demo Mode"})
    return status


@app.get("/api/history")
async def history(user=Depends(current_user)):
    return await db.history(20)


@app.get("/api/events")
async def events(request: Request, user=Depends(current_user)):
    q = asyncio.Queue()
    subscribers.add(q)

    async def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    yield f"data: {json.dumps(await asyncio.wait_for(q.get(), 20))}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/whoami")
async def whoami(user=Depends(current_user)):
    return {
        "app_version": cfg.APP_VERSION,
        "env": cfg.ENV_NAME,
        "served_by": cfg.POD_NAME,
        "session_minutes": cfg.SESSION_MINUTES,
        "target": f"{cfg.TARGET_NAMESPACE}/{cfg.TARGET_DEPLOYMENT}",
        "db_connected": db.is_up(),
        "audit_rows": await db.count(),
        "user": user,
    }


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/readyz")
async def readyz():
    if not db.is_up():
        raise HTTPException(503, "PostgreSQL is not connected.")
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")
