"""Module 2: a change feed processor hosted by Azure Functions.

The Cosmos DB trigger is the change feed processor: it reads the tickets
container's change feed, keeps one lease per partition range in the leases
container, and checkpoints after this function returns. The output binding
upserts into the events container, so a redelivered batch replaces the same
event instead of adding a duplicate.
"""
import json
import logging
from datetime import datetime, timezone

import azure.functions as func

app = func.FunctionApp()


@app.cosmos_db_trigger(arg_name="docs", database_name="support", container_name="tickets",
                       connection="COSMOS", lease_container_name="leases",
                       create_lease_container_if_not_exists=True)
@app.cosmos_db_output(arg_name="out", database_name="support", container_name="events",
                      connection="COSMOS")
def on_change(docs: func.DocumentList, out: func.Out[func.DocumentList]) -> None:
    events = func.DocumentList()
    for doc in docs:
        if doc.get("type") != "ticket" or doc.get("status") != "resolved":
            continue
        events.append(func.Document.from_dict({
            "id": f"evt-{doc['id']}",          # predictable id: a retry overwrites, never duplicates
            "ticketId": doc["id"],             # partition key of the events container
            "customerId": doc.get("customerId"),
            "category": doc.get("category"),
            "kind": "ticket-resolved",
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }))
    if events:
        out.set(events)
    logging.info("Processed %d changes, wrote %d events", len(docs), len(events))


@app.route(route="ping", auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    """Wakes the host after deployment so the trigger starts listening."""
    return func.HttpResponse(json.dumps({"status": "awake"}), mimetype="application/json")
