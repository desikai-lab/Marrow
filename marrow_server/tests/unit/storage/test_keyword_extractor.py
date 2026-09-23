import pytest
from unittest.mock import MagicMock
from storage.artifact_chunker import ChunkInfo

# Helper
def _make_chunk(text: str, section: str = "") -> ChunkInfo:
    c = MagicMock(spec=ChunkInfo)
    c.text = text
    c.section = section
    c.start_line = 1
    c.end_line = 10
    return c


def test_identifierTerms_alphanumericMix_returnsAsPriority0():
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("Fix TD4000238 and SB2 today")
    assert "td4000238" in result
    assert "sb2" in result


def test_identifierTerms_camelCase_returnsAsPriority2():
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("Use MemGPT or arXiv references")
    assert "memgpt" in result
    assert "arxiv" in result


def test_identifierTerms_capitalizedSentenceStart_notReturned():
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("The quick fox does things")
    assert "the" not in result
    assert "does" not in result


def test_identifierTerms_acronymWithin2to6chars_returned():
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("Use RRF and ADR for BESI metrics")
    assert "rrf" in result
    assert "adr" in result
    assert "besi" in result


def test_identifierTerms_acronymLongerThan6chars_notReturned():
    """Mitigation for Cyrillic false positives: max acronym length is now 6."""
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("ABCDEFGH is a long acronym")
    assert "abcdefgh" not in result


def test_identifierTerms_emphasisWords_notReturned():
    from storage.keyword_extractor import identifier_terms
    result = identifier_terms("NOT ALWAYS NEVER MUST ONLY ALSO")
    assert not any(w in result for w in ["not", "always", "never", "must", "only", "also"])


def test_isStub_bodyUnder3Tokens_returnsTrue():
    from storage.keyword_extractor import is_stub
    assert is_stub("one two") is True


def test_isStub_bodyWith3OrMoreTokens_returnsFalse():
    from storage.keyword_extractor import is_stub
    assert is_stub("one two three") is False


def test_extractiveKeywordExtractor_stubChunk_returnsEmptyKept():
    from storage.keyword_extractor import ExtractiveKeywordExtractor
    chunk = _make_chunk(text="ok hi", section="")
    results = ExtractiveKeywordExtractor().extract_detailed([chunk])
    assert results[0].kept == []


def test_extractiveKeywordExtractor_richChunk_returnsKeywords():
    from storage.keyword_extractor import ExtractiveKeywordExtractor
    chunk = _make_chunk(
        text="TD4000238 is blocked by F4000249. Use MemGPT via arXiv:2310.08560",
        section=""
    )
    results = ExtractiveKeywordExtractor().extract_detailed([chunk])
    assert len(results[0].kept) > 0
    assert "td4000238" in results[0].kept


def test_extractiveKeywordExtractor_capAt20Terms():
    from storage.keyword_extractor import ExtractiveKeywordExtractor
    body = " ".join(f"ID{i}" for i in range(25))
    chunk = _make_chunk(text=body, section="")
    results = ExtractiveKeywordExtractor().extract_detailed([chunk])
    assert len(results[0].kept) <= 20


def test_keywordExtractorProtocol_isSatisfiedByExtractiveKeywordExtractor():
    from storage.keyword_extractor import ExtractiveKeywordExtractor
    extractor = ExtractiveKeywordExtractor()
    assert hasattr(extractor, "extract_detailed")
