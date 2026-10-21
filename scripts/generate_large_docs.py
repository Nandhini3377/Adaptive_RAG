# ruff: noqa: E501  (the service and settings tables read best one entry per line)
"""Generate the "large" evaluation corpus: two ~20-page documents and their gold questions.

The demo corpus (generate_demo_docs.py) is 5-20 chunks per document, so every mode
returns nearly the whole document and they all tie. These two are built so the modes
differ:

- orion_architecture.md: 60 services, dependency chains up to 4 hops, and NO summary
  table, so "which services indirectly depend on X" needs facts from many sections.
  Expected strategy: graph_hybrid.
- orion_pay_reference.md: 120 near-identical error codes (PAY-1041 vs PAY-1014) and
  30 snake_case settings, plus prose policy sections. Expected strategy: hybrid.

Every gold sentence is produced by the same function that writes it into the document,
so a question's evidence is always an exact sentence. Seeded: re-running gives the same
files.

Usage (from backend/):  uv run python ../scripts/generate_large_docs.py
"""

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "eval_large"
DOCS = OUT / "docs"
ARCH = "orion_architecture.md"
PAY = "orion_pay_reference.md"
SEED = 7


@dataclass
class Question:
    id: str
    type: str
    question: str
    documents: list[str]
    gold_answer: str
    answer_keywords: list[str]
    gold_evidence: list[str | list[str]]
    answerable: bool = True
    notes: str = ""
    extra: dict = field(default_factory=dict)


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


# =========================================================== 1. architecture

# team -> (lead, city, planning day)
TEAMS = {
    "Platform": ("Asha Raman", "Bengaluru", "Monday"),
    "Data Platform": ("Marcus Lee", "Pune", "Tuesday"),
    "Security": ("Elena Petrova", "Hyderabad", "Wednesday"),
    "Identity": ("Daniel Okafor", "Chennai", "Thursday"),
    "Catalog": ("Priya Nair", "Bengaluru", "Friday"),
    "Checkout": ("Tomas Garcia", "Madrid", "Monday"),
    "Payments": ("Mei Chen", "Singapore", "Tuesday"),
    "Fulfilment": ("Samuel Adeyemi", "Lagos", "Wednesday"),
    "Customer": ("Hannah Schmidt", "Berlin", "Thursday"),
    "Analytics": ("Kenji Watanabe", "Tokyo", "Friday"),
}

# name -> (team, layer, what it does). Layer 0 depends on nothing; a service only
# depends on services in lower layers, so chains run up to 4 hops.
SERVICES = {
    "Event Bus": (
        "Platform",
        0,
        "carries events between services so they never call each other synchronously for updates",
    ),
    "Cache Cluster": (
        "Platform",
        0,
        "keeps frequently read data in memory so that hot pages load without touching the databases",
    ),
    "Config Service": (
        "Platform",
        0,
        "stores feature flags and runtime settings that every service reads at start-up",
    ),
    "Service Mesh": (
        "Platform",
        1,
        "encrypts traffic between services and retries calls that fail because of network blips",
    ),
    "Job Scheduler": (
        "Platform",
        1,
        "runs timed background jobs such as nightly clean-ups and hourly exports",
    ),
    "API Gateway": (
        "Platform",
        4,
        "receives every request from the mobile apps and the website and forwards it to the right service",
    ),
    "Postgres Cluster": (
        "Data Platform",
        0,
        "is the main relational database that holds orders, accounts, and stock levels",
    ),
    "Object Store": (
        "Data Platform",
        0,
        "keeps large files such as product photos, invoices, and exported reports",
    ),
    "Search Index": (
        "Data Platform",
        0,
        "holds a full-text index of products so that searches return results in milliseconds",
    ),
    "Metrics Pipeline": (
        "Data Platform",
        0,
        "collects counters and timings from every service and sends them to the dashboards",
    ),
    "Stream Processor": (
        "Data Platform",
        1,
        "reads the event stream and computes running totals such as sales per minute",
    ),
    "Data Warehouse": (
        "Data Platform",
        2,
        "stores the full history of business data for analysts to query",
    ),
    "Secrets Vault": (
        "Security",
        0,
        "stores passwords, API keys, and certificates and hands them only to approved services",
    ),
    "Token Service": (
        "Security",
        1,
        "issues and verifies the signed tokens that prove a request comes from a logged-in user",
    ),
    "Key Rotation Service": (
        "Security",
        1,
        "replaces every encryption key every 90 days so a leaked key stops working quickly",
    ),
    "Audit Log": (
        "Security",
        1,
        "records who changed what and when, and keeps the records for seven years",
    ),
    "Fraud Engine": (
        "Security",
        2,
        "scores each payment for the risk that it was made with stolen card details",
    ),
    "Consent Manager": (
        "Security",
        2,
        "remembers which kinds of marketing each customer agreed to receive",
    ),
    "User Accounts": (
        "Identity",
        1,
        "stores customer accounts, email addresses, and password hashes",
    ),
    "Session Store": (
        "Identity",
        1,
        "remembers who is logged in on which device until the session expires",
    ),
    "Login Service": (
        "Identity",
        2,
        "checks passwords and starts a session when a customer signs in",
    ),
    "Profile Service": (
        "Identity",
        2,
        "stores names, saved addresses, and preferences that customers edit in their account page",
    ),
    "Permissions Service": (
        "Identity",
        2,
        "decides which staff members may open which internal tools",
    ),
    "Two Factor Service": (
        "Identity",
        2,
        "sends one-time codes and checks them when a login looks unusual",
    ),
    "Product Catalog": (
        "Catalog",
        1,
        "holds product titles, descriptions, sizes, and colours for everything Orion sells",
    ),
    "Inventory Ledger": (
        "Catalog",
        1,
        "records every change to stock so that the count of items on hand is always exact",
    ),
    "Image Service": (
        "Catalog",
        1,
        "resizes and crops product photos for phones, tablets, and desktops",
    ),
    "Pricing Engine": (
        "Catalog",
        2,
        "calculates the current price of each product, including regional prices",
    ),
    "Recommendation Engine": (
        "Catalog",
        3,
        "suggests products a customer is likely to want based on what similar shoppers bought",
    ),
    "Search Frontend": (
        "Catalog",
        3,
        "turns what a shopper types into a product search and ranks the results",
    ),
    "Address Validator": (
        "Checkout",
        1,
        "checks that a shipping address really exists and corrects common spelling mistakes in street names",
    ),
    "Cart Service": (
        "Checkout",
        2,
        "keeps the items a shopper has added to the basket, even across devices",
    ),
    "Promotions Service": ("Checkout", 2, "applies discount codes and seasonal offers to a basket"),
    "Tax Calculator": (
        "Checkout",
        2,
        "works out sales tax and VAT for each item based on where it ships",
    ),
    "Checkout Orchestrator": (
        "Checkout",
        3,
        "guides a basket through address, payment, and confirmation steps in order",
    ),
    "Order Service": (
        "Checkout",
        3,
        "creates the order record once payment succeeds and tracks its status",
    ),
    "Currency Converter": (
        "Payments",
        1,
        "shows prices in the shopper's local money using exchange rates refreshed every 15 minutes",
    ),
    "Card Processor": (
        "Payments",
        2,
        "sends card payments to the card networks and reads back the approval or decline",
    ),
    "Wallet Service": (
        "Payments",
        2,
        "holds store credit and gift card balances for each customer",
    ),
    "Settlement Service": (
        "Payments",
        2,
        "moves collected money to Orion's bank account in daily batches",
    ),
    "Payment Router": (
        "Payments",
        3,
        "chooses which payment provider handles each payment to keep fees low",
    ),
    "Refund Service": (
        "Payments",
        3,
        "returns money to the original payment method when an order is cancelled or returned",
    ),
    "Warehouse Manager": ("Fulfilment", 2, "tracks which shelf in which warehouse holds each item"),
    "Stock Allocator": ("Fulfilment", 2, "decides which warehouse should ship each order line"),
    "Picking Planner": (
        "Fulfilment",
        3,
        "plans the route warehouse staff walk to collect items so the walking distance stays short",
    ),
    "Packing Service": (
        "Fulfilment",
        3,
        "chooses the box size and prints the packing slip for each parcel",
    ),
    "Shipment Tracker": (
        "Fulfilment",
        3,
        "follows each parcel with the courier and updates its delivery status",
    ),
    "Returns Service": (
        "Fulfilment",
        4,
        "books return pickups and checks returned items back into stock",
    ),
    "Email Sender": (
        "Customer",
        1,
        "delivers transactional emails such as receipts and password resets",
    ),
    "SMS Gateway": ("Customer", 1, "delivers text messages through local mobile carriers"),
    "Notification Hub": (
        "Customer",
        2,
        "decides whether to tell a customer something by email, text, or app notification",
    ),
    "Reviews Service": (
        "Customer",
        3,
        "collects product ratings and hides reviews that break the posting rules",
    ),
    "Loyalty Service": (
        "Customer",
        3,
        "awards points for purchases and lets members spend them on later orders",
    ),
    "Support Desk": (
        "Customer",
        4,
        "gives support agents one screen with a customer's orders, payments, and messages",
    ),
    "Clickstream Collector": (
        "Analytics",
        1,
        "records page views and clicks from the website and apps",
    ),
    "Experiment Platform": (
        "Analytics",
        3,
        "splits shoppers into groups to test changes and measures which version wins",
    ),
    "Forecasting Service": (
        "Analytics",
        3,
        "predicts next month's demand for each product so buyers can reorder in time",
    ),
    "Reporting Service": (
        "Analytics",
        4,
        "builds the weekly sales and margin reports for the leadership team",
    ),
    "Dashboard Service": ("Analytics", 4, "shows live business numbers on screens in every office"),
    "Attribution Service": ("Analytics", 4, "works out which advert or campaign led to each sale"),
}

REGIONS = ["Mumbai", "Singapore", "Frankfurt", "Virginia"]
CADENCES = ["several times a day", "daily", "twice a week", "weekly"]
OPS_FILLER = [
    "Its alerts page the owning team only during working hours unless an error budget is burning fast.",
    "Changes go through a canary release that receives five percent of traffic for thirty minutes.",
    "The service writes structured logs that are kept for thirty days.",
    "Load tests run against it before every major sales event.",
    "Its dashboards show request rate, error rate, and saturation side by side.",
    "A runbook describes how to drain traffic from one region during an incident.",
    "Capacity is reviewed every quarter against the traffic forecast.",
    "All of its configuration is stored in version control and reviewed before release.",
    "It exposes a health endpoint that the load balancer checks every ten seconds.",
    "Database migrations for it must be backwards compatible for one release.",
    "Its on-call rotation hands over every Monday at ten in the morning.",
    "The team keeps a list of known failure modes and how each one was last fixed.",
    "Synthetic checks call it from outside the data centre every minute.",
    "Feature flags let the team switch new behaviour off without a deployment.",
    "Error messages from it never include customer personal data.",
    "It was last reviewed for security in the most recent annual audit.",
]


def build_dependencies(rng: random.Random) -> dict[str, list[str]]:
    by_layer: dict[int, list[str]] = {}
    for name, (_team, layer, _what) in SERVICES.items():
        by_layer.setdefault(layer, []).append(name)
    deps: dict[str, list[str]] = {}
    for name, (_team, layer, _what) in SERVICES.items():
        if layer == 0:
            deps[name] = []
            continue
        chosen = [rng.choice(by_layer[layer - 1])]  # one from the layer just below
        lower = [s for lay in range(layer) for s in by_layer[lay] if s not in chosen]
        chosen += rng.sample(lower, rng.randint(0, 2))
        deps[name] = sorted(chosen, key=list(SERVICES).index)
    return deps


def purpose_sentence(name: str) -> str:
    return f"The {name} {SERVICES[name][2]}."


def owner_sentence(name: str) -> str:
    return f"The {name} is owned by the {SERVICES[name][0]} team."


def depends_sentence(name: str, deps: dict[str, list[str]]) -> str:
    if not deps[name]:
        return f"The {name} does not depend on any other service."
    return f"The {name} depends on {_join(['the ' + d for d in deps[name]])}."


def latency_sentence(name: str, ms: int) -> str:
    return f"The {name} has a p99 latency target of {ms} ms."


def lead_sentence(team: str) -> str:
    return f"The {team} team is led by {TEAMS[team][0]}."


def architecture_md(deps: dict, latency: dict, rng: random.Random) -> str:
    lines = [
        "# Orion Retail Platform Architecture",
        "",
        "## 1. About this document",
        "",
        "This document describes every service that runs the Orion Retail website and apps. "
        "Each service has its own section that explains what it does, which team owns it, "
        "which other services it needs, and how it is operated. There is deliberately no "
        "single dependency diagram: dependencies change every week, so each service section "
        "is the source of truth for that service only.",
        "",
        "Teams are listed at the end of the document with their leads and planning days. "
        "When a service changes owner, the service section is updated first and the team "
        "list second.",
        "",
        "## 2. How services are operated",
        "",
        "Every service is deployed to at least two regions so that one region can fail "
        "without taking the shop down. Each service has a p99 latency target and an "
        "availability target that the owning team reviews every quarter. When a target is "
        "missed two quarters in a row, the team must present a recovery plan at the "
        "architecture review.",
        "",
        "A service may only depend on services in a lower layer of the platform. Calls in "
        "the other direction must go through the Event Bus as events, which keeps the "
        "platform free of circular dependencies.",
        "",
        "## 3. Services",
        "",
    ]
    for team in TEAMS:
        lines += [f"## {team} services", ""]
        for name, (owner, _layer, _what) in SERVICES.items():
            if owner != team:
                continue
            replicas = rng.choice([2, 3, 4, 6, 8])
            availability = rng.choice(["99.9", "99.95", "99.99"])
            filler = " ".join(rng.sample(OPS_FILLER, 6))
            lines += [
                f"### {name}",
                "",
                f"{purpose_sentence(name)} {owner_sentence(name)} {depends_sentence(name, deps)}",
                "",
                f"It runs {replicas} replicas in the {rng.choice(REGIONS)} region and is "
                f"deployed {rng.choice(CADENCES)}. {latency_sentence(name, latency[name])} "
                f"Its availability target is {availability} percent. {filler}",
                "",
            ]
    lines += ["## 4. Teams", ""]
    for team, (_lead, city, day) in TEAMS.items():
        lines += [
            f"### {team} team",
            "",
            f"{lead_sentence(team)} The team is based in {city} and holds its planning "
            f"review every {day}. New joiners are paired with a buddy for their first month.",
            "",
        ]
    return "\n".join(lines)


def dependents(name: str, deps: dict) -> list[str]:
    return [s for s in SERVICES if name in deps[s]]


def all_dependents(name: str, deps: dict) -> list[str]:
    found: list[str] = []
    frontier = [name]
    while frontier:
        nxt = [d for f in frontier for d in dependents(f, deps) if d not in found]
        found += list(dict.fromkeys(nxt))
        frontier = list(dict.fromkeys(nxt))
    return [s for s in SERVICES if s in found]


def architecture_questions(deps: dict, latency: dict, rng: random.Random) -> list[dict]:
    q: list[dict] = []

    def add(type_, question, answer, keywords, evidence):
        q.append(
            dict(
                type=type_,
                question=question,
                documents=[ARCH],
                gold_answer=answer,
                answer_keywords=[str(k) for k in keywords],
                gold_evidence=evidence,
            )
        )

    names = list(SERVICES)
    for name in rng.sample(names, 6):
        ms = latency[name]
        add(
            "fact_lookup",
            f"What is the p99 latency target of the {name}?",
            f"{ms} ms",
            [ms],
            [latency_sentence(name, ms)],
        )

    semantic = {
        "Address Validator": "How do we stop parcels going to a misspelled street?",
        "Key Rotation Service": "How often are our encryption keys swapped for new ones?",
        "Currency Converter": "How do shoppers abroad see prices in their own money?",
        "Picking Planner": "What keeps warehouse workers from walking too far to gather an order?",
    }
    for name, question in semantic.items():
        add("semantic", question, f"The {name}", [name], [purpose_sentence(name)])

    with_deps = [n for n in names if deps[n]]
    for name in rng.sample(names, 4):
        team = SERVICES[name][0]
        add(
            "relationship",
            f"Which team owns the {name}?",
            f"The {team} team",
            [team],
            [owner_sentence(name)],
        )
    for name in rng.sample(with_deps, 4):
        add(
            "relationship",
            f"What does the {name} depend on?",
            ", ".join(deps[name]),
            deps[name],
            [depends_sentence(name, deps)],
        )

    # Multi-hop 1: indirect dependents, kept to 2-4 so they fit in the top 5
    indirect_targets = [
        n
        for n in names
        if 2 <= len([d for d in all_dependents(n, deps) if d not in dependents(n, deps)]) <= 4
    ]
    for name in rng.sample(indirect_targets, min(6, len(indirect_targets))):
        indirect = [d for d in all_dependents(name, deps) if d not in dependents(name, deps)]
        add(
            "multi_hop",
            f"Which services indirectly depend on the {name}?",
            ", ".join(indirect),
            indirect,
            [depends_sentence(d, deps) for d in indirect],
        )

    # Multi-hop 2: service -> owning team -> its lead (two different sections)
    for name in rng.sample(names, 4):
        team = SERVICES[name][0]
        add(
            "multi_hop",
            f"Who leads the team that owns the {name}?",
            TEAMS[team][0],
            [TEAMS[team][0]],
            [owner_sentence(name), lead_sentence(team)],
        )

    # Multi-hop 3: teams owning the direct dependents (owner sentence is in the same section)
    direct_targets = [n for n in names if 2 <= len(dependents(n, deps)) <= 3]
    for name in rng.sample(direct_targets, min(4, len(direct_targets))):
        users = dependents(name, deps)
        teams = sorted({SERVICES[u][0] for u in users})
        add(
            "multi_hop",
            f"Which teams own services that depend on the {name}?",
            ", ".join(teams),
            teams,
            [depends_sentence(u, deps) for u in users],
        )

    a, b = rng.sample(with_deps, 2)
    add(
        "comparison",
        f"Compare the dependencies of the {a} and the {b}.",
        f"{a}: {', '.join(deps[a])}; {b}: {', '.join(deps[b])}",
        [*deps[a], *deps[b]],
        [depends_sentence(a, deps), depends_sentence(b, deps)],
    )
    a, b = rng.sample(names, 2)
    add(
        "comparison",
        f"Compare the p99 latency targets of the {a} and the {b}.",
        f"{latency[a]} ms vs {latency[b]} ms",
        [latency[a], latency[b]],
        [latency_sentence(a, latency[a]), latency_sentence(b, latency[b])],
    )
    return q


# ========================================================== 2. API reference

SUBJECTS = [
    "the card number",
    "the expiry date",
    "the card security code",
    "the billing address",
    "the currency code",
    "the merchant account",
    "the idempotency key",
    "the webhook signature",
    "the refund amount",
    "the settlement batch",
    "the customer token",
    "the 3-D Secure challenge",
]
PROBLEMS = [
    ("is missing from the request", "add the field and send the request again"),
    ("has the wrong format", "check the format in the field reference and resend"),
    ("has expired", "ask the customer for fresh details"),
    ("does not match the stored value", "reload the stored value and compare before resending"),
    ("was rejected by the card network", "show the customer a generic decline message"),
    ("is longer than allowed", "shorten the value to the documented maximum"),
    ("belongs to a different merchant", "use the credentials of the merchant that owns it"),
    ("was already used", "create a new one instead of reusing the old one"),
    ("is locked for manual review", "wait for the review to finish before retrying"),
    ("timed out before it could be checked", "retry with exponential backoff"),
]
CAUSES = [
    "This usually comes from an outdated client library.",
    "It is most often seen right after a merchant changes their integration.",
    "Support tickets show it is common during large sales events.",
    "It can appear when a request is replayed from a log file.",
    "Mobile clients on weak connections trigger it more often than web clients.",
    "It is logged with the request ID so support can trace it.",
]

SETTINGS = [
    ("retry_max_attempts", "how many times the client library retries a failed request", "5"),
    ("retry_backoff_ms", "the first wait between retries, which doubles each time", "200"),
    ("retry_backoff_max_ms", "the longest wait allowed between two retries", "10000"),
    ("request_timeout_ms", "how long the client waits for any response", "30000"),
    ("connect_timeout_ms", "how long the client waits to open a connection", "5000"),
    ("webhook_retry_hours", "how long failed webhook deliveries keep being retried", "72"),
    ("webhook_timeout_ms", "how long Orion Pay waits for a merchant's webhook endpoint", "10000"),
    ("webhook_batch_size", "how many events are sent in one webhook call", "50"),
    ("idempotency_ttl_hours", "how long an idempotency key is remembered", "24"),
    ("settlement_cutoff_utc", "the time each daily settlement batch closes", "23:00"),
    ("settlement_delay_days", "how many business days settled funds take to arrive", "2"),
    ("refund_window_days", "how long after a payment a refund can be issued", "180"),
    ("refund_partial_limit", "how many partial refunds one payment can have", "10"),
    ("dispute_response_days", "how long a merchant has to answer a chargeback", "7"),
    ("fraud_score_threshold", "the fraud score above which a payment is held", "0.85"),
    ("fraud_review_hours", "how long a held payment waits for manual review", "48"),
    ("token_ttl_days", "how long a saved card token stays valid without use", "395"),
    ("token_cache_size", "how many card tokens the client library caches", "1000"),
    ("rate_limit_rps", "how many requests per second one merchant may send", "300"),
    ("rate_limit_burst", "how many extra requests are allowed in a short burst", "600"),
    ("batch_export_rows", "the maximum number of rows in one transaction export", "100000"),
    ("batch_export_format", "the default file format of transaction exports", "CSV"),
    ("currency_rate_refresh_min", "how often exchange rates are refreshed", "15"),
    ("currency_default", "the currency used when a merchant sets none", "INR"),
    ("card_min_amount", "the smallest card payment accepted, in minor units", "100"),
    (
        "card_max_amount",
        "the largest card payment accepted without review, in minor units",
        "50000000",
    ),
    ("three_ds_required_above", "the amount above which 3-D Secure is always required", "500000"),
    ("log_retention_days", "how long request logs are kept", "90"),
    ("log_redact_fields", "whether sensitive fields are masked in logs", "true"),
    ("sandbox_reset_days", "how often sandbox accounts are wiped", "30"),
]

POLICIES = [
    (
        "Idempotency",
        "Every payment request must carry an idempotency key, and keys are remembered for 24 hours.",
        "How long does the system remember a request so a shopper isn't charged twice?",
        "semantic",
        ["24 hours"],
    ),
    (
        "Retries",
        "Clients should retry a failed request at most 5 times, with exponential backoff starting at 200 milliseconds.",
        "How many times should a client retry a failed request?",
        "fact_lookup",
        ["5"],
    ),
    (
        "Rate limits",
        "Each merchant may send up to 300 requests per second, and requests above that limit receive HTTP status 429.",
        "What happens if a shop sends too many requests too quickly?",
        "semantic",
        ["429"],
    ),
    (
        "Webhooks",
        "Webhook deliveries that fail are retried with backoff for up to 3 days.",
        "For how long are failed webhook deliveries retried?",
        "fact_lookup",
        ["3 days"],
    ),
    (
        "Data retention",
        "Raw card numbers are never stored, and tokenized card data is deleted 13 months after the card was last used.",
        "How long do we keep a customer's saved card after they stop shopping?",
        "semantic",
        ["13 months"],
    ),
    (
        "Settlement",
        "Settlement batches close at 23:00 UTC every day, and funds reach merchants within 2 business days.",
        "When does the daily settlement batch close?",
        "fact_lookup",
        ["23:00"],
    ),
    (
        "Refunds",
        "Refunds can be issued up to 180 days after the original payment.",
        "How long after buying can a customer still get their money back?",
        "semantic",
        ["180 days"],
    ),
    (
        "Disputes",
        "Merchants have 7 days to respond to a chargeback with supporting evidence.",
        "How many days does a merchant have to respond to a chargeback?",
        "fact_lookup",
        ["7"],
    ),
]
PROSE_FILLER = [
    "All requests use JSON over HTTPS, and every response carries a request ID.",
    "The sandbox environment behaves like production but never moves real money.",
    "Merchants can see each request and its response in the dashboard for ninety days.",
    "Client libraries are published for Python, Java, Go, and JavaScript.",
    "Breaking changes are announced at least six months in advance.",
    "Each API version is supported for at least two years after release.",
    "Timestamps are always given in UTC using the ISO 8601 format.",
    "Amounts are always sent as integers in the currency's minor unit.",
    "Merchants should store the request ID of every failed call for support.",
    "The status page lists any incident that affects payment success rates.",
    "Test card numbers for every error case are listed in the sandbox guide.",
    "Field names are case sensitive and always use snake case.",
]


def error_codes(rng: random.Random) -> list[str]:
    # Built from only four digits, so codes look alike (PAY-1041, PAY-1014, PAY-4011)
    pool = sorted(
        {f"PAY-{a}{b}{c}{d}" for a in "0147" for b in "0147" for c in "0147" for d in "0147"}
    )
    return rng.sample(pool, len(SUBJECTS) * len(PROBLEMS))


def error_sentence(code: str, subject: str, problem: str) -> str:
    return f"Error {code} means {subject} {problem}."


def setting_sentence(key: str, what: str, default: str) -> str:
    return f"The setting {key} controls {what} and defaults to {default}."


def pay_reference_md(codes: list[str], rng: random.Random) -> tuple[str, dict[str, tuple]]:
    lines = [
        "# Orion Pay API Reference",
        "",
        "## 1. Introduction",
        "",
        "Orion Pay is the payment API used by Orion Retail and its marketplace sellers. This "
        "reference explains the policies every integration must follow, every error code the "
        "API can return, and every client setting. " + " ".join(rng.sample(PROSE_FILLER, 4)),
        "",
        "## 2. Policies",
        "",
    ]
    for title, fact, *_ in POLICIES:
        filler = " ".join(rng.sample(PROSE_FILLER, 9))
        lines += [
            f"### {title}",
            "",
            f"{fact} {filler}",
            "",
            " ".join(rng.sample(PROSE_FILLER, 8)),
            "",
        ]

    meaning: dict[str, tuple] = {}
    lines += ["## 3. Error codes", ""]
    i = 0
    for subject in SUBJECTS:
        lines += [f"### Errors about {subject.removeprefix('the ')}", ""]
        for problem, fix in PROBLEMS:
            code = codes[i]
            i += 1
            meaning[code] = (subject, problem)
            lines += [
                f"{error_sentence(code, subject, problem)} {' '.join(rng.sample(CAUSES, 2))} "
                f"To resolve it, {fix}. In the sandbox, request req_{rng.randrange(16**8):08x} reproduces {code} on demand.",
                "",
            ]
    lines += ["## 4. Client settings", ""]
    for key, what, default in SETTINGS:
        lines += [
            f"{setting_sentence(key, what, default)} {' '.join(rng.sample(PROSE_FILLER, 2))}",
            "",
        ]
    return "\n".join(lines), meaning


def pay_questions(codes: list[str], meaning: dict, rng: random.Random) -> list[dict]:
    q: list[dict] = []

    def add(type_, question, answer, keywords, evidence):
        q.append(
            dict(
                type=type_,
                question=question,
                documents=[PAY],
                gold_answer=answer,
                answer_keywords=[str(k) for k in keywords],
                gold_evidence=evidence,
            )
        )

    # Codes with a look-alike (same digits, different order): the hard case for embeddings
    twins = [c for c in codes if any(o != c and sorted(o) == sorted(c) for o in codes)]
    for code in rng.sample(twins, 12):
        subject, problem = meaning[code]
        add(
            "keyword",
            f"What does error {code} mean?",
            f"{subject} {problem}",
            [subject.removeprefix("the ")],
            [error_sentence(code, subject, problem)],
        )
    for key, what, default in rng.sample(SETTINGS, 4):
        add(
            "keyword",
            f"What is the default value of {key}?",
            default,
            [default],
            [setting_sentence(key, what, default)],
        )
    for _title, fact, question, type_, keywords in POLICIES:
        add(type_, question, fact, keywords, [fact])
    for _ in range(2):
        a = rng.choice(twins)
        b = next(o for o in codes if o != a and sorted(o) == sorted(a))
        add(
            "comparison",
            f"Compare error {a} with error {b}.",
            f"{a}: {' '.join(meaning[a])}; {b}: {' '.join(meaning[b])}",
            [meaning[a][0].removeprefix("the "), meaning[b][0].removeprefix("the ")],
            [error_sentence(a, *meaning[a]), error_sentence(b, *meaning[b])],
        )
    return q


# ===================================================================== main


def main() -> None:
    rng = random.Random(SEED)
    DOCS.mkdir(parents=True, exist_ok=True)

    deps = build_dependencies(rng)
    latency = {
        name: rng.choice([20, 35, 50, 80, 120, 150, 200, 250, 300, 400]) for name in SERVICES
    }
    (DOCS / ARCH).write_text(architecture_md(deps, latency, rng), encoding="utf-8")
    codes = error_codes(rng)
    pay_text, meaning = pay_reference_md(codes, rng)
    (DOCS / PAY).write_text(pay_text, encoding="utf-8")

    raw = architecture_questions(deps, latency, rng) + pay_questions(codes, meaning, rng)
    unanswerable = [
        "Which team owns the Mobile App Service?",
        "What does error PAY-9999 mean?",
        "Who is the chief financial officer of Orion Retail?",
        "How long is the refund window for gift card purchases made in stores?",
    ]
    questions = [Question(id=f"L{i:02d}", **item) for i, item in enumerate(raw, start=1)] + [
        Question(
            id=f"L{len(raw) + i:02d}",
            type="unanswerable",
            question=text,
            documents=[ARCH, PAY],
            gold_answer="",
            answer_keywords=[],
            gold_evidence=[],
            answerable=False,
        )
        for i, text in enumerate(unanswerable, start=1)
    ]
    with (OUT / "questions.jsonl").open("w", encoding="utf-8") as out:
        for question in questions:
            out.write(json.dumps(asdict(question), ensure_ascii=False) + "\n")

    manifest = {
        "documents": [
            {
                "file": ARCH,
                "profile": "many services and multi-hop dependencies",
                "intents": ["connections", "compare"],
                "expected_strategy": "graph_hybrid",
            },
            {
                "file": PAY,
                "profile": "near-identical IDs and settings",
                "intents": ["facts", "exact_terms"],
                "expected_strategy": "hybrid",
            },
        ]
    }
    (OUT / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    counts: dict[str, int] = {}
    for question in questions:
        counts[question.type] = counts.get(question.type, 0) + 1
    words = {f: len((DOCS / f).read_text(encoding="utf-8").split()) for f in (ARCH, PAY)}
    pages = {f: round(w / 500) for f, w in words.items()}
    print(f"Wrote {DOCS}: words {words}, about {pages} pages")
    print(f"Wrote {len(questions)} questions: {counts}")


if __name__ == "__main__":
    main()
