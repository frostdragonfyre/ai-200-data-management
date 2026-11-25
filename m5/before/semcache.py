"""Module 5: a semantic cache. Recognize a question by meaning, not by its exact text.

    python m5/after/semcache.py create          # FT.CREATE semcache: TEXT, TAG, HNSW vector (384, cosine)
    python m5/after/semcache.py store           # store two answered questions with a one-hour TTL
    python m5/after/semcache.py ask "can I send back a broken item?" [--region US] [--threshold 0.25]
    python m5/after/semcache.py info            # FT.INFO: how many keys the index holds
    python m5/after/semcache.py outside         # a hash outside the sc: prefix is never indexed
    python m5/after/semcache.py drop            # drop the index and its keys so the demo can run again
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from redis.commands.search.field import TagField, TextField, VectorField  # noqa: E402
from redis.commands.search.index_definition import IndexDefinition, IndexType  # noqa: E402
from redis.commands.search.query import Query  # noqa: E402
from cache import connect  # noqa: E402
from common.embed import embed  # noqa: E402

INDEX, PREFIX = "semcache", "sc:"
ANSWERED = [
    ("How do I return a damaged item?", "Contact support within 7 days; we send a replacement or a refund, and you keep the damaged item.", "US"),
    ("When will my refund show up?", "US refunds post to the original payment method within 5 to 10 business days.", "US"),
]


def as_bytes(text):
    return np.array(embed(text), dtype=np.float32).tobytes()


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def create(r):
    raise NotImplementedError("You add this in the demo")


def store(r):
    raise NotImplementedError("You add this in the demo")


def ask(r, question, region="US", threshold=0.25):
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    r = connect()
    if cmd == "create":
        create(r)
    elif cmd == "store":
        store(r)
    elif cmd == "ask":
        ask(r, sys.argv[2], arg("--region", "US"), float(arg("--threshold", "0.25")))
    elif cmd == "info":
        info = r.ft(INDEX).info()
        print(f"{INDEX}: {info['num_docs']} documents indexed, prefix {PREFIX}")
    elif cmd == "outside":
        r.hset("other:1", mapping={"question": "How do I return a damaged item?", "answer": "x", "region": "US",
                                    "vec": as_bytes("How do I return a damaged item?")})
        print(f"Stored other:1; {INDEX} still holds {r.ft(INDEX).info()['num_docs']} documents")
        r.delete("other:1")
    elif cmd == "drop":
        try:
            r.ft(INDEX).dropindex(delete_documents=True)
            print(f"Dropped {INDEX} and its keys")
        except Exception as e:  # index may not exist yet
            print(f"Nothing to drop: {e}")
    else:
        print(__doc__)
