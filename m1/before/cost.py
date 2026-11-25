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


def projection(tickets):
    raise NotImplementedError("You add this in the demo")


def index_metrics(tickets):
    raise NotImplementedError("You add this in the demo")


def write_sessions(n=5):
    raise NotImplementedError("You add this in the demo")


def add_composite(tickets):
    raise NotImplementedError("You add this in the demo")


def remove_composite(tickets):
    raise NotImplementedError("You add this in the demo")


def policies():
    raise NotImplementedError("You add this in the demo")


def narrow_queries():
    raise NotImplementedError("You add this in the demo")


def point_vs_query(tickets):
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "star"
    t = get_tickets()
    {"star": lambda: select_star(t), "project": lambda: projection(t), "metrics": lambda: index_metrics(t),
     "sessions": write_sessions, "composite": lambda: add_composite(t), "policies": policies,
     "narrow": narrow_queries, "point": lambda: point_vs_query(t),
     "uncomposite": lambda: remove_composite(t)}.get(cmd, lambda: print(__doc__))()
