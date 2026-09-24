import json
import os
from pathlib import Path

import numpy as np
import pytest

from src.embedding.lazy_model import LazyEncoder


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    arr_a = np.array(a, dtype=np.float32)
    arr_b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))


@pytest.fixture
def drift_fixtures():
    repo_root = _get_repo_root()
    fixtures_dir = repo_root / "tests" / "fixtures" / "embedding_drift"
    code_path = fixtures_dir / "corpus_code.json"
    queries_path = fixtures_dir / "corpus_queries.json"
    vectors_path = fixtures_dir / "baseline_vectors_code.json"

    assert code_path.exists(), f"Corpus code file missing at {code_path}"
    assert vectors_path.exists(), f"Baseline vectors file missing at {vectors_path}"

    with open(code_path, encoding="utf-8") as f:
        code_snippets = json.load(f)

    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    with open(vectors_path, encoding="utf-8") as f:
        baseline_data = json.load(f)

    return {
        "code_snippets": code_snippets,
        "queries": queries,
        "baseline_code_vectors": baseline_data["code_vectors"],
        "baseline_query_vectors": baseline_data["query_vectors"],
    }


def test_embed_fixed_corpus_meets_cosine_tolerance(drift_fixtures):
    code_snippets = drift_fixtures["code_snippets"]
    baseline_code_vectors = drift_fixtures["baseline_code_vectors"]

    # Ensure offline mode during drift gate execution
    os.environ["HF_HUB_OFFLINE"] = "1"

    with LazyEncoder() as enc:
        current_code_vectors = enc.encode(code_snippets)

    assert len(current_code_vectors) == len(baseline_code_vectors)

    similarities = [
        _cosine_similarity(curr, base)
        for curr, base in zip(current_code_vectors, baseline_code_vectors, strict=True)
    ]

    mean_sim = float(np.mean(similarities))
    min_sim = float(np.min(similarities))

    # ADR-0052 Tolerances: mean cosine >= 0.999, min cosine >= 0.99
    assert mean_sim >= 0.999, f"Mean cosine similarity ({mean_sim:.6f}) fell below 0.999 tolerance threshold"
    assert min_sim >= 0.99, f"Minimum cosine similarity ({min_sim:.6f}) fell below 0.99 tolerance threshold"


def test_embed_fixed_queries_meets_cosine_tolerance(drift_fixtures):
    queries = drift_fixtures["queries"]
    baseline_query_vectors = drift_fixtures["baseline_query_vectors"]

    os.environ["HF_HUB_OFFLINE"] = "1"

    with LazyEncoder() as enc:
        current_query_vectors = enc.encode(queries)

    assert len(current_query_vectors) == len(baseline_query_vectors)

    similarities = [
        _cosine_similarity(curr, base)
        for curr, base in zip(current_query_vectors, baseline_query_vectors, strict=True)
    ]

    mean_sim = float(np.mean(similarities))
    min_sim = float(np.min(similarities))

    assert mean_sim >= 0.999, f"Mean query cosine similarity ({mean_sim:.6f}) fell below 0.999 threshold"
    assert min_sim >= 0.99, f"Min query cosine similarity ({min_sim:.6f}) fell below 0.99 threshold"
