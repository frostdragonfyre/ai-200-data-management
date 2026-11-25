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


def metadata_query(product="blender", region="US"):
    raise NotImplementedError("You add this in the demo")


def vector_size():
    raise NotImplementedError("You add this in the demo")


def orphan():
    raise NotImplementedError("You add this in the demo")


def counts():
    raise NotImplementedError("You add this in the demo")


def table_sizes():
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "query" and len(sys.argv) > 2:
        metadata_query(product=sys.argv[3] if len(sys.argv) > 3 else "blender", region=sys.argv[2])
    else:
        {"schema": schema, "wrongdim": wrong_dimension, "load": load, "query": metadata_query,
         "size": vector_size, "orphan": orphan, "counts": counts, "tables": table_sizes}.get(cmd, lambda: print(__doc__))()
