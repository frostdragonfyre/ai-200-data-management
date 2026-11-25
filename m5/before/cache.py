"""Module 5: cache answers in Azure Managed Redis; expire them and invalidate them.

    python m5/after/cache.py ttl          # a key with a 5-second TTL counts down and disappears
    python m5/after/cache.py nottl        # a key with no expiry: TTL is -1
    python m5/after/cache.py aside        # cache-aside around the answer path: a miss, then a hit
    python m5/after/cache.py bump         # policy version 3 -> 4: same question, new key, a miss
    python m5/after/cache.py keys         # list answer keys with their TTLs
    python m5/after/cache.py delete       # delete one corrected answer; the next read misses
    python m5/after/cache.py normalize    # three spellings of one question map to one key
    python m5/after/cache.py memory       # memory used, the limit, and the eviction policy
"""
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "m4" / "after"))
import redis  # noqa: E402
from common import config  # noqa: E402

DAY = 86400
QUESTION, REGION = "How long do I have to return an order?", "US"


def connect():
    # Port 10000, TLS, access key from .env. Enterprise clustering presents one endpoint,
    # so a plain client works; the OSS cluster policy would need a cluster-aware client.
    return redis.Redis(host=config.get("REDIS_HOST"), port=int(config.get("REDIS_PORT", "10000")),
                       password=config.get("REDIS_KEY"), ssl=config.get("REDIS_SSL", "true") == "true",
                       decode_responses=True)


def normalize(q):
    return " ".join(q.lower().replace("?", "").split())


def answer_key(r, question, region):
    version = r.get(f"policy_version:{region}") or "3"
    return f"answer:v{version}:{region}:{hashlib.sha256(normalize(question).encode()).hexdigest()[:16]}"


def answer_uncached(question, region):
    """The expensive path from module 4: embed, retrieve, prompt, model."""
    import psycopg
    import rag
    with psycopg.connect(config.pg_conninfo(port=config.get("PG_BOUNCER_PORT", "6432")),
                         autocommit=True, prepare_threshold=None) as conn:
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
        rows = rag.retrieve(conn, question, region, k=5)
        prompt = rag.build_prompt(question, rows)
    import json
    import urllib.request
    req = urllib.request.Request(rag.STUB_URL, data=json.dumps({"prompt": prompt}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())["answer"]


def answer(r, question, region):
    """Cache-aside: check the cache, fall through on a miss, store the result with a TTL."""
    raise NotImplementedError("You add this in the demo")


def timed(r):
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    r = connect()
    if cmd == "ttl":
        print("PING ->", r.ping())
        r.set("answer:demo", "Start a return from Orders.", ex=5)
        for _ in range(4):
            print("TTL ->", r.ttl("answer:demo"))
            time.sleep(1.5)
        time.sleep(1)
        print("GET after expiry ->", r.get("answer:demo"))
    elif cmd == "nottl":
        r.set("answer:nottl", "This key never expires.")
        print("TTL answer:nottl ->", r.ttl("answer:nottl"), "  (-1: the key exists with no expiry)")
        print("TTL answer:gone  ->", r.ttl("answer:gone"), "  (-2: the key does not exist)")
        r.expire("answer:nottl", 60)
        print("EXPIRE 60, then TTL ->", r.ttl("answer:nottl"))
    elif cmd == "aside":
        r.set(f"policy_version:{REGION}", 3)
        timed(r)
    elif cmd == "bump":
        print("INCR policy_version ->", r.incr(f"policy_version:{REGION}"))
        timed(r)
    elif cmd == "keys":
        for k in sorted(r.scan_iter("answer:v*")):
            print(f"  {k}  TTL {r.ttl(k)} s")
    elif cmd == "delete":
        key = answer_key(r, QUESTION, REGION)
        print("DEL ->", r.delete(key), key)
        print("Next read:", answer(r, QUESTION, REGION)[1])
    elif cmd == "normalize":
        for q in (QUESTION, "how LONG do I have to   return an order", "What is the deadline to send an order back?"):
            print(f"{answer_key(r, q, REGION)}  <- {q!r}")
    elif cmd == "memory":
        m = r.info("memory")
        print("used_memory_human ->", m.get("used_memory_human"))
        print("maxmemory_human   ->", m.get("maxmemory_human"))
        print("maxmemory_policy  ->", m.get("maxmemory_policy"))
        print("answer keys       ->", sum(1 for _ in r.scan_iter("answer:v*")))
    else:
        print(__doc__)
