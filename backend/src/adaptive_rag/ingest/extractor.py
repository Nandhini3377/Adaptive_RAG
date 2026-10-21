"""Full graph extraction: entities and relationships from every chunk (FR19).

Runs only for documents whose strategy includes the graph, because it costs an
LLM call per batch of chunks.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMTruncatedError
from adaptive_rag.llm.safety import DATA_RULE, quoted
from adaptive_rag.schemas import Chunk, GraphEntity, GraphExtraction, GraphRelation

_SCHEMA = {
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
                    "chunk": {"type": "integer"},
                    "confidence": {"type": "number"},
                },
                "required": ["source", "relation", "target", "chunk", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entities", "relationships"],
    "additionalProperties": False,
}

_PROMPT = """Build a knowledge graph from these numbered text chunks.

Entities: specific named things (services, systems, teams, people, products, policies,
error codes, documents). Not generic words like "user", "data", or "system".
Entity type: one lowercase word, e.g. service, team, person, policy, code, product.

Relationships: only ones the text states. For each, give:
- source and target: entity names exactly as in your entity list
- relation: UPPER_SNAKE_CASE verb, e.g. DEPENDS_ON, OWNED_BY, CALLS, PART_OF, REPORTS_TO
- chunk: the id of the <document> chunk that states it
- confidence: 0-1, how clearly the text states it
{data_rule}
{known}
Chunks:
{chunks}"""

_KNOWN = """
Entities already found earlier in this document. If a chunk refers to one of
them, reuse the exact name (so "the auth service" -> "Auth Service"):
{names}
"""

_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
_SPACE_OR_PUNCT = re.compile(r"[\s\-_.,:;'\"()]+")


def entity_key(name: str) -> str:
    """Normalize a name so 'The Auth-Service' and 'auth service' are one node."""
    name = _ARTICLE.sub("", name.strip())
    return _SPACE_OR_PUNCT.sub(" ", name.lower()).strip()


def extract_graph(chunks: list[Chunk], llm: LLM) -> GraphExtraction:
    """Extract entities and relationships from small batches, several at a time.

    Batches run in waves of `extraction_parallel`. Each wave is told the entity names
    found by earlier waves, so later text reuses them ("the auth service" -> "Auth Service").
    """
    result = GraphExtraction()
    entities: dict[str, GraphEntity] = {}
    relations: dict[tuple[str, str, str], GraphRelation] = {}  # dedupe repeated facts

    batches = _batches(chunks)
    wave_size = max(1, settings.extraction_parallel)
    with ThreadPoolExecutor(max_workers=wave_size) as pool:
        for start in range(0, len(batches), wave_size):
            wave = batches[start : start + wave_size]
            known = list(entities.values())  # a snapshot: workers never share state
            # map() keeps batch order, so results merge the same way on every run
            extract = partial(_extract_or_split, known=known, llm=llm)
            for parts in pool.map(extract, wave):
                for part, data, tokens, cost in parts:
                    result.tokens += tokens
                    result.cost_inr += cost
                    _merge(data, part, entities, relations)

    result.entities = list(entities.values())
    result.relations = list(relations.values())
    result.mentions = _mentions(chunks, result.entities, result.relations)
    return result


def _extract_or_split(
    batch: list[Chunk], known: list[GraphEntity], llm: LLM
) -> list[tuple[list[Chunk], dict, int, float]]:
    """Extract one batch; if the answer does not fit in max_tokens, do each half."""
    try:
        data, tokens, cost = _extract_batch(batch, known, llm)
    except LLMTruncatedError:
        if len(batch) == 1:
            raise
        middle = len(batch) // 2
        return [
            *_extract_or_split(batch[:middle], known, llm),
            *_extract_or_split(batch[middle:], known, llm),
        ]
    return [(batch, data, tokens, cost)]


def _merge(
    data: dict,
    batch: list[Chunk],
    entities: dict[str, GraphEntity],
    relations: dict[tuple[str, str, str], GraphRelation],
) -> None:
    """Add one batch's entities and relationships, deduping against earlier ones."""
    for item in data.get("entities", []):
        key = entity_key(item["name"])
        if key and key not in entities:
            entities[key] = GraphEntity(key=key, name=item["name"].strip(), type=item["type"])
    for item in data.get("relationships", []):
        relation = _relation(item, batch, entities)
        if relation is None:
            continue
        triple = (relation.source, relation.relation, relation.target)
        if triple not in relations or relation.confidence > relations[triple].confidence:
            relations[triple] = relation


def _extract_batch(
    batch: list[Chunk], known: list[GraphEntity], llm: LLM
) -> tuple[dict, int, float]:
    numbered = "\n\n".join(quoted(n, chunk.text) for n, chunk in enumerate(batch, start=1))
    known_text = _KNOWN.format(names=", ".join(e.name for e in known[:200])) if known else ""
    prompt = _PROMPT.format(known=known_text, chunks=numbered, data_rule=DATA_RULE)
    response = llm.complete_json(
        [{"role": "user", "content": prompt}],
        _SCHEMA,
        name="graph_extraction",
        max_tokens=settings.extraction_max_tokens,
        reasoning_effort=settings.structured_reasoning_effort,
    )
    return response.data or {}, response.input_tokens + response.output_tokens, response.cost_inr


def _relation(
    item: dict, batch: list[Chunk], entities: dict[str, GraphEntity]
) -> GraphRelation | None:
    """Validate one extracted relationship; None if it is unusable."""
    source, target = entity_key(item["source"]), entity_key(item["target"])
    number = item["chunk"]
    if not (1 <= number <= len(batch)) or source == target:
        return None
    if item["confidence"] < settings.extraction_min_confidence:
        return None
    for key, name in ((source, item["source"]), (target, item["target"])):
        entities.setdefault(key, GraphEntity(key=key, name=name.strip()))  # model forgot it
    relation = re.sub(r"[^A-Z0-9]+", "_", item["relation"].upper()).strip("_") or "RELATED_TO"
    return GraphRelation(
        source=source,
        relation=relation,
        target=target,
        chunk_id=batch[number - 1].id,
        confidence=round(float(item["confidence"]), 2),
    )


def _mentions(
    chunks: list[Chunk], entities: list[GraphEntity], relations: list[GraphRelation]
) -> dict[str, list[str]]:
    """Which entities each chunk mentions: by name match, or by stating a relation."""
    mentions: dict[str, set[str]] = {chunk.id: set() for chunk in chunks}
    for relation in relations:
        mentions[relation.chunk_id].update((relation.source, relation.target))
    for entity in entities:
        pattern = re.compile(rf"\b{re.escape(entity.name)}\b", re.IGNORECASE)
        for chunk in chunks:
            if pattern.search(chunk.text):
                mentions[chunk.id].add(entity.key)
    return {chunk_id: sorted(keys) for chunk_id, keys in mentions.items() if keys}


def _batches(chunks: list[Chunk]) -> list[list[Chunk]]:
    """Group chunks so each LLM call gets about `extraction_batch_chars` of text."""
    batches: list[list[Chunk]] = [[]]
    size = 0
    for chunk in chunks:
        if batches[-1] and size + len(chunk.text) > settings.extraction_batch_chars:
            batches.append([])
            size = 0
        batches[-1].append(chunk)
        size += len(chunk.text)
    return [batch for batch in batches if batch]
