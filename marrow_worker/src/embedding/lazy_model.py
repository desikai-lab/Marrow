import gc
import logging
import os

import torch
from config import EMBEDDING_MODEL_CODE, EMBEDDING_MODEL_REVISION

logger = logging.getLogger(__name__)



class LazyEncoder:
    """
    Context manager that loads the Heavy Neural Network into RAM/VRAM only when opened,
    and violently garbage collects it upon closing to prevent memory starvation.
    """

    def __init__(self, model_name: str | None = None, revision: str | None = None):
        if model_name is None:
            model_name = EMBEDDING_MODEL_CODE
        if revision is None:
            revision = EMBEDDING_MODEL_REVISION

        self.model_name = model_name
        self.revision = revision
        self._model = None




    def __enter__(self):
        import sentence_transformers
        from sentence_transformers import SentenceTransformer
        import transformers

        # local_files_only is controlled by HF_HUB_OFFLINE env var.
        # Default (0): allows download on first run into the shared marrow-hf-cache volume.
        # Set to "1" after first successful download to prevent any network calls.
        local_files_only = os.getenv("HF_HUB_OFFLINE", "0") == "1"

        logger.info(
            "Loading embedding model '%s' (revision=%s) [sentence_transformers=%s, torch=%s, transformers=%s]",
            self.model_name,
            self.revision,
            getattr(sentence_transformers, "__version__", "unknown"),
            getattr(torch, "__version__", "unknown"),
            getattr(transformers, "__version__", "unknown"),
        )

        kwargs = {
            "local_files_only": local_files_only,
        }
        if self.revision:
            kwargs["revision"] = self.revision

        self._model = SentenceTransformer(self.model_name, **kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._model is not None:
            del self._model
            self._model = None

        # System RAM sweep
        gc.collect()

        # VRAM sweep (GPU) - crucial to avoid memory leaking the IDE/OS
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self._model:
            raise RuntimeError("Model must be loaded inside `with LazyEncoder() as enc:` context.")

        embeddings = self._model.encode(texts, convert_to_numpy=True)
        # Ensure primitive Python floats for serialization
        return [arr.tolist() for arr in embeddings]

