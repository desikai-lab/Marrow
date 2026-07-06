from unittest.mock import MagicMock, patch

import numpy as np
from src.embedding import LazyEncoder


def test_lazy_encoder_context():
    # Model should not exist before context
    encoder = LazyEncoder()
    assert encoder._model is None

    fake_model = MagicMock()
    # SentenceTransformer.encode returns numpy arrays which LazyEncoder.encode converts to list
    fake_model.encode.return_value = [
        np.array([0.1] * 384, dtype="float32"),
        np.array([0.2] * 384, dtype="float32"),
    ]

    # LazyEncoder uses a lazy import: `from sentence_transformers import SentenceTransformer`
    # inside __enter__, so we must patch the class on the sentence_transformers module itself,
    # not on embedding.lazy_model (which has no module-level reference to patch).
    with patch(
        "sentence_transformers.SentenceTransformer",
        return_value=fake_model,
    ):
        with encoder as enc:
            assert enc._model is not None

            # Test basic dummy batch array
            skeletons = ["public class Dummy { /* ... implementation */ }", "def foo(): pass"]

            embeddings = enc.encode(skeletons)

            # BAAI/bge-small-en-v1.5 outputs vectors of size 384
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 384
            assert isinstance(embeddings[0][0], float)

    # After context closes, _model must be destroyed entirely
    assert encoder._model is None
