import asyncpg
from datetime import datetime, timedelta, timezone
from passlib.hash import bcrypt
from config import cfg

_pool = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  id BIGSERIAL PRIMARY KEY,
  at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  detail TEXT,
  env TEXT NOT NULL,
  served_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_at_idx ON audit (at DESC);

CREATE TABLE IF NOT EXISTS app_users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_control (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  active_until TIMESTAMPTZ,
  next_run TIMESTAMPTZ,
  started_by TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO demo_control(id) VALUES (1) ON CONFLICT (id) DO NOTHING;
"""


async def connect():
    global _pool
    try:
        _pool = await asyncpg.create_pool(cfg.dsn(), min_size=1, max_size=5)
        async with _pool.acquire() as c:
            await c.execute(SCHEMA)
    except Exception as exc:
        _pool = None
        print(f"[db] connection failed; audit/users/demo disabled: {exc}")


async def disconnect():
    if _pool:
        await _pool.close()


def is_up():
    return _pool is not None


async def record(actor, action, target="", detail=""):
    if not _pool:
        return
    try:
        async with _pool.acquire() as c:
            await c.execute(
                "INSERT INTO audit (actor,action,target,detail,env,served_by) VALUES ($1,$2,$3,$4,$5,$6)",
                actor, action, target, detail, cfg.ENV_NAME, cfg.POD_NAME,
            )
    except Exception as exc:
        print(f"[db] audit write failed: {exc}")


async def history(limit=50):
    if not _pool:
        return []
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT at,actor,action,target,detail,served_by FROM audit ORDER BY at DESC LIMIT $1", limit
        )
    return [
        {
            "at": r["at"].astimezone(timezone.utc).isoformat(),
            "actor": r["actor"],
            "action": r["action"],
            "target": r["target"],
            "detail": r["detail"],
            "served_by": r["served_by"],
        }
        for r in rows
    ]


async def count():
    if not _pool:
        return 0
    async with _pool.acquire() as c:
        return await c.fetchval("SELECT count(*) FROM audit")


async def register(username, email, password):
    if not _pool:
        raise RuntimeError("PostgreSQL unavailable")
    password_hash = bcrypt.hash(password)
    try:
        async with _pool.acquire() as c:
            await c.execute(
                "INSERT INTO app_users(username,email,password_hash,role) VALUES($1,$2,$3,$4)",
                username, email.lower(), password_hash, "user",
            )
    except asyncpg.UniqueViolationError:
        raise ValueError("Username or email already exists.")


async def verify_user(identity, password):
    if not _pool:
        return None
    async with _pool.acquire() as c:
        r = await c.fetchrow(
            "SELECT username,email,password_hash,role FROM app_users WHERE username=$1 OR lower(email)=lower($1)",
            identity,
        )
    if r and bcrypt.verify(password, r["password_hash"]):
        return {"username": r["username"], "email": r["email"], "role": r["role"]}
    return None


async def start_demo(actor: str):
    if not _pool:
        raise RuntimeError("PostgreSQL unavailable")
    now = datetime.now(timezone.utc)
    active_until = now + timedelta(minutes=cfg.DEMO_MINUTES)
    async with _pool.acquire() as c:
        await c.execute(
            """
            UPDATE demo_control
               SET active_until=$1, next_run=$2, started_by=$3, updated_at=now()
             WHERE id=1
            """,
            active_until, now, actor,
        )
    return await demo_status()


async def stop_demo():
    if not _pool:
        raise RuntimeError("PostgreSQL unavailable")
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE demo_control SET active_until=NULL,next_run=NULL,updated_at=now() WHERE id=1"
        )
    return await demo_status()


async def demo_status():
    if not _pool:
        return {"active": False, "active_until": None, "next_run": None, "started_by": None}
    async with _pool.acquire() as c:
        r = await c.fetchrow("SELECT active_until,next_run,started_by FROM demo_control WHERE id=1")
    now = datetime.now(timezone.utc)
    active = bool(r and r["active_until"] and r["active_until"] > now)
    return {
        "active": active,
        "active_until": r["active_until"].astimezone(timezone.utc).isoformat() if active else None,
        "next_run": r["next_run"].astimezone(timezone.utc).isoformat() if active and r["next_run"] else None,
        "started_by": r["started_by"] if r else None,
        "interval_seconds": cfg.DEMO_INTERVAL_SECONDS,
        "duration_minutes": cfg.DEMO_MINUTES,
    }


async def claim_demo_tick():
    """Atomically lets only one console Pod claim each scheduled demo rollout."""
    if not _pool:
        return None
    async with _pool.acquire() as c:
        r = await c.fetchrow(
            """
            UPDATE demo_control
               SET next_run = now() + ($1 * interval '1 second'), updated_at=now()
             WHERE id=1
               AND active_until > now()
               AND next_run IS NOT NULL
               AND next_run <= now()
         RETURNING active_until, next_run, started_by
            """,
            cfg.DEMO_INTERVAL_SECONDS,
        )
    if not r:
        return None
    return {
        "active_until": r["active_until"].astimezone(timezone.utc).isoformat(),
        "next_run": r["next_run"].astimezone(timezone.utc).isoformat(),
        "started_by": r["started_by"],
    }
