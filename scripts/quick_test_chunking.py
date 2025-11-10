#!/usr/bin/env python3
"""Quick validation of documentation chunking"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Simple markdown sample
SAMPLE = """# Main Header

This is a paragraph under the main header.

## Subheader 1

Content for subheader 1.

```python
def hello():
    print("Hello, World!")
```

## Subheader 2

More content here.

- Item 1
- Item 2
- Item 3
"""

def test_basic():
    """Test basic functionality"""
    print("Testing Documentation Chunking...\n")

    # Test token counter
    print("1. Testing Token Counter...")
    try:
        from webnexus.utils.token_counter import TokenCounter
        counter = TokenCounter()
        tokens = counter.count_tokens("Hello, World!")
        print(f"   ✓ Token count: {tokens}")
        print(f"   ✓ Encoding: {counter.get_encoding_name()}")
    except Exception as e:
        print(f"   ✗ Token counter error: {e}")

    # Test markdown parser
    print("\n2. Testing Markdown Parser...")
    try:
        from webnexus.utils.markdown_parser import MarkdownParser
        parser = MarkdownParser()
        elements = parser.parse(SAMPLE)
        print(f"   ✓ Parsed {len(elements)} elements")
        headers = [e for e in elements if e.type.value == "header"]
        print(f"   ✓ Found {len(headers)} headers")
        code = [e for e in elements if e.type.value == "code_block"]
        print(f"   ✓ Found {len(code)} code blocks")
    except Exception as e:
        print(f"   ✗ Parser error: {e}")

    # Test header hierarchy
    print("\n3. Testing Header Hierarchy...")
    try:
        from webnexus.utils.header_hierarchy import create_hierarchy_analyzer
        analyzer = create_hierarchy_analyzer(elements)
        print(f"   ✓ Built hierarchy with {len(analyzer.get_all_headers())} headers")
    except Exception as e:
        print(f"   ✗ Hierarchy error: {e}")

    # Test similarity calculator
    print("\n4. Testing Similarity Calculator...")
    try:
        from webnexus.utils.similarity_calculator import calculate_similarity
        sim = calculate_similarity("Hello World", "Hello World")
        print(f"   ✓ Similarity calculation works: {sim:.2f}")
    except Exception as e:
        print(f"   ✗ Similarity error: {e}")

    # Test documentation chunker
    print("\n5. Testing Documentation Chunker...")
    try:
        from webnexus.utils.documentation_chunking import DocumentationChunker
        chunker = DocumentationChunker(max_tokens=500, enable_merging=True)
        chunks = chunker.chunk_document(SAMPLE, url="test.md")
        print(f"   ✓ Created {len(chunks)} chunks")
        if chunks:
            print(f"   ✓ First chunk: {chunks[0].token_count} tokens")
            print(f"   ✓ Has code: {chunks[0].metadata.get('has_code', False)}")
    except Exception as e:
        print(f"   ✗ Chunker error: {e}")
        import traceback
        traceback.print_exc()

    print("\n✅ Basic validation complete!")

if __name__ == "__main__":
    test_basic()
