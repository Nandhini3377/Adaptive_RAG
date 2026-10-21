"""Step 3b: a second opinion on the strategy from the LLM, and how the two picks combine.

The rules (selector.py) decide from fixed thresholds. The LLM gets every number the scan
and the sample produced, the uploader's intent, and the rules' criteria (what the numbers
mean), but not the rules' pick, so its answer stays a second opinion. It picks from all
five strategies.

Combining them: build only the indexes both picks share, and offer the rest as a
suggestion. Every overlap of two strategies' index sets is itself a strategy (see
MODE_INDEXES); when they share nothing, the rules' pick is built.
"""

import logging

from pydantic import BaseModel

from adaptive_rag.config import settings
from adaptive_rag.ingest.intent import INTENT_LABELS, many_relationships
from adaptive_rag.ingest.selector import is_small_plain
from adaptive_rag.llm.base import LLM, LLMError
from adaptive_rag.schemas import (
    INDEX_ORDER,
    MODE_INDEXES,
    DocumentProfile,
    Intent,
    Strategy,
    StrategyDecision,
    mode_for,
)

log = logging.getLogger(__name__)

_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy": {"type": "string", "enum": list(MODE_INDEXES)},
        "reason": {"type": "string"},
    },
    "required": ["strategy", "reason"],
    "additionalProperties": False,
}

_PROMPT = """Choose how to index a document for question answering. Options, cheapest first:
- vector: meaning search only. Free (local model). Plain prose, questions in the reader's own words.
- keyword: exact-word search only. Free. Questions will name exact IDs, codes, or terms.
- hybrid: meaning + exact words. Free. The safe choice for most documents.
- graph: knowledge graph only. Costs LLM calls over the whole document. Only when nearly
  every question follows relationships between named things.
- graph_hybrid: graph + meaning + exact words. Costs LLM calls. Many relationships, and
  questions mix facts with how things connect.
Pick the cheapest option that will answer the expected questions well.

Document signals:
- {pages} pages, {sections} sections, {words} words
- {tables} tables, holding {table_share:.0%} of the words
- cross-references ("see Section 4"): {cross_refs:.1f} per 1,000 words
- relationship phrases ("depends on", "owned by"): {phrases:.1f} per 1,000 words
- identifiers (codes, versions, IDs): {ids:.1f} per 1,000 words
- in a sample of sections: {relationship_density:.2f} relationships per entity;
  {repetition:.0%} of sampled entities appear in 3 or more sections
- sampled entities: {entities}
- sampled relationships: {relationships}

Expected questions (from the uploader): {intents}

The fixed rules' criteria, already checked against the numbers above (trust these
results; then decide yourself, and unlike the rules you may also pick keyword or graph):
{rule_checks}
The rules map them as: many relationships + questions about connections -> graph_hybrid;
small and plain + only fact questions -> vector; otherwise -> hybrid.

Reply with the strategy and one sentence saying why, citing the signals."""


class LLMStrategy(BaseModel):
    strategy: Strategy
    reason: str
    cost_inr: float = 0.0


def llm_strategy(
    profile: DocumentProfile, intents: list[Intent] | None, llm: LLM
) -> LLMStrategy | None:
    """The LLM's pick from all five strategies; None if the call fails or the reply is invalid."""
    prompt = _PROMPT.format(
        pages=profile.page_count,
        sections=profile.section_count,
        words=profile.word_count,
        tables=profile.table_count,
        table_share=profile.table_share,
        cross_refs=profile.cross_ref_rate,
        phrases=profile.relationship_phrase_rate,
        ids=profile.identifier_density,
        relationship_density=profile.relationship_density,
        repetition=profile.entity_repetition,
        entities=", ".join(profile.sample_entities[:15]) or "none found",
        relationships="; ".join(profile.sample_relationships[:10]) or "none found",
        intents="; ".join(INTENT_LABELS[i] for i in intents) if intents else "not given",
        rule_checks=rule_checks(profile),
    )
    try:
        response = llm.complete_json(
            [{"role": "user", "content": prompt}],
            _SCHEMA,
            name="strategy_choice",
            max_tokens=settings.strategy_max_tokens,
            reasoning_effort=settings.structured_reasoning_effort,
        )
    except LLMError as error:
        log.warning("LLM strategy choice failed: %s", error)
        return None
    data = response.data or {}
    strategy = data.get("strategy")
    if strategy not in MODE_INDEXES:
        return None
    return LLMStrategy(
        strategy=strategy, reason=str(data.get("reason", "")).strip(), cost_inr=response.cost_inr
    )


def rule_checks(profile: DocumentProfile) -> str:
    """Each rule criterion with its number, limit, and result, computed here (not by the LLM).

    Measured: given only the limits, the LLM called 9.8 relationship phrases per 1,000
    words "well below" a limit of 3.0. Comparing numbers is done in code instead.
    """

    def check(name: str, value: float, op: str, limit: float, unit: str = "") -> str:
        met = value > limit if op == ">" else value < limit if op == "<" else value >= limit
        words = {">": "more than", "<": "under", ">=": "at least"}[op]
        result = "met" if met else "not met"
        return f"  - {name}: {value:g}{unit} vs {words} {limit:g}{unit} -> {result}"

    s = settings
    yes = {True: "YES", False: "NO"}
    exact_terms = profile.identifier_density >= s.exact_terms_identifier_density
    lines = [
        f"- Many relationships: {yes[many_relationships(profile)]} "
        "(the first check alone, or the second AND the third, or the fourth alone)",
        check(
            "relationships per entity",
            profile.relationship_density,
            ">",
            s.many_relationships_density,
        ),
        check(
            "cross-references per 1,000 words",
            profile.cross_ref_rate,
            ">",
            s.many_relationships_cross_ref_rate,
        ),
        check(
            "relationship phrases per 1,000 words",
            profile.relationship_phrase_rate,
            ">",
            s.many_relationships_phrase_rate,
        ),
        check(
            "relationship phrases per 1,000 words (counts alone)",
            profile.relationship_phrase_rate,
            ">",
            s.many_relationships_phrase_only_rate,
        ),
        f"- Small and plain: {yes[is_small_plain(profile)]} (all three)",
        check("pages", profile.page_count, "<", s.small_plain_max_pages),
        check(
            "identifiers per 1,000 words",
            profile.identifier_density,
            "<",
            s.small_plain_max_identifier_density,
        ),
        check(
            "share of words in tables",
            round(profile.table_share * 100, 1),
            "<",
            s.small_plain_max_table_share * 100,
            "%",
        ),
        f"- Exact terms likely: {yes[exact_terms]}",
        check(
            "identifiers per 1,000 words",
            profile.identifier_density,
            ">=",
            s.exact_terms_identifier_density,
        ),
    ]
    return "\n".join(lines)


def combine(rules: StrategyDecision, llm: LLMStrategy | None) -> StrategyDecision:
    """Build what both picks share; suggest what only one of them wanted."""
    if llm is None:
        suggested = ["graph"] if rules.graph_candidate else []
        return rules.model_copy(
            update={
                "rules_strategy": rules.strategy,
                "suggested_indexes": suggested,
                "reason": f"{rules.reason} (No second opinion from the LLM: the rules decided.)",
            }
        )

    wanted_by_rules, wanted_by_llm = MODE_INDEXES[rules.strategy], MODE_INDEXES[llm.strategy]
    shared = wanted_by_rules & wanted_by_llm
    final = mode_for(shared) if shared else rules.strategy
    assert final is not None  # every overlap of two strategies is a strategy
    leftover = (wanted_by_rules | wanted_by_llm) - MODE_INDEXES[final]
    if rules.graph_candidate:
        leftover |= {"graph"}
    agree = rules.strategy == llm.strategy

    if agree:
        outcome = "Both picked it."
    elif shared:
        outcome = f"Built what both share: {final}."
    else:
        outcome = f"They share no index, so the rules' pick ({final}) is built."
    reason = f"Rules: {rules.strategy}. {rules.reason} LLM: {llm.strategy}. {llm.reason} {outcome}"
    confidence = rules.confidence + (0.1 if agree else -0.1)
    return rules.model_copy(
        update={
            "strategy": final,
            "confidence": round(min(0.95, max(0.3, confidence)), 2),
            "reason": reason,
            "graph_candidate": "graph" in leftover,
            "rules_strategy": rules.strategy,
            "llm_strategy": llm.strategy,
            "llm_reason": llm.reason,
            "suggested_indexes": [index for index in INDEX_ORDER if index in leftover],
        }
    )
