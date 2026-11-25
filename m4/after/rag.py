"""Module 4: retrieve context with metadata filters, then ground the answer.

    python m4/after/rag.py unfiltered       # top 3 by distance alone
    python m4/after/rag.py filtered         # region EU and in effect today
    python m4/after/rag.py nodate           # region EU only: the superseded version appears
    python m4/after/rag.py starve           # LIMIT 5, EU filter, a password question: iterative scan off, then on
    python m4/after/rag.py answer           # iterative scan, grounded prompt, stub model, citation
    python m4/after/rag.py offtopic         # a question the knowledge base cannot answer
Options: --region US, --port 6432 (through PgBouncer), --q "your question"; nofilter = answer with no filters
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg  # noqa: E402
from common import config  # noqa: E402
from common.embed import embed  # noqa: E402

QUESTION = "I changed my mind about an order, can I return it?"
STARVE_QUESTION = "How do I reset my password?"   # few EU chunks sit near it, so the filter starves the index
MAX_DISTANCE = 0.7          # farther than this, the sources don't answer the question
STUB_URL = "http://127.0.0.1:8000/answer"


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def vec(text):
    return "[" + ",".join(f"{x:.6f}" for x in embed(text)) + "]"


def retrieve(conn, question, region=None, in_effect=True, k=3, ef=400):
    conn.execute(f"SET hnsw.ef_search = {ef}")  # wider HNSW search: duplicate chunks hide neighbors at the default 40
    where, params = [], {"q": vec(question), "k": k}
# >>> demo
    if region:
        where.append("region = %(region)s")
        params["region"] = region
    if in_effect:
        where.append("effective_from <= current_date AND (effective_to IS NULL OR effective_to >= current_date)")
# <<< demo
    sql = ("SELECT id, region, effective_from, content, embedding <=> %(q)s::vector AS distance FROM chunks "
           + ("WHERE " + " AND ".join(where) + " " if where else "")
           + "ORDER BY embedding <=> %(q)s::vector LIMIT %(k)s")
    return conn.execute(sql, params).fetchall()


def starve(conn, question, region):
    for mode in ("off", "relaxed_order"):
        conn.execute(f"SET hnsw.iterative_scan = {mode}")
        rows = retrieve(conn, question, region=region, k=5, ef=40)
        print(f"iterative_scan = {mode:<13} LIMIT 5 returned {len(rows)} rows")


def show(rows):
    for cid, region, eff, content, d in rows:
        print(f"  {d:.3f}  chunk {cid}  {region}  effective {eff}  {content[:60]}")


# >>> demo
def build_prompt(question, rows):
    sources = "\n".join(f"[{i}] chunk {cid}: {content}" for i, (cid, _, _, content, _) in enumerate(rows, 1))
    return ("Answer only from the sources below. Cite them as [1], [2].\n"
            "If the sources do not answer the question, say so.\n\n"
            f"{sources}\n\nQuestion: {question}")


def answer(conn, question, region, filters=True):
    conn.execute("SET hnsw.iterative_scan = relaxed_order")
    rows = retrieve(conn, question, region if filters else None, in_effect=filters, k=5)
    if not rows or rows[0][4] > MAX_DISTANCE:
        best = rows[0][4] if rows else None
        print(f"Best distance {best:.3f} is over {MAX_DISTANCE}: the API declines instead of guessing.")
        return None
    prompt = build_prompt(question, rows)
    print(prompt + "\n")
    req = urllib.request.Request(STUB_URL, data=json.dumps({"prompt": prompt}).encode(),
                                 headers={"Content-Type": "application/json"})
    reply = json.loads(urllib.request.urlopen(req, timeout=5).read())
    print(f"{reply['model']}: {reply['answer']}")
    return reply
# <<< demo


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "answer"
    region = arg("--region", "EU")
    default_q = {"offtopic": "what is the capital of France?", "starve": STARVE_QUESTION}.get(cmd, QUESTION)
    question = arg("--q", default_q)
    port = arg("--port", config.get("PG_PORT", "5432"))
    # prepare_threshold=None: no server-side prepared statements, which PgBouncer transaction mode needs
    with psycopg.connect(config.pg_conninfo(port=port), autocommit=True, prepare_threshold=None) as conn:
        print(f"Question ({region} customer): {question}")
        if cmd == "unfiltered":
            show(retrieve(conn, question, region=None, in_effect=False))
        elif cmd == "filtered":
            show(retrieve(conn, question, region=region))
        elif cmd == "nodate":
            show(retrieve(conn, question, region=region, in_effect=False))
        elif cmd == "starve":
            starve(conn, question, region)
        elif cmd in ("answer", "offtopic"):
            answer(conn, question, region)
        elif cmd == "nofilter":
            answer(conn, question, region, filters=False)
        else:
            print(__doc__)
