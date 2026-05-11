import pytest
from src.embedding import LazyEncoder

def test_lazy_encoder_context():
    # Model should not exist before context
    encoder = LazyEncoder()
    assert encoder._model is None
    
    with encoder as enc:
        assert enc._model is not None
        
        # Test basic dummy batch array
        skeletons = [
            "public class Dummy { /* ... implementation */ }",
            "def foo(): pass"
        ]
        
        embeddings = enc.encode(skeletons)
        
        # BAAI/bge-small-en-v1.5 outputs vectors of size 384
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384
        assert isinstance(embeddings[0][0], float)

    # After context closes, _model must be destroyed entirely
    assert encoder._model is None
