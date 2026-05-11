import gc
import torch
from typing import List

class LazyEncoder:
    """
    Context manager that loads the Heavy Neural Network into RAM/VRAM only when opened,
    and violently garbage collects it upon closing to prevent memory starvation.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"): 
        self.model_name = model_name
        self._model = None

    def __enter__(self):
        from sentence_transformers import SentenceTransformer
        # sentence-transformers automatically pushes the model to GPU if CUDA is available.
        # local_files_only=True prevents huggingface_hub from making ANY network calls
        # (version-check HEADs, tree GETs, metadata fetches) when the model is already cached.
        # To download the model on a new machine for the first time, temporarily remove
        # local_files_only=True (or unset HF_HUB_OFFLINE), run the worker once, then restore.
        self._model = SentenceTransformer(self.model_name, local_files_only=True)
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

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not self._model:
            raise RuntimeError("Model must be loaded inside `with LazyEncoder() as enc:` context.")
        
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        # Ensure primitive Python floats for serialization
        return [arr.tolist() for arr in embeddings]
