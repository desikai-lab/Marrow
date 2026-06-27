import os
from unittest.mock import MagicMock, patch


def test_sentence_transformer_called_with_local_files_only_false_by_default():
    """
    When HF_HUB_OFFLINE is not set, local_files_only must be False
    so the model can be downloaded on a fresh container.
    """
    mock_model = MagicMock()
    mock_st_class = MagicMock(return_value=mock_model)

    env = {k: v for k, v in os.environ.items() if k != "HF_HUB_OFFLINE"}
    with patch.dict(os.environ, env, clear=True):
        with patch("sentence_transformers.SentenceTransformer", mock_st_class):
            from src.embedding.lazy_model import LazyEncoder
            enc = LazyEncoder()
            enc.__enter__()

    mock_st_class.assert_called_once_with("BAAI/bge-small-en-v1.5", local_files_only=False)


def test_sentence_transformer_called_with_local_files_only_true_when_offline():
    """
    When HF_HUB_OFFLINE=1, local_files_only must be True
    to prevent any network calls.
    """
    mock_model = MagicMock()
    mock_st_class = MagicMock(return_value=mock_model)

    with patch.dict(os.environ, {"HF_HUB_OFFLINE": "1"}):
        with patch("sentence_transformers.SentenceTransformer", mock_st_class):
            from src.embedding.lazy_model import LazyEncoder
            enc = LazyEncoder()
            enc.__enter__()

    mock_st_class.assert_called_once_with("BAAI/bge-small-en-v1.5", local_files_only=True)


def test_lazy_encoder_reads_model_name_from_env():
    """
    EMBEDDING_MODEL_CODE env var must be used as the default model name.
    """
    mock_model = MagicMock()
    mock_st_class = MagicMock(return_value=mock_model)

    with patch.dict(os.environ, {"EMBEDDING_MODEL_CODE": "custom/model", "HF_HUB_OFFLINE": "0"}):
        with patch("sentence_transformers.SentenceTransformer", mock_st_class):
            from src.embedding.lazy_model import LazyEncoder
            enc = LazyEncoder()
            enc.__enter__()

    mock_st_class.assert_called_once_with("custom/model", local_files_only=False)
