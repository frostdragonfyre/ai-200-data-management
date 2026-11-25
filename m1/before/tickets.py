"""Module 1: connect to the ticket store and read the bill on every call.

    python m1/after/tickets.py load       # load data/tickets.json (500 tickets)
    python m1/after/tickets.py read       # point read of t7 in partition c7
    python m1/after/tickets.py wrongpk    # same id, wrong partition key
    python m1/after/tickets.py open c7    # open tickets for one customer
    python m1/after/tickets.py billing    # billing tickets across partitions, newest first
    python m1/after/tickets.py page       # page billing tickets 20 at a time, save the token
    python m1/after/tickets.py next       # resume from the saved token: page 2
    python m1/after/tickets.py mine c7    # billing tickets for one customer, partition key given
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from azure.cosmos import CosmosClient, exceptions  # noqa: E402
from common import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = Path(__file__).resolve().parent / ".page_token"


def get_db(consistency_level=None):
    """One client per process, reused. The demos use the account key from .env;
    in production pass azure.identity.DefaultAzureCredential() instead of the key."""
    client = CosmosClient(config.get("COSMOS_ENDPOINT"), credential=config.get("COSMOS_KEY"),
                          consistency_level=consistency_level)
    return client.get_database_client("support")


def get_tickets(consistency_level=None):
    return get_db(consistency_level).get_container_client("tickets")


def charge(container):
    """Every response carries its price in the x-ms-request-charge header."""
    return float(container.client_connection.last_response_headers["x-ms-request-charge"])


def load_tickets(tickets):
    items = json.loads((ROOT / "data/tickets.json").read_text())
    total = 0.0
    for item in items:
        tickets.upsert_item(item)
        total += charge(tickets)
    print(f"Loaded {len(items)} tickets, {total:.0f} RU in total")


def point_read(tickets, ticket_id="t7", customer_id="c7"):
    item = tickets.read_item(item=ticket_id, partition_key=customer_id)
    print(f"{item['id']} | {item['customerId']} | {item['status']} | {item['subject']}")
    print(f"Request charge: {charge(tickets):.2f} RU")
    return item


def open_tickets(tickets, customer_id="c7"):
    """Query scoped to one partition: parameterized, never string concatenation."""
    raise NotImplementedError("You add this in the demo")


def billing_by_date(tickets):
    """No partition key: the query asks every partition, then the results merge."""
    raise NotImplementedError("You add this in the demo")


def page_billing(tickets, size=20):
    raise NotImplementedError("You add this in the demo")


def next_page(tickets, size=20):
    raise NotImplementedError("You add this in the demo")


def billing_for(tickets, customer_id="c7"):
    """The same billing query, scoped to one customer's partition."""
    raise NotImplementedError("You add this in the demo")



if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "read"
    t = get_tickets()
    if cmd == "load":
        load_tickets(t)
    elif cmd == "read":
        point_read(t)
    elif cmd == "wrongpk":
        try:
            point_read(t, "t7", "c8")
        except exceptions.CosmosResourceNotFoundError as e:
            print(f"CosmosResourceNotFoundError: status {e.status_code}. The partition key is part of the address.")
    elif cmd == "open":
        open_tickets(t, sys.argv[2] if len(sys.argv) > 2 else "c7")
    elif cmd == "billing":
        billing_by_date(t)
    elif cmd == "page":
        page_billing(t)
    elif cmd == "next":
        next_page(t)
    elif cmd == "mine":
        billing_for(t, sys.argv[2] if len(sys.argv) > 2 else "c7")
    else:
        print(__doc__)
