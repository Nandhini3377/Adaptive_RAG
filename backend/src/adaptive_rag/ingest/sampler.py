"""Step 1b: LLM extraction on a small sample of sections, not the whole document (FR10, FR11).

Full extraction of a 100-page document costs ~100K tokens; a sample costs a
fraction of that and is enough to estimate how relationship-heavy it is.
"""

import math
import re

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMResponse, LLMTruncatedError
from adaptive_rag.schemas import DocumentProfile, Section

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                "required": ["name", "type"],
                "additionalProperties": False,
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "relation": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["source", "relation", "target"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entities", "relationships"],
    "additionalProperties": False,
}

_PROMPT = """Extract named entities and the relationships between them from these document sections.
- Entities: specific named things (services, systems, teams, people, products, policies, codes).
  Not generic words like "user" or "data".
- Relationships: only ones the text states, e.g. "Payments depends on Auth" ->
  {{"source": "Payments", "relation": "DEPENDS_ON", "target": "Auth"}}.
- Use UPPER_SNAKE_CASE relation names.
- List at most {limit} entities and {limit} relationships: the most important ones.

Sections:
"""


def choose_sample(sections: list[Section]) -> list[Section]:
    """5-10 sections: the most relationship-heavy half, plus evenly spread ones."""
    if not sections:
        return []
    size = min(
        len(sections),
        max(settings.sample_min_sections, min(settings.sample_max_sections, len(sections) // 4)),
    )
    by_phrases = sorted(sections, key=lambda s: s.relationship_phrases, reverse=True)
    chosen = {s.id: s for s in by_phrases[: math.ceil(size / 2)] if s.relationship_phrases}
    # Fill the rest with sections spread evenly from start to end, then any left over
    step = len(sections) / size
    spread = [sections[int(i * step)] for i in range(size)]
    for section in [*spread, *sections]:
        if len(chosen) >= size:
            break
        chosen.setdefault(section.id, section)
    return sorted(chosen.values(), key=lambda s: int(s.id))  # document order


def analyze_sample(sections: list[Section], profile: DocumentProfile, llm: LLM) -> DocumentProfile:
    """Extract from the sample and add relationship density and entity repetition."""
    sample = choose_sample(sections)
    if not sample:
        return profile
    response = _extract_sample(sample, llm)
    for _shrink in range(settings.sample_shrink_retries):
        if response is not None or len(sample) == 1:
            break
        sample = sample[::2]  # every other section: half the text, still spread out
        response = _extract_sample(sample, llm)
    if response is None:
        raise LLMTruncatedError("The sample analysis did not fit in the token budget")
    data = response.data or {}
    entities = _unique([e["name"] for e in data.get("entities", [])])
    relationships = [
        f"{r['source']} -{r['relation']}-> {r['target']}" for r in data.get("relationships", [])
    ]
    density = round(len(relationships) / len(entities), 2) if entities else 0.0
    return profile.model_copy(
        update={
            "sampled_section_ids": [s.id for s in sample],
            "relationship_density": density,
            "entity_repetition": entity_repetition(entities, sections),
            "analysis_tokens": response.input_tokens + response.output_tokens,
            "analysis_cost_inr": response.cost_inr,
            "sample_entities": entities,
            "sample_relationships": relationships,
        }
    )


def _extract_sample(sample: list[Section], llm: LLM) -> LLMResponse | None:
    """One extraction call over the sample; None if the answer was cut off."""
    prompt = _PROMPT.format(limit=settings.sample_max_items) + _sample_text(sample)
    try:
        return llm.complete_json(
            [{"role": "user", "content": prompt}],
            _EXTRACTION_SCHEMA,
            name="sample_extraction",
            max_tokens=settings.sample_max_tokens,
        )
    except LLMTruncatedError:
        return None


def entity_repetition(entities: list[str], sections: list[Section]) -> float:
    """Share of sampled entities that appear in 3+ sections (string match, full text)."""
    if not entities:
        return 0.0
    repeated = 0
    for name in entities:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if sum(bool(pattern.search(section.text)) for section in sections) >= 3:
            repeated += 1
    return round(repeated / len(entities), 2)


def _sample_text(sample: list[Section]) -> str:
    """The sampled sections as text, cut to the character budget."""
    budget = settings.sample_max_chars // len(sample)
    return "\n\n".join(f"## {s.title}\n{s.text[:budget]}" for s in sample)


def _unique(names: list[str]) -> list[str]:
    """Drop duplicates, ignoring case and extra spaces."""
    seen: dict[str, str] = {}
    for name in names:
        key = " ".join(name.lower().split())
        if key and key not in seen:
            seen[key] = name.strip()
    return list(seen.values())
