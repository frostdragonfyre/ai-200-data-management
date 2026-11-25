"""Module 2: resolve tickets so the change feed processor has work to do.

    python m2/after/resolve.py t12 t13 t14     # resolve three tickets
    python m2/after/resolve.py t12             # resolve one again: its event is replaced, not duplicated
    python m2/after/resolve.py --events        # list documents in the events container
    python m2/after/resolve.py --leases        # list the processor's lease documents
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "m1" / "after"))
from tickets import get_db  # noqa: E402


def resolve(ids):
    tickets = get_db().get_container_client("tickets")
    for tid in ids:
        item = next(iter(tickets.query_items("SELECT * FROM c WHERE c.id = @id",
                                             parameters=[{"name": "@id", "value": tid}],
                                             enable_cross_partition_query=True)))
        item["status"] = "resolved"
        item["resolution"] = item.get("resolution") or "Resolved by an agent during the demo."
        item["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        tickets.replace_item(item["id"], item)
        print(f"Resolved {tid} at {item['updatedAt']}")


def list_events():
    events = get_db().get_container_client("events")
    rows = list(events.query_items("SELECT c.id, c.ticketId, c.updatedAt, c._ts FROM c ORDER BY c._ts DESC",
                                   enable_cross_partition_query=True))
    for r in rows:
        print(f"  {r['id']:<10} ticket {r['ticketId']:<6} processed {r['updatedAt']}")
    print(f"{len(rows)} event documents")


def list_leases():
    leases = get_db().get_container_client("leases")
    rows = list(leases.query_items("SELECT * FROM c", enable_cross_partition_query=True))
    for r in rows:
        owner = r.get("Owner") or r.get("owner")
        kind = "store metadata" if r["id"].endswith(".info") else \
            f"lease for range {r['id'].rsplit('.', 1)[-1]}, owner {owner[:8] + '...' if owner else 'none (host idle)'}"
        print(f"  {r['id'][-24:]:<26} {kind}")
    print(f"{len(rows)} lease documents")


if __name__ == "__main__":
    if "--leases" in sys.argv:
        list_leases()
    elif "--events" in sys.argv:
        list_events()
    else:
        resolve(sys.argv[1:] or ["t12", "t13", "t14"])
