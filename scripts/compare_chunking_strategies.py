#!/usr/bin/env python3
"""
Chunking Strategy Comparison Script

Compares all 4 chunking strategies on a real documentation page:
1. Original Archon
2. Advanced
3. Specialized
4. Documentation

Tests with: https://zulko.github.io/moviepy/user_guide/loading.html
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import httpx
from bs4 import BeautifulSoup
import html2text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import all chunking strategies
from webnexus.utils.original_chunking import OriginalArchonChunker
from webnexus.utils.chunking import DocumentChunker as AdvancedChunker, SpecializedChunkers
from webnexus.utils.documentation_chunking import DocumentationChunker
from webnexus.utils.token_counter import TokenCounter


class ChunkingComparison:
    """Compare chunking strategies on real documentation"""

    def __init__(self, url: str = None, markdown_file: str = None, output_dir: str = "./chunking_comparison"):
        self.url = url
        self.markdown_file = markdown_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Store results
        self.markdown_content = None
        self.results = {}

        # Token counter for consistent token counting
        self.token_counter = TokenCounter()

        print(f"🔍 Chunking Strategy Comparison")
        if url:
            print(f"📄 URL: {url}")
        elif markdown_file:
            print(f"📄 File: {markdown_file}")
        print(f"📁 Output: {output_dir}")
        print()

    async def crawl_page(self) -> str:
        """Crawl the page once and get markdown content"""
        print("📥 Fetching page...")

        try:
            # Fetch HTML using httpx with headers to avoid 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers=headers) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                html_content = response.text

            print(f"   ✓ Fetched HTML ({len(html_content):,} characters)")

            # Convert HTML to markdown using html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.body_width = 0  # Don't wrap lines
            h.ignore_tables = False

            self.markdown_content = h.handle(html_content)

            # Save original markdown
            markdown_file = self.output_dir / "original_markdown.md"
            markdown_file.write_text(self.markdown_content, encoding='utf-8')

            print(f"✅ Converted to markdown successfully")
            print(f"   Characters: {len(self.markdown_content):,}")
            print(f"   Words: {len(self.markdown_content.split()):,}")
            print(f"   Lines: {self.markdown_content.count(chr(10)):,}")
            print(f"   Saved to: {markdown_file}")
            print()

            return self.markdown_content

        except Exception as e:
            print(f"❌ Fetch error: {e}")
            raise

    def test_original_strategy(self) -> Dict[str, Any]:
        """Test Original Archon strategy"""
        print("🔷 Testing Original Archon Strategy...")

        chunker = OriginalArchonChunker(chunk_size=5000)
        url = self.url or self.markdown_file or "sample_document.md"
        chunks = chunker.chunk_document(
            self.markdown_content,
            url=url
        )

        result = self._analyze_chunks(
            strategy="original",
            chunks=[{
                'content': c.content,
                'chunk_index': c.chunk_index,
                'char_count': c.char_count,
                'word_count': c.word_count,
                'metadata': c.metadata
            } for c in chunks],
            config={
                'chunk_size': 5000,
                'overlap': 0,
                'boundaries': 'code_blocks, paragraphs, sentences'
            }
        )

        self._save_chunks("original", chunks)

        return result

    def test_advanced_strategy(self) -> Dict[str, Any]:
        """Test Advanced strategy"""
        print("🔷 Testing Advanced Strategy...")

        chunker = AdvancedChunker(
            chunk_size=1000,
            overlap_size=100,
            respect_boundaries=True,
            min_chunk_size=50,
            max_chunk_size=2000
        )
        url = self.url or self.markdown_file or "sample_document.md"
        chunks = chunker.chunk_document(self.markdown_content, url)

        result = self._analyze_chunks(
            strategy="advanced",
            chunks=[{
                'content': c.content,
                'chunk_index': c.chunk_index,
                'char_count': c.char_count,
                'word_count': c.word_count,
                'start_char': c.start_char,
                'end_char': c.end_char,
                'metadata': {}
            } for c in chunks],
            config={
                'chunk_size': 1000,
                'overlap': 100,
                'boundaries': 'headers, code_blocks, lists, paragraphs, sentences'
            }
        )

        self._save_chunks("advanced", chunks)

        return result

    def test_specialized_strategy(self) -> Dict[str, Any]:
        """Test Specialized strategy"""
        print("🔷 Testing Specialized Strategy (Markdown)...")

        chunks = SpecializedChunkers.chunk_markdown(self.markdown_content)

        result = self._analyze_chunks(
            strategy="specialized",
            chunks=[{
                'content': c.content,
                'chunk_index': c.chunk_index,
                'char_count': c.char_count,
                'word_count': c.word_count,
                'start_char': c.start_char,
                'end_char': c.end_char,
                'metadata': {}
            } for c in chunks],
            config={
                'chunk_size': 1200,
                'overlap': 100,
                'boundaries': 'markdown_structure_aware'
            }
        )

        self._save_chunks("specialized", chunks)

        return result

    def test_documentation_strategy(self) -> Dict[str, Any]:
        """Test Documentation strategy"""
        print("🔷 Testing Documentation Strategy...")

        chunker = DocumentationChunker(
            max_tokens=4000,
            similarity_threshold=0.80,
            max_level_difference=0,
            enable_merging=True
        )
        url = self.url or self.markdown_file or "sample_document.md"
        chunks = chunker.chunk_document(
            self.markdown_content,
            url=url,
            metadata={'source': 'moviepy_docs'}
        )

        result = self._analyze_chunks(
            strategy="documentation",
            chunks=[{
                'content': c.content,
                'chunk_index': c.chunk_index,
                'char_count': c.char_count,
                'word_count': c.word_count,
                'token_count': c.token_count,
                'start_char': c.start_char,
                'end_char': c.end_char,
                'metadata': c.metadata
            } for c in chunks],
            config={
                'max_tokens': 4000,
                'overlap': 0,
                'similarity_threshold': 0.80,
                'enable_merging': True,
                'boundaries': 'markdown_structure + hierarchy + similarity'
            }
        )

        self._save_chunks("documentation", chunks)

        return result

    def _analyze_chunks(self, strategy: str, chunks: List[Dict], config: Dict) -> Dict[str, Any]:
        """Analyze chunks and generate metrics"""

        if not chunks:
            return {
                'strategy': strategy,
                'config': config,
                'chunk_count': 0,
                'error': 'No chunks created'
            }

        # Calculate statistics
        char_counts = [c['char_count'] for c in chunks]
        word_counts = [c['word_count'] for c in chunks]

        # Count tokens for all chunks
        token_counts = []
        for c in chunks:
            if 'token_count' in c:
                token_counts.append(c['token_count'])
            else:
                token_counts.append(self.token_counter.count_tokens(c['content']))

        # Calculate overlap (if any)
        overlap_chars = 0
        if len(chunks) > 1:
            for i in range(len(chunks) - 1):
                if 'start_char' in chunks[i] and 'end_char' in chunks[i]:
                    if 'start_char' in chunks[i+1]:
                        overlap = chunks[i]['end_char'] - chunks[i+1]['start_char']
                        if overlap > 0:
                            overlap_chars += overlap

        # Calculate coverage (what % of original content is in chunks)
        total_chunk_chars = sum(char_counts)
        original_chars = len(self.markdown_content)

        # Detect special elements in chunks
        chunks_with_code = sum(1 for c in chunks if '```' in c['content'])
        chunks_with_headers = sum(1 for c in chunks if any(
            c['content'].startswith('#' * i) for i in range(1, 7)
        ))
        chunks_with_lists = sum(1 for c in chunks if '\n- ' in c['content'] or '\n* ' in c['content'])

        # Check for merged/split chunks
        merged_chunks = sum(1 for c in chunks if c.get('metadata', {}).get('merged', False))
        split_chunks = sum(1 for c in chunks if c.get('metadata', {}).get('split', False))

        result = {
            'strategy': strategy,
            'config': config,
            'chunk_count': len(chunks),
            'character_stats': {
                'total': sum(char_counts),
                'min': min(char_counts),
                'max': max(char_counts),
                'avg': sum(char_counts) / len(char_counts),
                'median': sorted(char_counts)[len(char_counts) // 2]
            },
            'word_stats': {
                'total': sum(word_counts),
                'min': min(word_counts),
                'max': max(word_counts),
                'avg': sum(word_counts) / len(word_counts),
                'median': sorted(word_counts)[len(word_counts) // 2]
            },
            'token_stats': {
                'total': sum(token_counts),
                'min': min(token_counts),
                'max': max(token_counts),
                'avg': sum(token_counts) / len(token_counts),
                'median': sorted(token_counts)[len(token_counts) // 2]
            },
            'overlap_chars': overlap_chars,
            'coverage': {
                'percentage': (total_chunk_chars / original_chars) * 100 if overlap_chars == 0 else
                              ((total_chunk_chars - overlap_chars) / original_chars) * 100,
                'original_chars': original_chars,
                'chunk_chars': total_chunk_chars,
                'net_chars': total_chunk_chars - overlap_chars
            },
            'content_analysis': {
                'chunks_with_code': chunks_with_code,
                'chunks_with_headers': chunks_with_headers,
                'chunks_with_lists': chunks_with_lists,
                'merged_chunks': merged_chunks,
                'split_chunks': split_chunks
            },
            'efficiency': {
                'chars_per_chunk': sum(char_counts) / len(chunks),
                'words_per_chunk': sum(word_counts) / len(chunks),
                'tokens_per_chunk': sum(token_counts) / len(chunks)
            }
        }

        # Print summary
        print(f"   ✓ Chunks created: {result['chunk_count']}")
        print(f"   ✓ Tokens: min={result['token_stats']['min']}, "
              f"max={result['token_stats']['max']}, avg={result['token_stats']['avg']:.0f}")
        print(f"   ✓ Coverage: {result['coverage']['percentage']:.1f}%")
        if merged_chunks > 0:
            print(f"   ✓ Merged chunks: {merged_chunks}")
        if split_chunks > 0:
            print(f"   ✓ Split chunks: {split_chunks}")
        print()

        return result

    def _save_chunks(self, strategy: str, chunks: List) -> None:
        """Save chunks to files"""
        strategy_dir = self.output_dir / strategy
        strategy_dir.mkdir(exist_ok=True)

        # Save each chunk
        for i, chunk in enumerate(chunks):
            chunk_file = strategy_dir / f"chunk_{i:03d}.txt"

            # Get content based on chunk type
            if hasattr(chunk, 'content'):
                content = chunk.content
            else:
                content = chunk['content']

            chunk_file.write_text(content, encoding='utf-8')

        # Save chunk metadata
        metadata_file = strategy_dir / "chunks_metadata.json"

        metadata = []
        for i, chunk in enumerate(chunks):
            if hasattr(chunk, '__dict__'):
                # Convert dataclass to dict
                chunk_dict = {
                    'chunk_index': chunk.chunk_index,
                    'char_count': chunk.char_count,
                    'word_count': chunk.word_count,
                }
                if hasattr(chunk, 'token_count'):
                    chunk_dict['token_count'] = chunk.token_count
                if hasattr(chunk, 'metadata'):
                    chunk_dict['metadata'] = chunk.metadata
            else:
                # Already a dict
                chunk_dict = {
                    'chunk_index': chunk.get('chunk_index', i),
                    'char_count': chunk.get('char_count', 0),
                    'word_count': chunk.get('word_count', 0),
                }
                if 'token_count' in chunk:
                    chunk_dict['token_count'] = chunk['token_count']
                if 'metadata' in chunk:
                    chunk_dict['metadata'] = chunk.get('metadata', {})

            metadata.append(chunk_dict)

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"   💾 Saved to: {strategy_dir}/")

    def generate_comparison_report(self) -> None:
        """Generate comprehensive comparison report"""
        print("\n" + "=" * 80)
        print("📊 CHUNKING STRATEGY COMPARISON REPORT")
        print("=" * 80 + "\n")

        print(f"Document: {self.url}")
        print(f"Original size: {len(self.markdown_content):,} characters")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Comparison table
        print("┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐")
        print("│ Strategy        │ Chunks   │ Avg Tok  │ Coverage │ Code Blk │ Merged   │")
        print("├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤")

        for strategy_name in ['original', 'advanced', 'specialized', 'documentation']:
            if strategy_name in self.results:
                r = self.results[strategy_name]
                print(f"│ {strategy_name:15s} │ {r['chunk_count']:8d} │ "
                      f"{r['token_stats']['avg']:8.0f} │ {r['coverage']['percentage']:7.1f}% │ "
                      f"{r['content_analysis']['chunks_with_code']:8d} │ "
                      f"{r['content_analysis']['merged_chunks']:8d} │")

        print("└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘")
        print()

        # Detailed analysis
        print("📈 Detailed Analysis:")
        print()

        for strategy_name in ['original', 'advanced', 'specialized', 'documentation']:
            if strategy_name not in self.results:
                continue

            r = self.results[strategy_name]
            print(f"【 {strategy_name.upper()} 】")
            print(f"  Configuration:")
            for key, value in r['config'].items():
                print(f"    • {key}: {value}")

            print(f"  Chunks: {r['chunk_count']}")
            print(f"  Token distribution: min={r['token_stats']['min']}, "
                  f"max={r['token_stats']['max']}, avg={r['token_stats']['avg']:.0f}, "
                  f"median={r['token_stats']['median']}")
            print(f"  Character distribution: min={r['character_stats']['min']}, "
                  f"max={r['character_stats']['max']}, avg={r['character_stats']['avg']:.0f}")
            print(f"  Coverage: {r['coverage']['percentage']:.2f}% "
                  f"({r['coverage']['net_chars']:,} / {r['coverage']['original_chars']:,} chars)")
            print(f"  Overlap: {r['overlap_chars']:,} characters")
            print(f"  Content:")
            print(f"    • Chunks with code blocks: {r['content_analysis']['chunks_with_code']}")
            print(f"    • Chunks with headers: {r['content_analysis']['chunks_with_headers']}")
            print(f"    • Chunks with lists: {r['content_analysis']['chunks_with_lists']}")
            if r['content_analysis']['merged_chunks'] > 0:
                print(f"    • Merged chunks: {r['content_analysis']['merged_chunks']}")
            if r['content_analysis']['split_chunks'] > 0:
                print(f"    • Split chunks: {r['content_analysis']['split_chunks']}")
            print()

        # Performance assessment
        print("🏆 Performance Assessment:")
        print()

        # Best for different metrics
        best_coverage = max(self.results.items(), key=lambda x: x[1]['coverage']['percentage'])
        best_efficiency = min(self.results.items(), key=lambda x: x[1]['chunk_count'])
        best_token_balance = min(self.results.items(),
                                 key=lambda x: abs(x[1]['token_stats']['avg'] - 2000))

        print(f"  • Best coverage: {best_coverage[0]} ({best_coverage[1]['coverage']['percentage']:.1f}%)")
        print(f"  • Most efficient (fewest chunks): {best_efficiency[0]} ({best_efficiency[1]['chunk_count']} chunks)")
        print(f"  • Best token balance (~2000): {best_token_balance[0]} "
              f"(avg {best_token_balance[1]['token_stats']['avg']:.0f} tokens)")
        print()

        # Save report
        report_file = self.output_dir / "comparison_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'url': self.url,
                'generated_at': datetime.now().isoformat(),
                'original_content': {
                    'chars': len(self.markdown_content),
                    'words': len(self.markdown_content.split()),
                    'lines': self.markdown_content.count('\n')
                },
                'results': self.results
            }, f, indent=2, ensure_ascii=False)

        print(f"💾 Full report saved to: {report_file}")
        print()

    def load_from_file(self) -> str:
        """Load markdown from file"""
        print("📂 Loading markdown from file...")

        try:
            file_path = Path(self.markdown_file)
            self.markdown_content = file_path.read_text(encoding='utf-8')

            # Save copy to output
            markdown_file = self.output_dir / "original_markdown.md"
            markdown_file.write_text(self.markdown_content, encoding='utf-8')

            print(f"✅ Loaded successfully")
            print(f"   Characters: {len(self.markdown_content):,}")
            print(f"   Words: {len(self.markdown_content.split()):,}")
            print(f"   Lines: {self.markdown_content.count(chr(10)):,}")
            print()

            return self.markdown_content

        except Exception as e:
            print(f"❌ Load error: {e}")
            raise

    async def run_comparison(self) -> None:
        """Run complete comparison"""
        try:
            # Step 1: Get content
            if self.markdown_file:
                self.load_from_file()
            elif self.url:
                await self.crawl_page()
            else:
                print("❌ No URL or file provided")
                return

            if not self.markdown_content:
                print("❌ No content to chunk")
                return

            # Step 2: Test all strategies
            self.results['original'] = self.test_original_strategy()
            self.results['advanced'] = self.test_advanced_strategy()
            self.results['specialized'] = self.test_specialized_strategy()
            self.results['documentation'] = self.test_documentation_strategy()

            # Step 3: Generate report
            self.generate_comparison_report()

            print("✅ Comparison complete!")
            print(f"📂 All outputs saved to: {self.output_dir}")

        except Exception as e:
            print(f"\n❌ Comparison failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main entry point"""

    # Option 1: Use local markdown file (for environments with network restrictions)
    markdown_file = "sample_documentation.md"

    # Option 2: Try URL (commented out - may fail in restricted environments)
    # url = "https://zulko.github.io/moviepy/user_guide/loading.html"

    # Output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./chunking_comparison_{timestamp}"

    # Run comparison
    if Path(markdown_file).exists():
        print(f"📄 Using local file: {markdown_file}\n")
        comparison = ChunkingComparison(markdown_file=markdown_file, output_dir=output_dir)
    else:
        print(f"⚠️  Local file not found, falling back to URL\n")
        comparison = ChunkingComparison(url="https://zulko.github.io/moviepy/user_guide/loading.html", output_dir=output_dir)

    await comparison.run_comparison()


if __name__ == "__main__":
    asyncio.run(main())
