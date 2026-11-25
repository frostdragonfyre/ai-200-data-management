"""Module 2: the change feed pull model. Your code asks for pages and keeps the token.

    python m2/after/pull.py start          # read from the beginning, save the token
    python m2/after/pull.py touch t7       # change one ticket
    python m2/after/pull.py next           # read only what changed since the saved token
    python m2/after/pull.py token          # show the saved token
    python m2/after/pull.py ghost          # create, then delete, a scratch ticket
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "m1" / "after"))
from tickets import get_tickets  # noqa: E402

TOKEN_FILE = Path(__file__).resolve().parent / ".changefeed_token"


def read_feed(tickets, continuation=None):
    if continuation:
        feed = tickets.query_items_change_feed(continuation=continuation)
    else:
        feed = tickets.query_items_change_feed(start_time="Beginning")
    pages = feed.by_page()
    ids = []
    for page in pages:
        ids.extend(item["id"] for item in page)
    # With no new changes the service can return no fresh token; keep the one we had.
    token = pages.continuation_token or continuation
    if token:
        TOKEN_FILE.write_text(token)
    return ids, token


def touch(tickets, ticket_id="t7"):
    item = next(iter(tickets.query_items("SELECT * FROM c WHERE c.id = @id",
                                         parameters=[{"name": "@id", "value": ticket_id}],
                                         enable_cross_partition_query=True)))
    item["status"] = "pending-customer" if item["status"] != "pending-customer" else "open"
    item["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    tickets.replace_item(item["id"], item)
    print(f"Updated {item['id']}: status is now {item['status']}")


def ghost(tickets):
    """Latest version mode has no delete events: an item created and deleted between reads leaves no trace."""
    item = {"id": "scratch-1", "customerId": "c99", "type": "scratch", "status": "open"}
    tickets.upsert_item(item)
    tickets.delete_item("scratch-1", partition_key="c99")
    print("Created and deleted scratch-1")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    t = get_tickets()
    if cmd == "start":
        ids, token = read_feed(t)
        print(f"Read {len(ids)} items from the beginning. Token saved.")
    elif cmd == "touch":
        touch(t, sys.argv[2] if len(sys.argv) > 2 else "t7")
    elif cmd == "next":
        ids, token = read_feed(t, TOKEN_FILE.read_text())
        print(f"{len(ids)} changed since the saved token: {ids}")
    elif cmd == "ghost":
        ghost(t)
    elif cmd == "token":
        token = TOKEN_FILE.read_text()
        print(f"{len(token)} characters: {token[:120]}...")
    else:
        print(__doc__)
