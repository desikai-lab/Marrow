import json
from pathlib import Path
import sys

# Ensure marrow_worker src is on PYTHONPATH
repo_root = Path(__file__).resolve().parents[3]
worker_src = repo_root / "marrow_worker" / "src"
sys.path.insert(0, str(worker_src))


from embedding.lazy_model import LazyEncoder  # noqa: E402



def generate_baseline():
    fixtures_dir = Path(__file__).parent
    code_path = fixtures_dir / "corpus_code.json"
    queries_path = fixtures_dir / "corpus_queries.json"
    vectors_path = fixtures_dir / "baseline_vectors_code.json"

    with open(code_path, encoding="utf-8") as f:
        code_snippets = json.load(f)

    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    with LazyEncoder("BAAI/bge-small-en-v1.5") as enc:
        code_vectors = enc.encode(code_snippets)
        query_vectors = enc.encode(queries)

    output_data = {
        "model_name": "BAAI/bge-small-en-v1.5",
        "code_vectors": code_vectors,
        "query_vectors": query_vectors,
    }

    with open(vectors_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully generated baseline vectors: {vectors_path}")


if __name__ == "__main__":
    generate_baseline()
