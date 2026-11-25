"""Create the Cosmos DB containers and load the tickets. Called by setup.sh.

    python tools/setup_cosmos.py            # containers plus 500 tickets
    python tools/setup_cosmos.py --empty    # containers only (the loading demo fills them)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from azure.cosmos import CosmosClient, PartitionKey  # noqa: E402
from common import config  # noqa: E402

VECTOR_POLICY = {"vectorEmbeddings": [{"path": "/embedding", "dataType": "float32",
                                       "distanceFunction": "cosine", "dimensions": 384}]}
TICKETS_INDEXING = {"indexingMode": "consistent", "automatic": True,
                    "includedPaths": [{"path": "/*"}],
                    "excludedPaths": [{"path": "/embedding/*"}, {"path": "/\"_etag\"/?"}],
                    "vectorIndexes": [{"path": "/embedding", "type": "diskANN"}]}
NARROW_INDEXING = {"indexingMode": "consistent", "automatic": True,
                   "includedPaths": [{"path": "/updatedAt/?"}],
                   "excludedPaths": [{"path": "/*"}]}


def main(empty=False):
    client = CosmosClient(config.get("COSMOS_ENDPOINT"), credential=config.get("COSMOS_KEY"))
    db = client.create_database_if_not_exists("support")
    tickets = db.create_container_if_not_exists("tickets", PartitionKey(path="/customerId"),
                                                indexing_policy=TICKETS_INDEXING,
                                                vector_embedding_policy=VECTOR_POLICY)
    db.create_container_if_not_exists("sessions_default", PartitionKey(path="/customerId"))
    db.create_container_if_not_exists("sessions_narrow", PartitionKey(path="/customerId"),
                                      indexing_policy=NARROW_INDEXING)
    db.create_container_if_not_exists("events", PartitionKey(path="/ticketId"))
    db.create_container_if_not_exists("leases", PartitionKey(path="/id"))
    print("Containers: tickets (vector policy, diskANN), sessions_default, sessions_narrow, events, leases")
    if empty:
        return
    items = json.loads((ROOT / "data/tickets.json").read_text())
    if "embedding" not in items[0]:
        sys.exit("data/tickets.json has no embeddings. Run: python tools/make_seed.py --embed")
    for item in items:
        tickets.upsert_item(item)
    print(f"Loaded {len(items)} tickets")


if __name__ == "__main__":
    main(empty="--empty" in sys.argv)
