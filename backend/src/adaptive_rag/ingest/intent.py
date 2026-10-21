"""Step 2: suggest what the uploader will mostly ask, pre-filled from the scan (FR12-FR14)."""

from adaptive_rag.config import settings
from adaptive_rag.schemas import DocumentProfile, Intent

INTENT_LABELS: dict[Intent, str] = {
    "facts": "Look up facts or policies",
    "exact_terms": "Find exact terms, IDs, or codes",
    "connections": "Understand how things connect or depend on each other",
    "compare": "Compare or summarize across sections",
}


def many_relationships(profile: DocumentProfile) -> bool:
    """PRD FR16: dense relationships in the sample, or many cross-refs AND relation phrases,
    or relation phrases so dense they count alone (relationships written as sentences)."""
    return (
        profile.relationship_density > settings.many_relationships_density
        or (
            profile.cross_ref_rate > settings.many_relationships_cross_ref_rate
            and profile.relationship_phrase_rate > settings.many_relationships_phrase_rate
        )
        or profile.relationship_phrase_rate > settings.many_relationships_phrase_only_rate
    )


def suggest_intents(profile: DocumentProfile) -> list[Intent]:
    """Pre-select the intents the scan points to; 'facts' is always useful."""
    suggested: list[Intent] = ["facts"]
    if (
        profile.identifier_density >= settings.exact_terms_identifier_density
        or profile.table_share >= settings.small_plain_max_table_share
    ):
        suggested.append("exact_terms")
    if many_relationships(profile):
        suggested.append("connections")
        if profile.cross_ref_rate > settings.many_relationships_cross_ref_rate:
            suggested.append("compare")
    return suggested
