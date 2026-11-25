"""Offline check of the retrieval numbers the demos rely on.

Runs entirely on your machine with the same model and the seed files, no Azure needed:
    python tools/check_retrieval.py

Prints the ticket similarity ranking, the RAG seed-question ranking with and
without filters, the decline-threshold distances, and the semantic-cache
distances. Cosine distance here is 1 - cosine similarity, the same value
Cosmos DB, pgvector (<=>), and Redis (COSINE) report.
"""
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[1]
model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")


def emb(text):
    return np.array(list(model.embed([text]))[0], dtype=np.float32)


def dist(a, b):
    return float(1 - a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def tickets_check():
    tickets = json.loads((ROOT / "data/tickets.json").read_text())
    for q in ["my blender arrived cracked", "how do I reset my password"]:
        qv = emb(q)
        scored = sorted(((dist(qv, np.array(t["embedding"])), t) for t in tickets), key=lambda x: x[0])
        print(f"\nTickets, query: {q!r}")
        for d, t in scored[:5]:
            print(f"  {d:.3f}  {t['id']:>5}  {t['category']:<8} {t['status']:<8} {t['subject']}")
        rr = [(d, t) for d, t in scored if t["category"] == "returns" and t["status"] == "resolved"]
        print(f"  filtered returns+resolved top: {rr[0][0]:.3f} {rr[0][1]['subject']}")


def chunks_check():
    rows = list(csv.DictReader(open(ROOT / "data/chunks.csv", encoding="utf-8")))
    for r in rows:
        r["v"] = np.array(json.loads(r["embedding"]), dtype=np.float32)
    today = date.today().isoformat()

    def in_effect(r):
        return r["effective_from"] <= today and (not r["effective_to"] or r["effective_to"] >= today)

    seeds = [
        ("I changed my mind about an order, can I return it?", "EU", "1042"),
        ("I changed my mind about an order, can I return it?", "US", None),
        ("When will my refund show up?", "EU", "1043"),
        ("My item came broken, what do I do?", "US", None),
        ("How do I turn on two-step verification?", "US", None),
    ]
    for q, region, expect in seeds:
        qv = emb(q)
        allr = sorted(((dist(qv, r["v"]), r) for r in rows), key=lambda x: x[0])
        filt = [(d, r) for d, r in allr if r["region"] == region and in_effect(r)]
        nodate = [(d, r) for d, r in allr if r["region"] == region]
        print(f"\nRAG, {region}: {q!r}" + (f" (expect {expect})" if expect else ""))
        print("  unfiltered top 3: " + "; ".join(f"{r['id']} {r['region']} {d:.3f}" for d, r in allr[:3]))
        print("  region+date top 3: " + "; ".join(f"{r['id']} {d:.3f} {r['content'][:48]!r}" for d, r in filt[:3]))
        print("  region only top 3: " + "; ".join(f"{r['id']} eff {r['effective_from']} {d:.3f}" for d, r in nodate[:3]))
    for q in ["what is the capital of France?", "how do I bake sourdough bread?"]:
        qv = emb(q)
        best = min(dist(qv, r["v"]) for r in rows if r["region"] == "EU" and in_effect(r))
        print(f"\nDecline check {q!r}: best EU distance {best:.3f}")


def semcache_check():
    stored = {"How do I return a damaged item?": emb("How do I return a damaged item?"),
              "Where is my refund?": emb("Where is my refund?")}
    print("\nSemantic cache distances")
    for q in ["can I send back a broken item?", "my refund still has not shown up",
              "how do I turn on two-step verification?"]:
        qv = emb(q)
        best = min((dist(qv, v), k) for k, v in stored.items())
        print(f"  {best[0]:.3f}  {q!r} -> nearest {best[1]!r}")


def semcache_candidates():
    print("\nCandidate stored questions for the refund paraphrase")
    para = emb("my refund still has not shown up")
    two = emb("how do I turn on two-step verification?")
    for c in ["Where is my refund?", "When will I get my money back?", "How long do refunds take?",
              "Has my refund been processed?", "When will my refund arrive?", "How long until a refund reaches my card?",
              "When does a refund post to my account?"]:
        v = emb(c)
        print(f"  {dist(para, v):.3f}  paraphrase vs {c!r}   (two-step vs it: {dist(two, v):.3f})")


if __name__ == "__main__":
    tickets_check()
    chunks_check()
    semcache_check()
    semcache_candidates()
