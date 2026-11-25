"""Module 3: create the schema and bulk-load the knowledge base.

    python m3/after/load.py schema     # run schema.sql
    python m3/after/load.py wrongdim   # insert a 1,536-number vector into vector(384)
    python m3/after/load.py load       # COPY articles and 5,000 chunks with embeddings
    python m3/after/load.py query      # parameterized metadata query
    python m3/after/load.py size       # bytes per stored vector
    python m3/after/load.py orphan     # a chunk that points at an article that does not exist
    python m3/after/load.py counts     # rows per region, and chunks per article
    python m3/after/load.py query EU blender   # the same metadata query for another customer
    python m3/after/load.py tables     # table, TOAST, and index sizes on disk
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psycopg  # noqa: E402
from db import connect  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def schema():
    with connect() as conn:
        conn.execute((HERE / "schema.sql").read_text())
    print("Created articles and chunks")


def wrong_dimension():
    with connect() as conn:
        try:
            conn.execute("INSERT INTO chunks (id, article_id, chunk_no, content, product, region, effective_from, embedding) "
                         "VALUES (999999, 42, 99, 'test', 'all', 'EU', current_date, %s::vector)",
                         ("[" + ",".join(["0.01"] * 1536) + "]",))
        except psycopg.Error as e:
            print(f"{type(e).__name__}: {str(e).splitlines()[0]}")


def load():
    articles = json.loads((ROOT / "data/kb_articles.json").read_text())
    start = time.perf_counter()
    with connect() as conn, conn.cursor() as cur:
        with cur.copy("COPY articles (id, title, product, region, effective_from, effective_to, meta) FROM STDIN") as cp:
            for a in articles:
                cp.write_row((a["id"], a["title"], a["product"], a["region"], a["effective_from"],
                              a["effective_to"], json.dumps(a["meta"])))
        with open(ROOT / "data/chunks.csv", encoding="utf-8") as f, \
                cur.copy("COPY chunks (id, article_id, chunk_no, content, product, region, "
                         "effective_from, effective_to, meta, embedding) FROM STDIN") as cp:
            for r in csv.DictReader(f):
                cp.write_row((r["id"], r["article_id"], r["chunk_no"], r["content"], r["product"], r["region"],
                              r["effective_from"], r["effective_to"] or None, r["meta"], r["embedding"]))
        n = cur.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"Loaded {len(articles)} articles and {n} chunks in {time.perf_counter() - start:.1f} s")


# >>> demo
def metadata_query(product="blender", region="US"):
    sql = ("SELECT c.id, a.title, c.effective_from FROM chunks c JOIN articles a ON a.id = c.article_id "
           "WHERE c.product IN (%s, 'all') AND c.region = %s "
           "AND c.effective_from <= current_date AND (c.effective_to IS NULL OR c.effective_to >= current_date) "
           "ORDER BY a.title, c.chunk_no")
    with connect() as conn:
        rows = conn.execute(sql, (product, region)).fetchall()
    for cid, title, eff in rows:
        print(f"  {cid}  {eff}  {title}")
    print(f"{len(rows)} chunks apply to a {region} customer with a {product}, today")


def vector_size():
    with connect() as conn:
        b = conn.execute("SELECT pg_column_size(embedding) FROM chunks LIMIT 1").fetchone()[0]
        h = conn.execute("SELECT pg_column_size(embedding::halfvec(384)) FROM chunks LIMIT 1").fetchone()[0]
    print(f"vector(384): {b} bytes per row (4 bytes x 384 + 8-byte header)")
    print(f"halfvec(384): {h} bytes per row (2 bytes x 384 + 8-byte header)")


def orphan():
    with connect() as conn:
        try:
            conn.execute("INSERT INTO chunks (id, article_id, chunk_no, content, product, region, effective_from, embedding) "
                         "VALUES (999998, 99999, 1, 'orphan', 'all', 'EU', current_date, %s::vector)",
                         ("[" + ",".join(["0.01"] * 384) + "]",))
        except psycopg.Error as e:
            print(f"{type(e).__name__}: {str(e).splitlines()[0]}")
            detail = getattr(e.diag, "message_detail", None)
            if detail:
                print(detail)


def counts():
    with connect() as conn:
        for region, a, c in conn.execute(
                "SELECT a.region, count(DISTINCT a.id), count(c.id) FROM articles a "
                "LEFT JOIN chunks c ON c.article_id = a.id GROUP BY 1 ORDER BY 1").fetchall():
            print(f"  {region:<3} {a:>4} articles  {c:>5} chunks")
        lo, hi, avg = conn.execute("SELECT min(n), max(n), round(avg(n), 1) FROM "
                                   "(SELECT count(*) n FROM chunks GROUP BY article_id) t").fetchone()
        print(f"Chunks per article: {lo} to {hi}, about {avg} on average")


def table_sizes():
    with connect() as conn:
        for label, sql in (("chunks table (heap)", "pg_relation_size('chunks')"),
                           ("chunks TOAST", "pg_total_relation_size('chunks') - pg_relation_size('chunks') - pg_indexes_size('chunks')"),
                           ("chunks indexes", "pg_indexes_size('chunks')"),
                           ("articles, everything", "pg_total_relation_size('articles')")):
            print(f"  {label:<22} {conn.execute(f'SELECT pg_size_pretty({sql}::bigint)').fetchone()[0]}")
# <<< demo


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "query" and len(sys.argv) > 2:
        metadata_query(product=sys.argv[3] if len(sys.argv) > 3 else "blender", region=sys.argv[2])
    else:
        {"schema": schema, "wrongdim": wrong_dimension, "load": load, "query": metadata_query,
         "size": vector_size, "orphan": orphan, "counts": counts, "tables": table_sizes}.get(cmd, lambda: print(__doc__))()
