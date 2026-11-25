"""Module 4: measure what a connection costs, three ways.

    python m4/after/connections.py limits      # max_connections and the backends in use now
    python m4/after/connections.py version     # one connection through PgBouncer (6432)
    python m4/after/connections.py measure     # median of 10: direct, PgBouncer, application pool
    python m4/after/connections.py burst       # 40 concurrent clients: server backends with and without PgBouncer
"""
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg  # noqa: E402
from psycopg_pool import ConnectionPool  # noqa: E402
from common import config  # noqa: E402

DIRECT, BOUNCER = config.get("PG_PORT", "5432"), config.get("PG_BOUNCER_PORT", "6432")


def connect(port):
    # prepare_threshold=None turns off server-side prepared statements;
    # PgBouncer in transaction mode can hand the next query to a different server connection.
    return psycopg.connect(config.pg_conninfo(port=port), autocommit=True, prepare_threshold=None)


def median_ms(fn, rounds=10):
    times = []
    for _ in range(rounds):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def connect_and_query(port):
    with connect(port) as conn:
        conn.execute("SELECT 1").fetchone()


def measure():
    raise NotImplementedError("You add this in the demo")


def burst(clients=40):
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "limits":
        with connect(DIRECT) as conn:
            print(f"max_connections: {conn.execute('SHOW max_connections').fetchone()[0]}")
            n = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'").fetchone()[0]
            print(f"client backends right now: {n}")
    elif cmd == "version":
        with connect(BOUNCER) as conn:
            print(f"Connected through PgBouncer on {BOUNCER}: {conn.execute('SHOW server_version').fetchone()[0]}")
    elif cmd == "measure":
        measure()
    elif cmd == "burst":
        burst(int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    elif cmd == "poolstats":
        with ConnectionPool(config.pg_conninfo(port=BOUNCER), min_size=2, max_size=10,
                            kwargs={"autocommit": True, "prepare_threshold": None}) as pool:
            pool.wait()
            for _ in range(200):
                with pool.connection() as conn:
                    conn.execute("SELECT 1").fetchone()
            st = pool.get_stats()
            print(f"200 requests served by {st.get('connections_num', 0)} connections opened "
                  f"(pool size now {st.get('pool_size')}, available {st.get('pool_available')})")
    else:
        print(__doc__)
