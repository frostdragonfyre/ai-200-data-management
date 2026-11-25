"""Module 1: a client can relax the account's consistency, never strengthen it.

    python m1/after/consistency.py
The account default is Session (set by setup.sh).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from azure.cosmos import exceptions  # noqa: E402
from tickets import charge, get_tickets  # noqa: E402


def read_with(level):
    label = level or "account default (Session)"
    try:
        t = get_tickets(consistency_level=level)
        t.read_item("t7", partition_key="c7")
        print(f"{label:<28} allowed   {charge(t):.2f} RU")
    except exceptions.CosmosHttpResponseError as e:
        first = str(e.message).splitlines()[0][:110]
        print(f"{label:<28} rejected  status {e.status_code}: {first}")


if __name__ == "__main__":
    for level in ("Eventual", "Strong", None):
        read_with(level)
