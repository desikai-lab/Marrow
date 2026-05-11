import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class ChunkInfo:
    section: str
    start_line: int
    end_line: int
    text: str


class ChunkerStrategy(ABC):
    @abstractmethod
    def chunk(self, content: str, max_chars: int) -> Iterator[ChunkInfo]:
        """Generates chunks from content. max_chars is primarily used for text files."""
        pass


class MarkdownChunker(ChunkerStrategy):
    """Splits Markdown files by ## and ### headers, ignoring headers inside fenced blocks."""

    def chunk(self, content: str, max_chars: int) -> Iterator[ChunkInfo]:
        from tools.utils.markdown_fence import build_fenced_ranges, in_fenced_range
        fenced_ranges = build_fenced_ranges(content)
        # Search for ## and ### headers (level 2 and 3)
        header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        
        matches = []
        for match in header_pattern.finditer(content):
            if not in_fenced_range(match.start(), fenced_ranges):
                matches.append(match)

        if not matches:
            # If no headers found, pass content to TextChunker
            yield from TextChunker().chunk(content, max_chars)
            return

        lines = content.split('\n')
        
        for i, match in enumerate(matches):
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1

            if i < len(matches) - 1:
                end_pos = matches[i+1].start()
                end_line = content[:end_pos].count('\n')
                text = content[start_pos:end_pos].strip()
            else:
                end_line = len(lines)
                text = content[start_pos:].strip()
                
            # section name is the whole match, e.g. "## Title"
            section_name = match.group(0).strip()
            
            yield ChunkInfo(
                section=section_name,
                start_line=start_line,
                end_line=end_line,
                text=text
            )


class TextChunker(ChunkerStrategy):
    """Splits files by empty lines (paragraphs), merging them up to max_chars."""

    def chunk(self, content: str, max_chars: int) -> Iterator[ChunkInfo]:
        if not content.strip():
            return
            
        paragraphs = re.split(r'\n\s*\n', content)
        
        current_chunk_text = ""
        current_start_line = 1
        current_end_line = 0
        chunk_index = 1
        
        lines = content.split('\n')

        def get_line_count(text):
            return text.count('\n') + 1 if text else 0
            
        for i, paragraph in enumerate(paragraphs):
            # Add separator if text is not empty
            addition = ("\n\n" + paragraph) if current_chunk_text else paragraph
            
            # If current chunk is empty OR adding the paragraph stays within limit
            if not current_chunk_text or len(current_chunk_text) + len(addition) <= max_chars:
                current_chunk_text += addition if current_chunk_text else paragraph
                # Line counting. For rough understanding in TextChunker, 
                # we just accumulate lengths. Real start_line/end_line could be calculated 
                # more accurately by traversing source text, but for simplicity we'll use 
                # line counts estimated from paragraphs.
            else:
                # Yield the accumulated chunk
                chunk_lines_len = get_line_count(current_chunk_text)
                current_end_line = current_start_line + chunk_lines_len - 1
                
                yield ChunkInfo(
                    section=f"(root:{chunk_index})",
                    start_line=current_start_line,
                    end_line=current_end_line,
                    text=current_chunk_text.strip()
                )
                chunk_index += 1
                
                # Start a new chunk
                # Estimated start_line for the new chunk
                current_start_line = current_end_line + 2 # +2 for empty separator line
                current_chunk_text = paragraph
                
        if current_chunk_text:
            chunk_lines_len = get_line_count(current_chunk_text)
            current_end_line = current_start_line + chunk_lines_len - 1
            yield ChunkInfo(
                section=f"(root:{chunk_index})" if chunk_index > 1 else "(root)",
                start_line=current_start_line,
                end_line=current_end_line,
                text=current_chunk_text.strip()
            )


class ChunkerFactory:
    _map = {
        ".md": MarkdownChunker(),
        ".txt": TextChunker(),
        ".json": TextChunker(),
    }

    @classmethod
    def get(cls, ext: str) -> ChunkerStrategy:
        return cls._map.get(ext.lower(), TextChunker())
