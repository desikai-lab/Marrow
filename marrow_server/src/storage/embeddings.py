import os
import logging
from typing import List, Optional, Dict

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
    _instance: Optional['EmbeddingManager'] = None
    _models: Dict[str, 'TextEmbedding'] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
        return cls._instance

    def _get_model(self, model_name: str) -> Optional['TextEmbedding']:
        """Lazily initializes the specified model."""
        if not HAS_FASTEMBED:
            return None
        
        if model_name not in self._models:
            try:
                logger.info(f"Loading embedding model: {model_name}...")
                self._models[model_name] = TextEmbedding(model_name=model_name)
                logger.info(f"Model {model_name} loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load embedding model {model_name}: {str(e)}")
                return None
        return self._models[model_name]

    def generate_vector(self, text: str, model_name: Optional[str] = None) -> Optional[List[float]]:
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
