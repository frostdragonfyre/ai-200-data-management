"""Module 3: watch the plan change when the vector index arrives, then size it.

    python m3/after/plans.py seq        # EXPLAIN ANALYZE top 5 with no vector index
    python m3/after/plans.py hnsw       # create the HNSW index (cosine)
    python m3/after/plans.py indexed    # EXPLAIN ANALYZE again
    python m3/after/plans.py l2         # same query ordered by <-> (Euclidean): no matching index
    python m3/after/plans.py halfvec    # halfvec expression index; compare index sizes
    python m3/after/plans.py halfquery  # query with the halfvec cast; EXPLAIN shows that index
    python m3/after/plans.py efsearch   # recall against exact search at ef_search 40, 100, 200, 400
    python m3/after/plans.py filters    # B-tree indexes on region and date, GIN on meta
    python m3/after/plans.py settings   # shared_buffers, maintenance_work_mem, work_mem
    python m3/after/plans.py reset      # drop the vector indexes so the demo can run again
    python m3/after/plans.py halfrecall # exact top 10 at full and at half precision: how many match
    python m3/after/plans.py fit        # table and index sizes next to shared_buffers
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.embed import embed  # noqa: E402
from db import connect  # noqa: E402

QUESTION = "I changed my mind about an order, can I return it?"


def qvec():
    return "[" + ",".join(f"{x:.6f}" for x in embed(QUESTION)) + "]"


def explain(conn, sql, params):
    plan = [r[0] for r in conn.execute("EXPLAIN (ANALYZE, COSTS OFF) " + sql, params).fetchall()]
    for line in plan:
        if any(k in line for k in ("Scan", "Limit", "Sort", "Execution Time", "Order By", "Rows Removed")):
            print("  " + re.sub(r"'\[[^\]]*\]'", "'[query vector]'", line.strip()))


def top5(op="<=>"):
    return f"SELECT id FROM chunks ORDER BY embedding {op} %s::vector LIMIT 5"


def size(conn, name):
    return conn.execute("SELECT pg_size_pretty(pg_relation_size(%s::regclass))", (name,)).fetchone()[0]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    with connect() as conn:
        if cmd == "seq":
            explain(conn, top5(), (qvec(),))
        elif cmd == "hnsw":
            t = time.perf_counter()
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
            print(f"Built chunks_embedding_hnsw in {time.perf_counter() - t:.1f} s, size {size(conn, 'chunks_embedding_hnsw')}")
# >>> demo
        elif cmd == "indexed":
            explain(conn, top5(), (qvec(),))
        elif cmd == "l2":
            explain(conn, top5("<->"), (qvec(),))
        elif cmd == "halfvec":
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_half ON chunks "
                         "USING hnsw ((embedding::halfvec(384)) halfvec_cosine_ops)")
            print(f"vector index:  {size(conn, 'chunks_embedding_hnsw')}")
            print(f"halfvec index: {size(conn, 'chunks_embedding_half')}")
        elif cmd == "halfquery":
            explain(conn, "SELECT id FROM chunks ORDER BY embedding::halfvec(384) <=> %s::halfvec(384) LIMIT 5", (qvec(),))
        elif cmd == "efsearch":
            q = qvec()
            conn.execute("SET enable_indexscan = off")
            exact = [r[0] for r in conn.execute(top5(), (q,)).fetchall()]
            conn.execute("SET enable_indexscan = on")
            print(f"exact top 5 (no index):  {exact}")
            for ef in (40, 100, 200, 400):
                conn.execute(f"SET hnsw.ef_search = {ef}")
                t = time.perf_counter()
                for _ in range(20):
                    ids = [r[0] for r in conn.execute(top5(), (q,)).fetchall()]
                ms = (time.perf_counter() - t) / 20 * 1000
                print(f"ef_search {ef:>3}: {ms:5.2f} ms per query, {len(set(ids) & set(exact))} of 5 true neighbors found")
        elif cmd == "filters":
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_region_eff ON chunks (region, effective_from)")
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_meta_gin ON chunks USING gin (meta)")
            print("Created chunks_region_eff (B-tree) and chunks_meta_gin (GIN)")
        elif cmd == "settings":
            for name in ("shared_buffers", "maintenance_work_mem", "work_mem", "max_connections"):
                print(f"  {name:<22} {conn.execute(f'SHOW {name}').fetchone()[0]}")
        elif cmd == "halfrecall":
            q = qvec()
            conn.execute("SET enable_indexscan = off")
            full = [r[0] for r in conn.execute("SELECT id FROM chunks ORDER BY embedding <=> %s::vector LIMIT 10", (q,)).fetchall()]
            half = [r[0] for r in conn.execute("SELECT id FROM chunks ORDER BY embedding::halfvec(384) <=> %s::halfvec(384) LIMIT 10", (q,)).fetchall()]
            print(f"full precision, exact top 10: {full}")
            print(f"half precision, exact top 10: {half}")
            print(f"{len(set(full) & set(half))} of 10 in common, {sum(a == b for a, b in zip(full, half))} in the same position")
        elif cmd == "fit":
            for name in ("chunks", "chunks_embedding_hnsw", "chunks_embedding_half"):
                try:
                    print(f"  {name:<24} {size(conn, name)}")
                except Exception:
                    conn.rollback() if not conn.autocommit else None
            total = conn.execute("SELECT pg_size_pretty(pg_total_relation_size('chunks'))").fetchone()[0]
            print(f"  {'chunks, everything':<24} {total}")
            print(f"  {'shared_buffers':<24} {conn.execute('SHOW shared_buffers').fetchone()[0]}")
        elif cmd == "reset":
            conn.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw")
            conn.execute("DROP INDEX IF EXISTS chunks_embedding_half")
            print("Vector indexes dropped")
# <<< demo
        else:
            print(__doc__)
