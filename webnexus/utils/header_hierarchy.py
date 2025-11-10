"""
Header Hierarchy Analyzer

Builds and analyzes header hierarchy for markdown documents.
Used to determine if chunks are under the same logical section.
"""

import logging
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field

from .markdown_parser import MarkdownElement, ElementType

logger = logging.getLogger(__name__)


@dataclass
class HeaderNode:
    """
    Represents a header node in the document hierarchy tree.

    Attributes:
        level: Header level (1-6)
        title: Header title/text
        start_pos: Start position in document
        end_pos: End position in document (where this section ends)
        parent: Parent header node
        children: Child header nodes
        elements: Elements belonging to this section
    """
    level: int
    title: str
    start_pos: int
    end_pos: Optional[int] = None
    parent: Optional['HeaderNode'] = None
    children: List['HeaderNode'] = field(default_factory=list)
    elements: List[MarkdownElement] = field(default_factory=list)

    def get_path(self) -> List[str]:
        """Get hierarchical path from root to this node"""
        path = []
        node = self
        while node:
            path.insert(0, f"H{node.level}:{node.title}")
            node = node.parent
        return path

    def get_depth(self) -> int:
        """Get depth of this node in the tree"""
        depth = 0
        node = self.parent
        while node:
            depth += 1
            node = node.parent
        return depth

    def is_ancestor_of(self, other: 'HeaderNode') -> bool:
        """Check if this node is an ancestor of another node"""
        node = other.parent
        while node:
            if node == self:
                return True
            node = node.parent
        return False

    def is_descendant_of(self, other: 'HeaderNode') -> bool:
        """Check if this node is a descendant of another node"""
        return other.is_ancestor_of(self)

    def get_common_ancestor(self, other: 'HeaderNode') -> Optional['HeaderNode']:
        """Find the lowest common ancestor with another node"""
        # Get paths from root to each node
        self_path = []
        node = self
        while node:
            self_path.insert(0, node)
            node = node.parent

        other_path = []
        node = other
        while node:
            other_path.insert(0, node)
            node = node.parent

        # Find common ancestor
        common_ancestor = None
        for self_node, other_node in zip(self_path, other_path):
            if self_node == other_node:
                common_ancestor = self_node
            else:
                break

        return common_ancestor

    def __repr__(self) -> str:
        return f"HeaderNode(H{self.level}: {self.title}, children={len(self.children)})"


class HierarchyAnalyzer:
    """
    Analyzes and manages header hierarchy in markdown documents.

    Builds a tree structure from headers and provides methods to:
    - Check if elements/chunks are under the same hierarchy
    - Find sections and subsections
    - Determine header relationships
    """

    def __init__(self):
        """Initialize hierarchy analyzer"""
        self.root: Optional[HeaderNode] = None
        self.headers: List[HeaderNode] = []
        self.position_map: Dict[int, HeaderNode] = {}  # Maps start position to header

    def build_tree(self, elements: List[MarkdownElement]) -> Optional[HeaderNode]:
        """
        Build header hierarchy tree from markdown elements.

        Args:
            elements: List of markdown elements (must be sorted by position)

        Returns:
            Root node of the hierarchy tree
        """
        if not elements:
            return None

        # Create a virtual root node at level 0
        self.root = HeaderNode(
            level=0,
            title="[Document Root]",
            start_pos=0,
            end_pos=len(max(elements, key=lambda e: e.end_pos).content) if elements else 0
        )

        self.headers = []
        self.position_map = {}

        # Extract headers in document order
        headers = [elem for elem in elements if elem.type == ElementType.HEADER]

        if not headers:
            # No headers, everything belongs to root
            self.root.elements = elements
            return self.root

        # Build tree structure
        current_stack: List[HeaderNode] = [self.root]

        for i, header_elem in enumerate(headers):
            # Create header node
            header_node = HeaderNode(
                level=header_elem.level,
                title=header_elem.metadata.get("title", ""),
                start_pos=header_elem.start_pos,
                end_pos=None  # Will be set later
            )

            # Find parent in stack (last header with level < current level)
            while len(current_stack) > 1 and current_stack[-1].level >= header_elem.level:
                current_stack.pop()

            parent = current_stack[-1]
            header_node.parent = parent
            parent.children.append(header_node)

            # Add to stack
            current_stack.append(header_node)

            # Add to tracking lists
            self.headers.append(header_node)
            self.position_map[header_elem.start_pos] = header_node

        # Set end positions for each header section
        for i, header_node in enumerate(self.headers):
            if i < len(self.headers) - 1:
                # End position is start of next header at same or higher level
                next_idx = i + 1
                while next_idx < len(self.headers):
                    if self.headers[next_idx].level <= header_node.level:
                        header_node.end_pos = self.headers[next_idx].start_pos - 1
                        break
                    next_idx += 1

                if header_node.end_pos is None:
                    # No next header at same/higher level, goes to end of document
                    header_node.end_pos = elements[-1].end_pos if elements else header_node.start_pos
            else:
                # Last header goes to end of document
                header_node.end_pos = elements[-1].end_pos if elements else header_node.start_pos

        # Assign elements to their sections
        self._assign_elements_to_sections(elements)

        logger.info(f"Built header hierarchy with {len(self.headers)} headers")
        return self.root

    def _assign_elements_to_sections(self, elements: List[MarkdownElement]):
        """Assign elements to their corresponding header sections"""
        for elem in elements:
            # Find the deepest header that contains this element
            containing_header = None

            for header in reversed(self.headers):  # Check from deepest to shallowest
                if header.start_pos <= elem.start_pos < header.end_pos:
                    containing_header = header
                    break

            if containing_header:
                containing_header.elements.append(elem)
            else:
                # Element before any header, belongs to root
                self.root.elements.append(elem)

    def get_header_for_position(self, position: int) -> Optional[HeaderNode]:
        """
        Get the header node that contains a given position.

        Args:
            position: Position in document

        Returns:
            HeaderNode or None if position is before any header
        """
        for header in reversed(self.headers):
            if header.start_pos <= position < header.end_pos:
                return header

        return None

    def are_under_same_hierarchy(
        self, pos1: int, pos2: int, max_level_difference: int = 0
    ) -> bool:
        """
        Check if two positions are under the same header hierarchy.

        Args:
            pos1: First position
            pos2: Second position
            max_level_difference: Maximum level difference to consider "same hierarchy"
                                 0 = must be under exact same header
                                 1 = can be under sibling headers with same parent
                                 2+ = more lenient

        Returns:
            True if positions are under same hierarchy
        """
        header1 = self.get_header_for_position(pos1)
        header2 = self.get_header_for_position(pos2)

        # Both before any header or both in root
        if header1 is None and header2 is None:
            return True

        # One in root, one in section
        if header1 is None or header2 is None:
            return max_level_difference >= 1

        # Same header
        if header1 == header2:
            return True

        # Check if they share a common ancestor
        common_ancestor = header1.get_common_ancestor(header2)

        if common_ancestor is None:
            return False

        # Calculate hierarchy distance
        depth1 = header1.get_depth()
        depth2 = header2.get_depth()
        ancestor_depth = common_ancestor.get_depth()

        # Distance is how many levels away from common ancestor
        distance = max(depth1 - ancestor_depth, depth2 - ancestor_depth)

        return distance <= max_level_difference

    def are_elements_under_same_hierarchy(
        self, elem1: MarkdownElement, elem2: MarkdownElement,
        max_level_difference: int = 0
    ) -> bool:
        """
        Check if two elements are under the same header hierarchy.

        Args:
            elem1: First element
            elem2: Second element
            max_level_difference: Maximum level difference to consider "same hierarchy"

        Returns:
            True if elements are under same hierarchy
        """
        return self.are_under_same_hierarchy(
            elem1.start_pos, elem2.start_pos, max_level_difference
        )

    def get_section_hierarchy(self, position: int) -> List[HeaderNode]:
        """
        Get the full hierarchy path for a position.

        Args:
            position: Position in document

        Returns:
            List of HeaderNode from root to the containing header
        """
        header = self.get_header_for_position(position)

        if header is None:
            return [self.root] if self.root else []

        path = []
        node = header
        while node and node != self.root:
            path.insert(0, node)
            node = node.parent

        return path

    def get_all_headers(self) -> List[HeaderNode]:
        """Get all headers in document order"""
        return self.headers.copy()

    def get_headers_at_level(self, level: int) -> List[HeaderNode]:
        """Get all headers at a specific level"""
        return [h for h in self.headers if h.level == level]

    def print_hierarchy(self, node: Optional[HeaderNode] = None, indent: int = 0):
        """
        Print the header hierarchy tree (for debugging).

        Args:
            node: Node to start from (defaults to root)
            indent: Current indentation level
        """
        if node is None:
            node = self.root

        if node is None:
            return

        prefix = "  " * indent
        logger.info(f"{prefix}{node}")

        for child in node.children:
            self.print_hierarchy(child, indent + 1)


def create_hierarchy_analyzer(elements: List[MarkdownElement]) -> HierarchyAnalyzer:
    """
    Convenience function to create and build a hierarchy analyzer.

    Args:
        elements: List of markdown elements

    Returns:
        HierarchyAnalyzer with built tree
    """
    analyzer = HierarchyAnalyzer()
    analyzer.build_tree(elements)
    return analyzer
