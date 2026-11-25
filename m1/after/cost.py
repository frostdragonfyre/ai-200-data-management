"""Module 1: find where Request Units go, then cut them.

    python m1/after/cost.py star        # SELECT * on billing tickets, charge summed across pages
    python m1/after/cost.py project     # same rows, three fields
    python m1/after/cost.py metrics     # index metrics: utilized and potential indexes
    python m1/after/cost.py sessions    # write 5 sessions to the default and narrow containers
    python m1/after/cost.py composite   # add the composite index and watch the transformation
    python m1/after/cost.py policies    # indexing policy of the two session containers
    python m1/after/cost.py narrow      # query sessions_narrow on an indexed and an excluded path
    python m1/after/cost.py point       # point read vs the cheapest query for the same ticket
    python m1/after/cost.py uncomposite # remove the composite index to run the demo again
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from azure.cosmos import PartitionKey  # noqa: E402
from tickets import charge, get_db, get_tickets  # noqa: E402

BILLING = "WHERE c.category = 'billing' ORDER BY c.createdAt DESC"


def run(tickets, query, **kw):
    total, rows = 0.0, []
    for page in tickets.query_items(query, enable_cross_partition_query=True, **kw).by_page():
        rows.extend(page)
        total += charge(tickets)
    return rows, total


def select_star(tickets):
    rows, total = run(tickets, f"SELECT * FROM c {BILLING}")
    first = rows[0]
    print(f"SELECT *: {len(rows)} rows, {total:.2f} RU")
    print(f"First row carries an embedding of {len(first.get('embedding') or [])} numbers the API never uses")


# >>> demo
def projection(tickets):
    rows, total = run(tickets, f"SELECT c.id, c.subject, c.status FROM c {BILLING}")
    print(f"Three fields: {len(rows)} rows, {total:.2f} RU")


def index_metrics(tickets):
    run(tickets, f"SELECT c.id, c.subject, c.status FROM c {BILLING}", populate_index_metrics=True)
    metrics = tickets.client_connection.last_response_headers.get("x-ms-cosmos-index-utilization")
    print(json.dumps(metrics, indent=2) if not isinstance(metrics, str) else metrics)


def write_sessions(n=5):
    db = get_db()
    for name in ("sessions_default", "sessions_narrow"):
        c = db.get_container_client(name)
        charges = []
        for i in range(n):
            now = datetime.now(timezone.utc).isoformat()
            doc = {"id": f"s{int(time.time() * 1000)}-{i}", "customerId": f"c{i + 1}", "ticketId": f"t{i + 1}",
                   "createdAt": now, "updatedAt": now, "channel": "chat", "locale": "en-US",
                   "messages": [{"from": "customer", "text": "Where is my refund?"},
                                {"from": "assistant", "text": "Refunds post to the original payment method within 5 to 10 business days."},
                                {"from": "customer", "text": "It has been 12 days."},
                                {"from": "assistant", "text": "I have sent the bank reference number to your email."}],
                   "summary": "Refund status question; reference number sent.",
                   "sources": [{"chunk": 1171, "distance": 0.21}, {"chunk": 1172, "distance": 0.27}]}
            c.create_item(doc)
            charges.append(float(c.client_connection.last_response_headers["x-ms-request-charge"]))
        print(f"{name:<17} " + "  ".join(f"{x:.2f}" for x in charges) + " RU per write")


def add_composite(tickets):
    props = tickets.read()
    policy = props["indexingPolicy"]
    policy["compositeIndexes"] = [[{"path": "/category", "order": "ascending"},
                                   {"path": "/createdAt", "order": "ascending"}]]
    db = get_db()
    db.replace_container(tickets, partition_key=PartitionKey(path="/customerId"), indexing_policy=policy,
                         vector_embedding_policy=props.get("vectorEmbeddingPolicy"))
    while True:
        tickets.read(populate_quota_info=True)
        progress = tickets.client_connection.last_response_headers.get(
            "x-ms-documentdb-collection-index-transformation-progress")
        print(f"Index transformation: {progress}%")
        if progress in (None, "100", "-1"):
            break
        time.sleep(2)


def remove_composite(tickets):
    props = tickets.read()
    policy = props["indexingPolicy"]
    policy["compositeIndexes"] = []
    get_db().replace_container(tickets, partition_key=PartitionKey(path="/customerId"), indexing_policy=policy,
                               vector_embedding_policy=props.get("vectorEmbeddingPolicy"))
    print("Composite index removed")


def policies():
    db = get_db()
    for name in ("sessions_default", "sessions_narrow"):
        p = db.get_container_client(name).read()["indexingPolicy"]
        inc = [x["path"] for x in p.get("includedPaths", [])]
        exc = [x["path"] for x in p.get("excludedPaths", []) if x["path"] != '/"_etag"/?']
        print(f"{name:<17} included {inc}  excluded {exc}")


def narrow_queries():
    c = get_db().get_container_client("sessions_narrow")
    for label, q in (("updatedAt (indexed) ", "SELECT VALUE COUNT(1) FROM c WHERE c.updatedAt > '2000-01-01'"),
                     ("channel (not indexed)", "SELECT VALUE COUNT(1) FROM c WHERE c.channel = 'chat'")):
        rows, total = run(c, q)
        print(f"Filter on {label}: {rows[0] if rows else 0} sessions, {total:.2f} RU")


def point_vs_query(tickets):
    tickets.read_item("t7", partition_key="c7")
    print(f"Point read t7:                     {charge(tickets):.2f} RU")
    list(tickets.query_items("SELECT * FROM c WHERE c.id = 't7'", partition_key="c7"))
    print(f"Query for t7, partition key given: {charge(tickets):.2f} RU")
    rows, total = run(tickets, "SELECT * FROM c WHERE c.id = 't7'")
    print(f"Query for t7, no partition key:    {total:.2f} RU")
# <<< demo


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "star"
    t = get_tickets()
    {"star": lambda: select_star(t), "project": lambda: projection(t), "metrics": lambda: index_metrics(t),
     "sessions": write_sessions, "composite": lambda: add_composite(t), "policies": policies,
     "narrow": narrow_queries, "point": lambda: point_vs_query(t),
     "uncomposite": lambda: remove_composite(t)}.get(cmd, lambda: print(__doc__))()
