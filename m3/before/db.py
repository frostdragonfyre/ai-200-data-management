"""Module 3: connect with psycopg, turn on pgvector, prove it works.

    python m3/after/db.py          # create the extension, print its version, run one distance
    python m3/after/db.py avail    # available versus installed, before CREATE EXTENSION
Turning on pgvector takes two steps: allow VECTOR in the server parameter
azure.extensions, then CREATE EXTENSION in each database that uses it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg  # noqa: E402
from common import config  # noqa: E402


def connect(**kw):
    return psycopg.connect(config.pg_conninfo(**kw), autocommit=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["avail"]:
        with connect() as conn:
            row = conn.execute("SELECT name, default_version, installed_version FROM pg_available_extensions "
                               "WHERE name = 'vector'").fetchone()
        print(f"name {row[0]}, default_version {row[1]}, installed_version {row[2]}" if row else
              "vector is not listed on this server")
        sys.exit(0)
    with connect() as conn:
        try:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except psycopg.Error as e:
            print(f"{type(e).__name__}: {str(e).splitlines()[0]}")
            print("Allow VECTOR in the server parameter azure.extensions, then run this again.")
            sys.exit(1)
        version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
        print(f"pgvector {version} is installed in this database")
        # TODO: you add this in the demo
