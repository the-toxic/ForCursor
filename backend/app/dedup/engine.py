from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.dedup.normalize import normalize_text, significant_tokens, text_hash


@dataclass(frozen=True, slots=True)
class Candidate:
    item_id: int
    content_hash: str
    raw_text: str


@dataclass(frozen=True, slots=True)
class DedupDecision:
    is_duplicate: bool
    similarity: float
    matched_item_id: int | None
    reason: str


def _cosine(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_counts = Counter(left)
    right_counts = Counter(right)
    shared = set(left_counts) & set(right_counts)
    dot = sum(left_counts[token] * right_counts[token] for token in shared)
    left_norm = sum(value * value for value in left_counts.values()) ** 0.5
    right_norm = sum(value * value for value in right_counts.values()) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def score_pair(left_text: str, right_text: str) -> float:
    left_norm = normalize_text(left_text)
    right_norm = normalize_text(right_text)
    left_tokens = significant_tokens(left_text)
    right_tokens = significant_tokens(right_text)
    left_sig = " ".join(left_tokens)
    right_sig = " ".join(right_tokens)

    token_set = fuzz.token_set_ratio(left_norm, right_norm) / 100
    token_sort = fuzz.token_sort_ratio(left_norm, right_norm) / 100
    weighted = fuzz.WRatio(left_norm, right_norm) / 100
    stemmed_set = fuzz.token_set_ratio(left_sig, right_sig) / 100 if left_sig and right_sig else 0.0
    cosine_score = _cosine(left_tokens, right_tokens)
    jaccard_score = _jaccard(left_tokens, right_tokens)

    left_numbers = {token for token in left_norm.split() if token.isdigit()}
    right_numbers = {token for token in right_norm.split() if token.isdigit()}
    number_bonus = 0.1 if left_numbers and left_numbers == right_numbers else 0.0

    return min(
        1.0,
        max(token_set, token_sort, weighted, stemmed_set, cosine_score, jaccard_score) + number_bonus,
    )


def decide(text: str, recent: list[Candidate], threshold: float) -> DedupDecision:
    incoming_hash = text_hash(text)
    for candidate in recent:
        if candidate.content_hash == incoming_hash:
            return DedupDecision(
                is_duplicate=True,
                similarity=1.0,
                matched_item_id=candidate.item_id,
                reason="exact_hash",
            )

    best_score = 0.0
    best_id: int | None = None
    for candidate in recent:
        score = score_pair(text, candidate.raw_text)
        if score > best_score:
            best_score = score
            best_id = candidate.item_id

    if best_id is not None and best_score >= threshold:
        return DedupDecision(
            is_duplicate=True,
            similarity=round(best_score, 4),
            matched_item_id=best_id,
            reason="similarity",
        )

    return DedupDecision(
        is_duplicate=False,
        similarity=round(best_score, 4),
        matched_item_id=best_id,
        reason="unique",
    )
