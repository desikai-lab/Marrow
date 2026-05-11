import os
import pytest
from unittest.mock import patch, MagicMock


def test_sentence_transformer_called_with_local_files_only():
    """
    Ensures LazyEncoder passes local_files_only=True to SentenceTransformer,
    preventing network calls to huggingface.co on every model load.
    """
    mock_model = MagicMock()
    mock_st_class = MagicMock(return_value=mock_model)

    with patch("sentence_transformers.SentenceTransformer", mock_st_class):
        from src.embedding.lazy_model import LazyEncoder
        enc = LazyEncoder()
        enc.__enter__()

    mock_st_class.assert_called_once_with("BAAI/bge-small-en-v1.5", local_files_only=True)
