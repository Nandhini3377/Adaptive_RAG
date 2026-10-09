"""Classify a question by type: rules first, LLM only when the rules are unsure (FR24).

Most questions contain a clear signal ("compare", "depends on", "AUTH-403"), so
rules handle them for free; the rule-coverage metric in the Evaluation Lab
measures how often the LLM was needed.
"""

import re

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMError
from adaptive_rag.schemas import Classification, QueryType

_COMPARISON = re.compile(
    r"\b(?:compare|comparison|difference between|differences|differ|versus|vs\.?|"
    r"contrast|similarities)\b",
    re.IGNORECASE,
)
_RELATIONSHIP = re.compile(
    r"\b(?:depend\w*|connect\w*|relat\w*|owns?|owned|owner|calls?|called|upstream|downstream|"
    r"integrat\w*|reports? to|managed|maintain\w*|affect\w*|impact\w*|uses|used by|"
    r"linked|between)\b",
    re.IGNORECASE,
)
# A second hop: a relationship phrase applied to the result of another one
_MULTI_HOP = re.compile(
    r"\b(?:which|what|who)\b.*\b(?:that|which|who)\b.*\b(?:depend\w*|own\w*|call\w*|use\w*|"
    r"affect\w*|report\w*|manag\w*|integrat\w*)\b"
    r"|\b(?:indirectly|transitively|chain|downstream of .* of|eventually)\b",
    re.IGNORECASE,
)
# Relationship verbs; two different ones in one question chain two hops
# ("Which teams OWN services AFFECTED by X?")
_HOP_VERB = re.compile(
    r"\b(depend|own|call|use|affect|impact|report|manag|integrat|maintain|connect)\w*",
    re.IGNORECASE,
)
_AGGREGATION = re.compile(
    r"\b(?:list (?:all|every)|all (?:the )?\w+s\b|every|summari[sz]e|summary|overview|"
    r"how many \w+s (?:are|do|does|exist)|total|across (?:all|the))\b",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"[\"'“‘]([^\"'”’]{2,})[\"'”’]")
_IDENTIFIER = re.compile(
    r"\b[A-Z]{2,}[-_]\d+[A-Z0-9-]*\b|\bv?\d+\.\d+(?:\.\d+)+\b|\b[a-z]+_[a-z0-9_]+\b"
)
_FACT = re.compile(
    r"^\s*(?:what (?:is|are|was)|how (?:many|much|long|often)|when|where|who (?:is|was)|"
    r"is there|does|do|can|which)\b",
    re.IGNORECASE,
)

_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "query_type": {
            "type": "string",
            "enum": [
                "fact_lookup",
                "semantic",
                "keyword",
                "relationship",
                "multi_hop",
                "comparison",
                "aggregation",
            ],
        }
    },
    "required": ["query_type"],
    "additionalProperties": False,
}

_LLM_PROMPT = """Classify this question about a company's documents. Reply with one type:
- fact_lookup: a single fact or policy value ("How many leave days?")
- semantic: explain a process or concept in general terms ("How do we handle data deletion?")
- keyword: about an exact ID, code, version, or quoted term ("What is AUTH-403?")
- relationship: how two things connect ("What depends on the Auth service?")
- multi_hop: needs a chain of connections ("Which teams own services that use Auth?")
- comparison: compare two or more things
- aggregation: list, count, or summarize many items

Question: {question}"""


def classify_by_rules(question: str) -> Classification:
    """Pattern rules; `confident=False` when no rule or conflicting rules match."""
    entities = _QUOTED.findall(question) + _IDENTIFIER.findall(question)

    def result(query_type: QueryType, reason: str, confident: bool = True) -> Classification:
        return Classification(
            query_type=query_type, entities=entities, confident=confident, reason=reason
        )

    if _COMPARISON.search(question):
        return result("comparison", "mentions comparing things")
    hop_verbs = {verb.lower() for verb in _HOP_VERB.findall(question)}
    if _MULTI_HOP.search(question) or len(hop_verbs) >= 2:
        return result("multi_hop", "asks about a chain of connections")
    relationship = _RELATIONSHIP.search(question)
    aggregation = _AGGREGATION.search(question)
    if relationship and aggregation:
        # "List all services that depend on Auth" is relationship-shaped
        return result("relationship", "asks how things connect (and lists them)")
    if relationship:
        return result("relationship", f"relationship word '{relationship.group(0)}'")
    if aggregation:
        return result("aggregation", "asks to list, count, or summarize")
    if entities:
        return result("keyword", f"contains an exact term: {entities[0]}")
    if _FACT.search(question):
        return result("fact_lookup", "short factual question")
    return result("semantic", "no rule matched", confident=False)


def classify(question: str, llm: LLM | None = None) -> Classification:
    """Rules first; ask the LLM only if they are not confident and an LLM is given."""
    by_rules = classify_by_rules(question)
    if by_rules.confident or llm is None or not settings.classifier_llm_fallback:
        return by_rules
    try:
        response = llm.complete_json(
            [{"role": "user", "content": _LLM_PROMPT.format(question=question)}],
            _LLM_SCHEMA,
            name="query_type",
            max_tokens=settings.classifier_max_tokens,
        )
    except LLMError:
        return by_rules  # fall back to the rule guess rather than failing the query
    query_type = (response.data or {}).get("query_type", "semantic")
    return Classification(
        query_type=query_type,
        entities=by_rules.entities,
        confident=True,
        source="llm",
        reason="rules were unsure, so the LLM classified it",
    )
