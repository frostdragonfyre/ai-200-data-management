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


# >>> demo
def create(r):
    schema = (TextField("question"), TextField("answer"), TagField("region"),
              VectorField("vec", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}))
    r.ft(INDEX).create_index(schema, definition=IndexDefinition(prefix=[PREFIX], index_type=IndexType.HASH))
    print(f"Created index {INDEX} on hashes with prefix {PREFIX}")


def store(r):
    for i, (question, answer, region) in enumerate(ANSWERED):
        key = f"{PREFIX}{i}"
        r.hset(key, mapping={"question": question, "answer": answer, "region": region, "vec": as_bytes(question)})
        r.expire(key, 3600)
        print(f"Stored {key}: {question!r} ({region}, TTL 1 hour)")


def ask(r, question, region="US", threshold=0.25):
    q = (Query(f"(@region:{{{region}}})=>[KNN 1 @vec $v AS dist]")
         .sort_by("dist").return_fields("question", "answer", "dist").dialect(2))
    docs = r.ft(INDEX).search(q, query_params={"v": as_bytes(question)}).docs
    if not docs:
        print(f"No cached answer tagged {region}: miss, fall through to retrieval")
        return None
    d = float(docs[0].dist)
    verdict = "HIT" if d <= threshold else "miss"
    print(f"{question!r}\n  nearest {docs[0].question!r}  distance {d:.3f}  threshold {threshold}  -> {verdict}")
    return docs[0].answer if d <= threshold else None
# <<< demo


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
