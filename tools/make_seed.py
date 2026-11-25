"""Regenerate the seed data for the support answer API.

    python tools/make_seed.py            # text only (fast, no model needed)
    python tools/make_seed.py --embed    # text plus 384-dimension embeddings

Writes:
    data/tickets.json      500 support tickets, 50 customers, 4 categories
    data/kb_articles.json  knowledge base articles (US and EU policy variants plus synthetic filler)
    data/chunks.csv        5,000 chunks; real policy text plus filler rows tagged synthetic

Every embedding comes from the same local model the demos use
(sentence-transformers/all-MiniLM-L6-v2 through fastembed), so stored vectors
and question vectors always share one embedding space.
"""
import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
rng = random.Random(200)

# ---------------------------------------------------------------- tickets
CATEGORY_COUNTS = {"billing": 126, "returns": 132, "shipping": 127, "account": 115}

PRODUCTS = ["toaster", "kettle", "coffee maker", "air fryer", "stand mixer", "rice cooker", "juicer", "waffle maker"]
TEMPLATES = {
    "billing": [
        ("Charged twice for order {o}", "My card statement shows two charges for order {o}. I only placed it once."),
        ("Refund not received for order {o}", "The refund for order {o} was approved and I still do not see it on my card."),
        ("Promo code ignored on the {p}", "I entered the code SAVE15 at checkout for the {p} in order {o} but paid full price."),
        ("Invoice total looks wrong", "The invoice for order {o} includes a shipping fee, but shipping was supposed to be free."),
        ("Card declined but money taken", "Checkout said my card was declined, yet my bank shows a pending charge for order {o}."),
        ("Need an itemized invoice", "Please send an itemized invoice for order {o}. I need it for an expense report."),
        ("Care plan renewed without notice", "The care plan on my {p} renewed automatically and I was charged. I wanted to cancel it."),
        ("Tax charged twice", "Order {o} shows sales tax on the {p} and again on the order total."),
    ],
    "returns": [
        ("Damaged item on delivery", "The box was crushed and the {p} inside was broken when I opened it. Order {o}."),
        ("{P} dented when I opened the box", "The {p} from order {o} has a deep dent on the side and the lid will not close."),
        ("Glass carafe shattered in shipping", "The glass carafe for the {p} in order {o} was in pieces inside the packaging."),
        ("Box crushed, {p} broken inside", "The carrier left a crushed box. The {p} housing is split and it will not power on. Order {o}."),
        ("Wrong size, want an exchange", "I ordered the large {p} but need the small one. Order {o}."),
        ("Return label will not print", "The prepaid return label link for order {o} shows an error page."),
        ("Changed my mind about the {p}", "I no longer need the {p} from order {o}. It is unopened. How do I send it back?"),
        ("Missing parts in the box", "The {p} from order {o} came without the accessory kit."),
    ],
    "shipping": [
        ("Package delayed", "Order {o} was due on Monday and tracking has not moved in four days."),
        ("Tracking number not working", "The tracking number for order {o} says it does not exist."),
        ("Delivered to the wrong address", "Tracking says order {o} was delivered, but it went to a different street."),
        ("Can I change my delivery address?", "I moved last week. Can order {o} go to my new address?"),
        ("Need faster shipping for a gift", "Can the {p} in order {o} be upgraded to two-day shipping? It is a gift."),
        ("Partial delivery only", "Only one of the two items in order {o} showed up. The {p} is missing."),
        ("Signature required but nobody home", "The carrier wants a signature for order {o}. Can it be left at the door?"),
    ],
    "account": [
        ("Reset my password", "I forgot my password and the reset email never shows up in my inbox."),
        ("Cannot sign in", "The site says my password is wrong even after I changed it."),
        ("Two-step verification code not arriving", "I turned on two-step verification and now the text message code never comes."),
        ("Change the email on my account", "I want to move my account to a new email address."),
        ("Close my account", "Please close my account and remove my saved addresses."),
        ("Saved card keeps disappearing", "Every time I sign in, my saved payment card is gone."),
        ("Locked out after a phone change", "I got a new phone and my authenticator app codes no longer work."),
    ],
}
DETAILS = ["I need this sorted before the weekend.", "This is the second time this has happened.",
           "I have attached a photo.", "Please reply by email.", "I have been a customer for years.",
           "The order was a gift.", "I already tried the help center.", "My order number is above.",
           "", "", ""]

RESOLUTIONS = {
    "billing": ["Reversed the duplicate charge; customer sees the credit in 3 to 5 business days.",
                "Confirmed the refund posted to the original card; shared the bank reference number.",
                "Applied the promo as a partial refund to the original payment method."],
    "returns": ["Sent a replacement at no charge and a prepaid label for the damaged unit.",
                "Issued a full refund; no need to return the damaged item.",
                "Emailed a new return label; refund issues when the carrier scans the package."],
    "shipping": ["Carrier confirmed a delay; shipment arrived two days later.",
                 "Opened a carrier trace; reshipped the order with tracking.",
                 "Updated the delivery address before the package left the warehouse."],
    "account": ["Sent a password reset link to the verified email; customer signed in.",
                "Reset two-step verification after identity check; customer re-enrolled.",
                "Updated the account email after confirming both addresses."],
}

AGENT_LINES = ["Thanks for reaching out. I am looking into this now.",
               "I have the order details in front of me.",
               "Could you confirm the email address on the order?",
               "I have escalated this to the team that handles it."]


def make_tickets():
    cats = [c for c, n in CATEGORY_COUNTS.items() for _ in range(n)]
    rng.shuffle(cats)
    # Pin t7 so the point-read demo has a known item.
    i7 = cats.index("billing")
    cats[6], cats[i7] = cats[i7], cats[6]
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    tickets = []
    for i, cat in enumerate(cats, start=1):
        subject, body = rng.choice(TEMPLATES[cat])
        order = f"A{100000 + i * 37 % 90000}"
        p = rng.choice(PRODUCTS)
        subject = subject.replace("{P}", p.capitalize()).replace("{p}", p)
        body = (body.replace("{p}", p) + " " + rng.choice(DETAILS)).strip()
        created = start + timedelta(minutes=rng.randint(0, 150 * 24 * 60))
        status = "resolved" if rng.random() < 0.6 else "open"
        if i == 7:
            subject, body, status = "Refund not received for order A100259", "The refund for order A100259 was approved last week and I still do not see it on my card.", "open"
        msgs = [{"from": "customer", "text": body.format(o=order)}]
        for _ in range(rng.randint(1, 3)):
            msgs.append({"from": "agent", "text": rng.choice(AGENT_LINES)})
        t = {
            "id": f"t{i}",
            "customerId": f"c{(i - 1) % 50 + 1}",
            "type": "ticket",
            "category": cat,
            "subject": subject.format(o=order),
            "body": body.format(o=order),
            "status": status,
            "priority": rng.choice(["low", "normal", "normal", "high"]),
            "orderId": order,
            "createdAt": created.isoformat().replace("+00:00", "Z"),
            "updatedAt": (created + timedelta(hours=rng.randint(1, 72))).isoformat().replace("+00:00", "Z"),
            "messages": msgs,
            "resolution": rng.choice(RESOLUTIONS[cat]) if status == "resolved" else None,
        }
        tickets.append(t)
    # Guarantee resolved damaged-delivery tickets for the similarity demo.
    damaged = [t for t in tickets if t["category"] == "returns" and t["subject"] in
               ("Damaged item on delivery",) or "dented when" in t["subject"] or "shattered" in t["subject"] or "broken inside" in t["subject"]]
    for t in damaged[:12]:
        t["status"] = "resolved"
        t["resolution"] = RESOLUTIONS["returns"][0]
    return tickets


# ---------------------------------------------------------------- knowledge base
# (article id, title, product, region, effective_from, effective_to, version, [chunks])
CURRENT, PREVIOUS_FROM, PREVIOUS_TO = "2026-01-01", "2025-01-01", "2025-12-31"
ARTICLES = [
    (42, "Returns and right of withdrawal (EU)", "all", "EU", CURRENT, None, 3, [
        "EU customers may return any item within 14 days of delivery for any reason. This is your right of withdrawal, and you do not need to give a reason.",
        "Refunds for EU returns post to the original payment method within 14 days of the day we receive your withdrawal notice.",
        "To withdraw from a purchase, open Orders, choose the item, and select Return. We email a prepaid label within one business day.",
    ]),
    (41, "Returns and right of withdrawal (EU), 2025 edition", "all", "EU", PREVIOUS_FROM, PREVIOUS_TO, 2, [
        "EU customers could return items within 14 days of delivery. Return shipping was paid by the customer unless the item was faulty.",
        "Refunds for EU returns in 2025 were issued as store credit unless the customer asked for a card refund.",
    ]),
    (40, "Return policy (US)", "all", "US", CURRENT, None, 3, [
        "US customers can return most items within 30 days of delivery for a full refund. Items must be unused and in the original packaging.",
        "Refunds for US returns post to the original payment method within 5 to 10 business days after the carrier scans your package.",
        "Start a US return from Orders. Select the item, choose a reason, and print the prepaid label.",
    ]),
    (39, "Return policy (US), 2025 edition", "all", "US", PREVIOUS_FROM, PREVIOUS_TO, 2, [
        "In 2025, US customers could return most items within 45 days of delivery for a full refund.",
        "A restocking fee of 10 percent applied to opened small appliances returned after 15 days in 2025.",
    ]),
    (43, "Damaged or defective on arrival (US)", "all", "US", CURRENT, None, 3, [
        "If an item is broken or damaged when it reaches you, contact support within 7 days. We send a replacement or a full refund, and you do not need to return the damaged item.",
        "Take a photo of the damaged item and the packaging before you throw anything away. Support may ask for it.",
        "Damaged deliveries are never charged return shipping and never count against your return window.",
    ]),
    (44, "Damaged or defective on arrival (EU)", "all", "EU", CURRENT, None, 2, [
        "EU customers who receive a damaged or faulty item are entitled to a repair, replacement, or refund under the legal guarantee.",
        "Report damage within 14 days and keep the packaging. We collect the item at no cost to you.",
    ]),
    (45, "Blender warranty (US)", "blender", "US", CURRENT, None, 1, [
        "Every blender sold in the US carries a 2-year limited warranty covering the motor base. Jars and blades are covered for 1 year.",
        "Warranty claims need the order number and a short video of the fault. We ship a replacement part or unit.",
    ]),
    (46, "Blender warranty (EU)", "blender", "EU", CURRENT, None, 1, [
        "Blenders sold in the EU carry the 2-year legal guarantee plus a 1-year extended warranty on the motor base.",
    ]),
    (47, "Refund timing (US)", "all", "US", CURRENT, None, 1, [
        "Most US refunds appear in 5 to 10 business days. Bank processing can add 2 to 3 days after we issue the refund.",
        "If a refund has not appeared after 10 business days, contact support with the order number and we will send the bank reference number.",
    ]),
    (48, "Shipping times and tracking (US)", "all", "US", CURRENT, None, 1, [
        "Standard US shipping takes 3 to 5 business days. Two-day shipping is available at checkout for most items.",
        "Tracking updates can lag by 24 hours after a package leaves the warehouse.",
    ]),
    (49, "Shipping times and tracking (EU)", "all", "EU", CURRENT, None, 1, [
        "Standard EU shipping takes 4 to 7 business days. Customs fees are included in the price at checkout.",
    ]),
    (50, "Account security and two-step verification", "all", "US", CURRENT, None, 2, [
        "Turn on two-step verification from Account, Security. Choose an authenticator app or text message codes.",
        "If verification codes stop arriving, use a backup code or contact support to reset two-step verification after an identity check.",
        "To reset your password, select Forgot password on the sign-in page. The reset link expires after 30 minutes.",
    ]),
    (51, "Kettle care and descaling", "kettle", "US", CURRENT, None, 1, [
        "Descale your kettle every month with equal parts water and white vinegar. Rinse twice before the next use.",
    ]),
    (52, "Air fryer basket sizes", "air fryer", "US", CURRENT, None, 1, [
        "Air fryer baskets come in small (3 quarts) and large (6 quarts). Baskets are not interchangeable between models.",
    ]),
]

FILLER_PRODUCTS = ["toaster", "coffee maker", "air fryer", "kettle", "stand mixer", "rice cooker", "juicer",
                   "food processor", "slow cooker", "waffle maker", "espresso machine", "hand blender"]
FILLER_TOPICS = [
    "Model {m} {p} specifications: {w} watts, {c} cup capacity, {f} foot cord, weight {k} pounds.",
    "Cleaning the {p} model {m}: unplug, let it cool, wipe the housing with a damp cloth, and wash removable parts by hand.",
    "The {p} model {m} ships with a quick start card, {n} accessories, and a recipe booklet with {r} recipes.",
    "Troubleshooting the {p} model {m}: if the power light blinks {n} times, reset by unplugging for {r} seconds.",
    "The {p} model {m} is compatible with accessory kit {a}. Kit {a} adds {n} attachments and a storage case.",
    "Energy use for the {p} model {m}: about {k} kWh per year with daily use, standby draw under 0.5 watts.",
]
FILLER_REGIONS = ["US"] * 64 + ["EU"] * 6 + ["UK"] * 12 + ["CA"] * 10 + ["AU"] * 8


def make_kb(total_chunks=5000):
    articles, chunks = [], []
    used = set()
    seq = 1001
    for aid, title, product, region, eff_from, eff_to, version, texts in ARTICLES:
        articles.append({"id": aid, "title": title, "product": product, "region": region,
                         "effective_from": eff_from, "effective_to": eff_to,
                         "meta": {"version": version, "source": "policy", "synthetic": False}})
        for n, text in enumerate(texts, start=1):
            if aid == 42:
                cid = 1041 + n            # fixed ids 1042, 1043, 1044
            else:
                while seq in used or 1042 <= seq <= 1044:
                    seq += 1
                cid = seq
                seq += 1
            used.add(cid)
            chunks.append({"id": cid, "article_id": aid, "chunk_no": n, "content": text,
                           "product": product, "region": region,
                           "effective_from": eff_from, "effective_to": eff_to,
                           "meta": {"version": version, "source": "policy", "synthetic": False}})
    aid, cid = 1000, 2001
    while len(chunks) < total_chunks:
        aid += 1
        product = rng.choice(FILLER_PRODUCTS)
        region = rng.choice(FILLER_REGIONS)
        model = f"{rng.choice('KLMPRSTX')}-{rng.randint(10, 99)}"
        articles.append({"id": aid, "title": f"{product.title()} model {model} reference", "product": product,
                         "region": region, "effective_from": "2024-01-01", "effective_to": None,
                         "meta": {"version": 1, "source": "manual", "synthetic": True}})
        for n in range(1, 11):
            if len(chunks) >= total_chunks:
                break
            text = rng.choice(FILLER_TOPICS).format(
                m=model, p=product, w=rng.randint(600, 1800), c=rng.randint(2, 12), f=rng.randint(2, 6),
                k=rng.randint(3, 40), n=rng.randint(2, 6), r=rng.randint(10, 60), a=f"AK-{rng.randint(100, 999)}")
            chunks.append({"id": cid, "article_id": aid, "chunk_no": n, "content": text, "product": product,
                           "region": region, "effective_from": "2024-01-01", "effective_to": None,
                           "meta": {"version": 1, "source": "manual", "synthetic": True}})
            cid += 1
    return articles, chunks


def embed_all(texts):
    from fastembed import TextEmbedding
    model = TextEmbedding(MODEL)
    return [[round(float(x), 6) for x in v] for v in model.embed(texts, batch_size=128)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true", help="compute embeddings with the local model")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    tickets = make_tickets()
    articles, chunks = make_kb()
    if args.embed:
        print("Embedding tickets...", file=sys.stderr)
        tv = embed_all([f"{t['subject']}. {t['body']}" for t in tickets])
        for t, v in zip(tickets, tv):
            t["embedding"], t["embeddingModel"] = v, "all-MiniLM-L6-v2"
        print("Embedding chunks...", file=sys.stderr)
        cv = embed_all([c["content"] for c in chunks])
        for c, v in zip(chunks, cv):
            c["embedding"] = v
    (DATA / "tickets.json").write_text(json.dumps(tickets, indent=1))
    (DATA / "kb_articles.json").write_text(json.dumps(articles, indent=1))
    with open(DATA / "chunks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "article_id", "chunk_no", "content", "product", "region",
                    "effective_from", "effective_to", "meta", "embedding"])
        for c in chunks:
            emb = "[" + ",".join(str(x) for x in c["embedding"]) + "]" if "embedding" in c else ""
            w.writerow([c["id"], c["article_id"], c["chunk_no"], c["content"], c["product"], c["region"],
                        c["effective_from"], c["effective_to"] or "", json.dumps(c["meta"]), emb])
    print(f"{len(tickets)} tickets, {len(articles)} articles, {len(chunks)} chunks written to {DATA}")


if __name__ == "__main__":
    main()
