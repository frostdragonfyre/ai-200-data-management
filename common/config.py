"""Read settings from .env (written by setup.sh) or the environment.

Values are never printed. Use get("NAME") in demo code; it raises a clear error
when a setting is missing instead of failing later with a confusing one.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def get(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise KeyError(f"{name} is not set. Run setup.sh or copy .env.example to .env and fill it in.")
    return value


def pg_conninfo(port=None, dbname=None):
    """libpq connection string for the knowledge base server."""
    return (f"host={get('PG_HOST')} port={port or get('PG_PORT', '5432')} "
            f"dbname={dbname or get('PG_DB', 'postgres')} user={get('PG_USER')} "
            f"password={get('PG_PASSWORD')} sslmode={get('PG_SSLMODE', 'require')}")
