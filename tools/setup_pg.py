"""Bring the knowledge base to the starting state a module expects. Called by setup.sh.

    python tools/setup_pg.py m3     # nothing loaded; the module 3 demos build it
    python tools/setup_pg.py m4     # extension, schema, 5,000 chunks, HNSW and GIN indexes
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "m3" / "after"))
from db import connect  # noqa: E402
import load  # noqa: E402

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "m4"
    if stage == "m4":
        with connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        load.schema()
        load.load()
        with connect() as conn:
            conn.execute("CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
                         "WITH (m = 16, ef_construction = 200)")
            conn.execute("CREATE INDEX chunks_meta_gin ON chunks USING gin (meta)")
            conn.execute("ANALYZE chunks")
        print("Knowledge base ready: HNSW and GIN indexes built.")
        print("No B-tree on region here, so the planner uses HNSW for filtered queries and the starvation demo shows.")
    else:
        print("Module 3 starts empty: no extension, no tables")
