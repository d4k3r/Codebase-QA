"""Small code-aware query terms for PostgreSQL full-text retrieval."""

import re


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[_.:/-][A-Za-z0-9]+)*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_PARTS = re.compile(r"[A-Za-z0-9]+")
_QUESTION_WORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
     "from", "how", "in", "is", "it", "of", "on", "or", "the", "then", "these",
     "this", "to", "what", "when", "where", "which", "who", "why", "with"}
)


def lexical_terms(query: str) -> tuple[str, ...]:
    """Keep complete code identifiers and useful subtokens; drop question glue.

    Terms are deliberately restricted to letters/digits/underscores so joining
    them into a PostgreSQL OR tsquery cannot introduce tsquery operators.
    """

    terms: dict[str, None] = {}
    for token in _TOKEN.findall(query):
        full = token.lower()
        if re.fullmatch(r"[A-Za-z0-9_]+", token) and full not in _QUESTION_WORDS:
            terms[full] = None
        for part in _PARTS.findall(token):
            normal = part.lower()
            if len(normal) > 1 and normal not in _QUESTION_WORDS:
                terms[normal] = None
        for part in _PARTS.findall(_CAMEL.sub(" ", token)):
            normal = part.lower()
            if len(normal) > 1 and normal not in _QUESTION_WORDS:
                terms[normal] = None
    return tuple(terms)[:32]


def exact_metadata_terms(query: str) -> tuple[str, ...]:
    """Recognize code-shaped complete tokens for modest metadata-only boosts."""

    return tuple(dict.fromkeys(
        token.lower() for token in _TOKEN.findall(query)
        if any(mark in token for mark in "_./:-")
        or bool(_CAMEL.search(token))
        or (len(token) > 1 and token.isupper())
    ))[:16]
