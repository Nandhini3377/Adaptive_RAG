"""Tests for the quick scan, sampling, intent suggestions, and the strategy decision table."""

import pytest

from adaptive_rag.ingest.intent import many_relationships, suggest_intents
from adaptive_rag.ingest.parser import parse_markdown
from adaptive_rag.ingest.sampler import analyze_sample, choose_sample, entity_repetition
from adaptive_rag.ingest.scanner import group_sections, scan
from adaptive_rag.ingest.selector import decide, is_small_plain
from adaptive_rag.schemas import DocumentProfile, Section
from tests.conftest import FakeLLM

ARCHITECTURE_MD = """# Overview

The Payments service depends on the Auth service. Orders calls Payments.
See Section 3 for the data flow.

# Auth service

Auth is owned by the Identity team. It integrates with the LDAP directory.
Error AUTH-403 means the token expired.

# Data flow

| Service  | Calls    |
|----------|----------|
| Orders   | Payments |
| Payments | Auth     |

As described in Section 2, Auth issues tokens via api_gateway v2.1.0.
"""


# ------------------------------------------------------------------- scan


def test_sections_group_text_under_each_heading():
    sections = group_sections(parse_markdown(ARCHITECTURE_MD))
    assert [s.title for s in sections] == ["Overview", "Auth service", "Data flow"]
    assert "Identity team" in sections[1].text
    assert sections[0].relationship_phrases == 2  # depends on, calls


def test_text_before_first_heading_is_an_introduction_section():
    sections = group_sections(parse_markdown("Preface text.\n\n# Title\n\nBody."))
    assert [s.title for s in sections] == ["Introduction", "Title"]


def test_scan_counts_structure():
    profile = scan(parse_markdown(ARCHITECTURE_MD))
    assert profile.section_count == 3
    assert profile.heading_count == 3
    assert profile.table_count == 1
    assert profile.page_count == 1  # Markdown has no pages: estimated from words
    assert 0 < profile.table_share < 0.3


def test_scan_finds_patterns():
    """Cross-refs, relationship phrases, and identifiers are counted per 1,000 words."""
    profile = scan(parse_markdown(ARCHITECTURE_MD))
    words = profile.word_count
    assert profile.cross_ref_rate == pytest.approx(4 * 1000 / words, rel=0.01)
    assert profile.relationship_phrase_rate > 0
    assert profile.identifier_density > 0


def test_plain_prose_has_no_signals():
    profile = scan(parse_markdown("# Leave\n\nEmployees get twenty days of leave each year."))
    assert profile.cross_ref_rate == 0
    assert profile.relationship_phrase_rate == 0
    assert profile.identifier_density == 0


# ----------------------------------------------------------------- sample


def sections(n: int, phrases_at: dict[int, int] | None = None) -> list[Section]:
    phrases_at = phrases_at or {}
    return [
        Section(
            id=str(i), title=f"S{i}", text=f"text {i}", relationship_phrases=phrases_at.get(i, 0)
        )
        for i in range(n)
    ]


def test_sample_size_is_between_5_and_10():
    assert len(choose_sample(sections(3))) == 3  # fewer sections than the minimum
    assert len(choose_sample(sections(12))) == 5
    assert len(choose_sample(sections(100))) == 10


def test_sample_prefers_relationship_heavy_sections_and_spreads_the_rest():
    chosen = [s.id for s in choose_sample(sections(40, phrases_at={33: 9, 21: 5}))]
    assert "33" in chosen and "21" in chosen
    assert chosen == sorted(chosen, key=int)  # document order
    assert int(chosen[0]) < 10 and int(chosen[-1]) > 25  # spread from start to end


def test_entity_repetition_counts_entities_in_three_or_more_sections():
    secs = [
        Section(id=str(i), title="t", text=t)
        for i, t in enumerate(["Auth and Orders", "Auth here", "auth again", "Orders once more"])
    ]
    assert entity_repetition(["Auth", "Orders", "Billing"], secs) == pytest.approx(0.33, abs=0.01)


def test_sampled_llm_extraction_sets_density():
    llm = FakeLLM(
        data={
            "entities": [
                {"name": n, "type": "service"} for n in ["Payments", "Auth", "Orders", "auth "]
            ],
            "relationships": [
                {"source": "Payments", "relation": "DEPENDS_ON", "target": "Auth"},
                {"source": "Orders", "relation": "CALLS", "target": "Payments"},
            ],
        }
    )
    elements = parse_markdown(ARCHITECTURE_MD)
    profile = analyze_sample(group_sections(elements), scan(elements), llm)
    assert profile.sample_entities == ["Payments", "Auth", "Orders"]  # 'auth ' deduplicated
    assert profile.relationship_density == pytest.approx(2 / 3, abs=0.01)
    assert profile.analysis_tokens == 120
    assert "Payments -DEPENDS_ON-> Auth" in profile.sample_relationships
    assert len(llm.calls) == 1  # one LLM call for the whole sample


# ---------------------------------------------------------------- intents


def profile(**signals) -> DocumentProfile:
    defaults = {"page_count": 5, "word_count": 3000}
    return DocumentProfile(**{**defaults, **signals})


MANY = {"relationship_density": 2.5}
FEW = {"relationship_density": 0.3}
SMALL_PLAIN = {"page_count": 3, "identifier_density": 0.2, "table_share": 0.0}


def test_many_relationships_rule():
    assert many_relationships(profile(relationship_density=1.6))
    assert many_relationships(profile(cross_ref_rate=2.5, relationship_phrase_rate=3.5))
    assert not many_relationships(profile(cross_ref_rate=2.5, relationship_phrase_rate=1.0))
    assert not many_relationships(profile(relationship_density=1.5))  # strictly greater


def test_suggested_intents_follow_the_scan():
    assert suggest_intents(profile(**FEW, **SMALL_PLAIN)) == ["facts"]
    assert "exact_terms" in suggest_intents(profile(identifier_density=8))
    assert "exact_terms" in suggest_intents(profile(table_share=0.2))
    assert suggest_intents(profile(relationship_density=3, cross_ref_rate=4)) == [
        "facts",
        "connections",
        "compare",
    ]


# ----------------------------------------------------- decision table rows


def test_row1_small_plain_facts_is_vector():
    decision = decide(profile(**FEW, **SMALL_PLAIN), ["facts"])
    assert decision.strategy == "vector"


def test_row2_few_relationships_facts_or_terms_is_hybrid():
    assert decide(profile(**FEW, page_count=40), ["facts"]).strategy == "hybrid"
    assert decide(profile(**FEW, **SMALL_PLAIN), ["facts", "exact_terms"]).strategy == "hybrid"


def test_row3_few_relationships_wanting_connections_is_hybrid_with_warning():
    decision = decide(profile(**FEW), ["connections"])
    assert decision.strategy == "hybrid"
    assert "few relationships" in decision.warning


def test_row4_many_relationships_wanting_connections_is_graph_hybrid():
    assert decide(profile(**MANY), ["connections"]).strategy == "graph_hybrid"
    assert decide(profile(**MANY), ["facts", "compare"]).strategy == "graph_hybrid"


def test_row5_many_relationships_but_only_facts_is_hybrid_graph_candidate():
    decision = decide(profile(**MANY), ["facts", "exact_terms"])
    assert decision.strategy == "hybrid"
    assert decision.graph_candidate is True


def test_row6_many_relationships_skipped_intent_is_graph_hybrid():
    assert decide(profile(**MANY), None).strategy == "graph_hybrid"


def test_skipped_intent_without_relationships_uses_the_scan():
    assert decide(profile(**FEW, **SMALL_PLAIN), None).strategy == "vector"
    assert decide(profile(**FEW, page_count=50), None).strategy == "hybrid"


def test_decisions_explain_themselves_with_numbers():
    decision = decide(profile(**MANY, cross_ref_rate=3.0), ["connections"])
    assert "2.5 per entity" in decision.reason
    assert "3.0 cross-references" in decision.reason


def test_confidence_is_higher_when_scan_is_clear_and_intent_agrees():
    clear_agree = decide(profile(relationship_density=4.0), ["connections"]).confidence
    borderline_agree = decide(profile(relationship_density=1.6), ["connections"]).confidence
    clear_disagree = decide(profile(relationship_density=4.0), ["facts"]).confidence
    assert clear_agree > borderline_agree
    assert clear_agree > clear_disagree
    assert all(0.3 <= c <= 0.95 for c in (clear_agree, borderline_agree, clear_disagree))


def test_small_plain_rule():
    assert is_small_plain(profile(**SMALL_PLAIN))
    assert not is_small_plain(profile(**{**SMALL_PLAIN, "page_count": 12}))
    assert not is_small_plain(profile(**{**SMALL_PLAIN, "table_share": 0.1}))
