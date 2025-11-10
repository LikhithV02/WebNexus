"""
Markdown Structure Parser

Parses markdown content into structural elements for intelligent chunking.
Identifies headers, code blocks, tables, lists, and paragraphs.
"""

import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ElementType(Enum):
    """Types of markdown elements"""
    HEADER = "header"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    LIST = "list"
    PARAGRAPH = "paragraph"
    BLANK = "blank"


@dataclass
class MarkdownElement:
    """
    Represents a structural element in markdown document.

    Attributes:
        type: Type of element (header, code_block, table, list, paragraph)
        content: The actual text content
        start_pos: Start position in original document
        end_pos: End position in original document
        level: Header level (1-6) or nesting level for lists, None for others
        metadata: Additional metadata (language for code blocks, etc.)
    """
    type: ElementType
    content: str
    start_pos: int
    end_pos: int
    level: Optional[int] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MarkdownParser:
    """
    Parse markdown content into structural elements.

    Handles:
    - Headers (# ## ### etc.)
    - Fenced code blocks (```)
    - Tables (| ... |)
    - Lists (ordered and unordered)
    - Paragraphs (regular text)
    """

    def __init__(self):
        """Initialize markdown parser with regex patterns"""

        # Header pattern: # Header or ## Header
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

        # Fenced code block pattern: ```language\ncode\n```
        self.code_block_pattern = re.compile(
            r'^```(\w*)\n(.*?)^```\s*$',
            re.MULTILINE | re.DOTALL
        )

        # Table pattern: | col1 | col2 | (at least 2 rows including separator)
        self.table_pattern = re.compile(
            r'(?:^\|.+\|\s*\n)+^\|[\s\-:|]+\|\s*\n(?:^\|.+\|\s*\n)*',
            re.MULTILINE
        )

        # List patterns
        self.unordered_list_pattern = re.compile(r'^([\s]*)[-*+]\s+(.+)$', re.MULTILINE)
        self.ordered_list_pattern = re.compile(r'^([\s]*)\d+\.\s+(.+)$', re.MULTILINE)

        # Paragraph pattern: non-empty lines not matching above patterns
        self.blank_line_pattern = re.compile(r'^\s*$', re.MULTILINE)

    def parse(self, content: str) -> List[MarkdownElement]:
        """
        Parse markdown content into structural elements.

        Args:
            content: Markdown text to parse

        Returns:
            List of MarkdownElement objects in document order
        """
        if not content or not content.strip():
            return []

        elements = []

        # Track which positions are already claimed by special elements
        claimed_positions = set()

        # 1. Extract code blocks (highest priority - must be preserved intact)
        for match in self.code_block_pattern.finditer(content):
            start, end = match.span()
            language = match.group(1) or "text"
            code_content = match.group(2)

            element = MarkdownElement(
                type=ElementType.CODE_BLOCK,
                content=match.group(0),
                start_pos=start,
                end_pos=end,
                metadata={"language": language, "code": code_content}
            )
            elements.append(element)

            # Mark positions as claimed
            claimed_positions.update(range(start, end))

        # 2. Extract tables (high priority)
        for match in self.table_pattern.finditer(content):
            start, end = match.span()

            # Skip if position already claimed by code block
            if any(pos in claimed_positions for pos in range(start, end)):
                continue

            element = MarkdownElement(
                type=ElementType.TABLE,
                content=match.group(0),
                start_pos=start,
                end_pos=end,
                metadata={"rows": match.group(0).count('\n')}
            )
            elements.append(element)

            # Mark positions as claimed
            claimed_positions.update(range(start, end))

        # 3. Extract headers
        for match in self.header_pattern.finditer(content):
            start, end = match.span()

            # Skip if position already claimed
            if any(pos in claimed_positions for pos in range(start, end)):
                continue

            level = len(match.group(1))  # Count # characters
            title = match.group(2).strip()

            element = MarkdownElement(
                type=ElementType.HEADER,
                content=match.group(0),
                start_pos=start,
                end_pos=end,
                level=level,
                metadata={"title": title}
            )
            elements.append(element)

            # Mark positions as claimed
            claimed_positions.update(range(start, end))

        # 4. Extract lists (both ordered and unordered)
        list_elements = self._extract_lists(content, claimed_positions)
        elements.extend(list_elements)

        # Update claimed positions for lists
        for elem in list_elements:
            claimed_positions.update(range(elem.start_pos, elem.end_pos))

        # 5. Extract remaining content as paragraphs
        paragraph_elements = self._extract_paragraphs(content, claimed_positions)
        elements.extend(paragraph_elements)

        # Sort elements by start position to maintain document order
        elements.sort(key=lambda x: x.start_pos)

        logger.info(f"Parsed {len(elements)} markdown elements")
        return elements

    def _extract_lists(self, content: str, claimed_positions: set) -> List[MarkdownElement]:
        """
        Extract list blocks from content.

        Groups consecutive list items into single list elements.
        """
        elements = []
        lines = content.split('\n')
        current_list_lines = []
        list_start_pos = 0
        current_pos = 0
        list_type = None  # 'ordered' or 'unordered'

        for line_idx, line in enumerate(lines):
            line_start = current_pos
            line_end = current_pos + len(line)

            # Check if this line is claimed
            is_claimed = any(pos in claimed_positions for pos in range(line_start, line_end))

            # Check if line is a list item
            is_unordered = self.unordered_list_pattern.match(line)
            is_ordered = self.ordered_list_pattern.match(line)
            is_list_item = is_unordered or is_ordered

            if is_list_item and not is_claimed:
                # Determine list type
                current_type = 'unordered' if is_unordered else 'ordered'

                # If starting a new list or continuing same type
                if not current_list_lines:
                    list_start_pos = line_start
                    list_type = current_type
                    current_list_lines.append(line)
                elif list_type == current_type:
                    current_list_lines.append(line)
                else:
                    # Different list type, save current list and start new one
                    if current_list_lines:
                        self._save_list_element(
                            elements, current_list_lines, list_start_pos,
                            current_pos - 1, list_type
                        )
                    list_start_pos = line_start
                    list_type = current_type
                    current_list_lines = [line]
            else:
                # Not a list item, save accumulated list if any
                if current_list_lines:
                    self._save_list_element(
                        elements, current_list_lines, list_start_pos,
                        current_pos - 1, list_type
                    )
                    current_list_lines = []
                    list_type = None

            current_pos = line_end + 1  # +1 for newline

        # Save final list if any
        if current_list_lines:
            self._save_list_element(
                elements, current_list_lines, list_start_pos,
                current_pos - 1, list_type
            )

        return elements

    def _save_list_element(
        self, elements: List[MarkdownElement], lines: List[str],
        start_pos: int, end_pos: int, list_type: str
    ):
        """Helper to save a list element"""
        content = '\n'.join(lines)
        element = MarkdownElement(
            type=ElementType.LIST,
            content=content,
            start_pos=start_pos,
            end_pos=end_pos,
            metadata={"list_type": list_type, "item_count": len(lines)}
        )
        elements.append(element)

    def _extract_paragraphs(self, content: str, claimed_positions: set) -> List[MarkdownElement]:
        """
        Extract paragraphs from unclaimed content.

        Paragraphs are continuous blocks of text separated by blank lines.
        """
        elements = []
        lines = content.split('\n')
        current_paragraph_lines = []
        paragraph_start_pos = 0
        current_pos = 0

        for line in lines:
            line_start = current_pos
            line_end = current_pos + len(line)

            # Check if line is claimed
            is_claimed = any(pos in claimed_positions for pos in range(line_start, line_end))

            # Check if line is blank
            is_blank = self.blank_line_pattern.match(line) is not None

            if not is_claimed and not is_blank:
                # Part of current paragraph
                if not current_paragraph_lines:
                    paragraph_start_pos = line_start
                current_paragraph_lines.append(line)
            else:
                # End of paragraph (blank line or claimed content)
                if current_paragraph_lines:
                    content_text = '\n'.join(current_paragraph_lines)
                    element = MarkdownElement(
                        type=ElementType.PARAGRAPH,
                        content=content_text,
                        start_pos=paragraph_start_pos,
                        end_pos=current_pos - 1,
                        metadata={"line_count": len(current_paragraph_lines)}
                    )
                    elements.append(element)
                    current_paragraph_lines = []

            current_pos = line_end + 1  # +1 for newline

        # Save final paragraph if any
        if current_paragraph_lines:
            content_text = '\n'.join(current_paragraph_lines)
            element = MarkdownElement(
                type=ElementType.PARAGRAPH,
                content=content_text,
                start_pos=paragraph_start_pos,
                end_pos=current_pos - 1,
                metadata={"line_count": len(current_paragraph_lines)}
            )
            elements.append(element)

        return elements

    def get_header_hierarchy(self, elements: List[MarkdownElement]) -> List[Tuple[int, str, int]]:
        """
        Extract header hierarchy from elements.

        Args:
            elements: List of markdown elements

        Returns:
            List of tuples: (level, title, position)
        """
        headers = []
        for elem in elements:
            if elem.type == ElementType.HEADER:
                headers.append((
                    elem.level,
                    elem.metadata.get("title", ""),
                    elem.start_pos
                ))

        return headers


# Global parser instance
markdown_parser = MarkdownParser()
