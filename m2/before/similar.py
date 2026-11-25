"""Module 2: find similar resolved tickets by meaning.

    python m2/after/similar.py "my blender arrived cracked"
    python m2/after/similar.py "my blender arrived cracked" --filter
    python m2/after/similar.py "how do I reset my password"
    python m2/after/similar.py cracked --keyword                 # word match on the subject, no vectors
    python m2/after/similar.py "my blender arrived cracked" --top 10
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "m1" / "after"))
from common.embed import MODEL_TAG, timed_embed  # noqa: E402
from tickets import charge, get_tickets  # noqa: E402


def similar(tickets, text, top=5, filtered=False):
    vector, ms = timed_embed(text)
    print(f"Embedded {text!r}: {len(vector)} numbers in {ms:.0f} ms")
    where = "WHERE c.embeddingModel = @model"
    # TODO: you add this in the demo
    query = (f"SELECT TOP {top} c.id, c.subject, c.category, c.status, c.resolution, "
             f"VectorDistance(c.embedding, @q) AS score FROM c {where} "
             "ORDER BY VectorDistance(c.embedding, @q)")
    params = [{"name": "@q", "value": vector}, {"name": "@model", "value": MODEL_TAG}]
    rows, total = [], 0.0
    for page in tickets.query_items(query, parameters=params, enable_cross_partition_query=True).by_page():
        rows.extend(page)
        total += charge(tickets)
    for r in rows:
        print(f"  {r['score']:.3f}  {r['id']:>5}  {r['category']:<8} {r['status']:<8} {r['subject']}")
    print(f"Request charge: {total:.2f} RU")
    print("Score is cosine similarity: higher means closer in meaning.")
    return rows


def keyword(tickets, word):
    """What search looked like before embeddings: the word has to be in the text."""
    query = ("SELECT c.id, c.subject, c.category, c.status FROM c "
             "WHERE CONTAINS(c.subject, @w, true) OR CONTAINS(c.body, @w, true)")
    rows, total = [], 0.0
    for page in tickets.query_items(query, parameters=[{"name": "@w", "value": word}],
                                    enable_cross_partition_query=True).by_page():
        rows.extend(page)
        total += charge(tickets)
    for r in rows:
        print(f"  {r['id']:>5}  {r['category']:<8} {r['status']:<8} {r['subject']}")
    print(f"{len(rows)} tickets contain the word {word!r}, request charge: {total:.2f} RU")


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "my blender arrived cracked"
    if "--keyword" in sys.argv:
        keyword(get_tickets(), text)
        sys.exit()
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
    rows = similar(get_tickets(), text, top=top, filtered="--filter" in sys.argv)
    if rows and rows[0].get("resolution"):
        print(f"\nHow the closest match was resolved: {rows[0]['resolution']}")
