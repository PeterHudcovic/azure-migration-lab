import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Config:
    ENV_NAME = os.getenv("ENV_NAME", "prod")
    BANNER = os.getenv("BANNER", "Kubernetes Operations Console")
    SESSION_MINUTES = _int("SESSION_MINUTES", 10)
    TARGET_NAMESPACE = os.getenv("TARGET_NAMESPACE", "prod")
    TARGET_DEPLOYMENT = os.getenv("TARGET_DEPLOYMENT", "pong-app")
    MAX_REPLICAS = _int("MAX_REPLICAS", 5)
    DEMO_MINUTES = _int("DEMO_MINUTES", 15)
    DEMO_INTERVAL_SECONDS = _int("DEMO_INTERVAL_SECONDS", 180)
    LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
    PG_HOST = os.getenv("DB_HOST", os.getenv("PG_HOST", "migration-postgresql"))
    PG_PORT = _int("DB_PORT", _int("PG_PORT", 5432))
    PG_USER = os.getenv("DB_USER", os.getenv("PG_USER", "migrationuser"))
    PG_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("PG_PASSWORD", ""))
    PG_DATABASE = os.getenv("DB_NAME", os.getenv("PG_DATABASE", "migrationdb"))
    POD_NAME = os.getenv("POD_NAME", "unknown-pod")
    APP_VERSION = os.getenv("APP_VERSION", "ops-v4")

    @classmethod
    def dsn(cls):
        return f"postgresql://{cls.PG_USER}:{cls.PG_PASSWORD}@{cls.PG_HOST}:{cls.PG_PORT}/{cls.PG_DATABASE}"


cfg = Config()
