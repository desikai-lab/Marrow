import logging
import os
from typing import Optional

# Logging setup
logger = logging.getLogger("marrow.embeddings")

try:
    from fastembed import TextEmbedding

    HAS_FASTEMBED = True
except ImportError:
    logger.warning("fastembed library not found. Semantic search will be disabled.")
    HAS_FASTEMBED = False


class EmbeddingManager:
    """
    Manages embedding generation for tasks.
    Uses the Singleton pattern to cache the model in memory.
    """

    _instance: Optional["EmbeddingManager"] = None
    _models: dict[str, "TextEmbedding"] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self, model_name: str) -> Optional["TextEmbedding"]:
        """Lazily initializes the specified model.

        If FASTEMBED_CACHE_DIR is configured, the model is stored there so it
        survives container restarts (Docker).  When unset (local / Windows dev)
        fastembed chooses its own OS-appropriate default — no behaviour change.
        """
        if not HAS_FASTEMBED:
            return None

        if model_name not in self._models:
            try:
                from config import FASTEMBED_CACHE_DIR

                kwargs: dict = {"model_name": model_name}
                if FASTEMBED_CACHE_DIR:
                    os.makedirs(FASTEMBED_CACHE_DIR, exist_ok=True)
                    kwargs["cache_dir"] = FASTEMBED_CACHE_DIR
                    logger.info(
                        f"Loading embedding model: {model_name} "
                        f"(cache_dir={FASTEMBED_CACHE_DIR})..."
                    )
                else:
                    logger.info(f"Loading embedding model: {model_name} (default cache)...")

                self._models[model_name] = TextEmbedding(**kwargs)
                logger.info(f"Model {model_name} loaded successfully.")
            except Exception as e:
                cache_hint = (
                    f" (cache_dir={FASTEMBED_CACHE_DIR})"
                    if "FASTEMBED_CACHE_DIR" in dir() and FASTEMBED_CACHE_DIR
                    else ""
                )
                logger.error(
                    f"Failed to load embedding model {model_name}{cache_hint}: {e}. "
                    "Artifact indexing will be skipped until the model loads successfully."
                )
                return None
        return self._models[model_name]

    def generate_vector(self, text: str, model_name: str | None = None) -> list[float] | None:
        """
        Generates a vector for the given text using the specified model.
        If model_name is not provided, EMBEDDING_MODEL_NAME from config is used.
        """
        if model_name is None:
            from config import EMBEDDING_MODEL_NAME

            model_name = EMBEDDING_MODEL_NAME

        model = self._get_model(model_name)
        if not model:
            return None

        if not text or not text.strip():
            return None

        try:
            # Text cleanup and normalization (fastembed-specific preprocessing)
            clean_text = " ".join(text.split()).lower()

            # fastembed.embed returns an iterator
            embeddings = list(model.embed([clean_text]))
            if embeddings:
                return embeddings[0].tolist()
        except Exception as e:
            logger.error(f"Error generating embedding with {model_name}: {str(e)}")
            return None

        return None


# Global singleton instance for convenient access
embeddings_manager = EmbeddingManager()
