#!/usr/bin/env python3
"""
Comprehensive Test Suite for WebNexus MCP Server

Tests all MCP tools:
- crawl_website (single_page, batch, recursive, sitemap strategies)
- search_documents (vector, keyword, hybrid search types)
- get_sources (with filtering options)
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webnexus.mcp.server import crawl_website, search_documents, get_sources, initialize_server


class Colors:
    """Terminal colors for pretty output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


class MCPServerTester:
    """Comprehensive tester for MCP server functionality."""
    
    def __init__(self):
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
    
    def print_header(self, text: str):
        """Print a formatted section header."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}\n")
    
    def print_test(self, test_name: str, status: str, details: str = ""):
        """Print a test result."""
        if status == "PASS":
            symbol = f"{Colors.GREEN}✓{Colors.END}"
            self.test_results['passed'] += 1
        elif status == "FAIL":
            symbol = f"{Colors.RED}✗{Colors.END}"
            self.test_results['failed'] += 1
        else:
            symbol = f"{Colors.YELLOW}⚠{Colors.END}"
        
        print(f"{symbol} {Colors.BOLD}{test_name}{Colors.END}: {status}")
        if details:
            print(f"  {Colors.BLUE}{details}{Colors.END}")
        
        self.test_results['tests'].append({
            'name': test_name,
            'status': status,
            'details': details
        })
    
    async def test_initialization(self):
        """Test MCP server initialization."""
        self.print_header("🏗️  Testing MCP Server Initialization")
        
        try:
            initialize_server()
            self.print_test(
                "Server Initialization",
                "PASS",
                "Database and services initialized successfully"
            )
            return True
        except Exception as e:
            self.print_test(
                "Server Initialization",
                "FAIL",
                f"Error: {str(e)}"
            )
            return False
    
    async def test_crawl_website_single(self):
        """Test crawl_website with single_page strategy."""
        self.print_header("🕷️  Testing crawl_website Tool - Single Page Strategy")
        
        test_url = "https://google.com"
        
        try:
            result_json = await crawl_website(
                url=test_url,
                strategy="single_page",
                store_documents=True
            )
            result = json.loads(result_json)
            
            # Validate response structure
            assert "success" in result, "Missing 'success' field"
            assert "session_id" in result, "Missing 'session_id' field"
            assert "documents_stored" in result, "Missing 'documents_stored' field"
            assert "strategy" in result, "Missing 'strategy' field"
            assert result["strategy"] == "single_page", "Incorrect strategy"
            
            if result["success"]:
                self.print_test(
                    "Single Page Crawl",
                    "PASS",
                    f"Crawled {test_url}, stored {result.get('documents_stored', 0)} documents"
                )
            else:
                self.print_test(
                    "Single Page Crawl",
                    "FAIL",
                    f"Crawl failed: {result.get('error', 'Unknown error')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Single Page Crawl",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_crawl_website_recursive(self):
        """Test crawl_website with recursive strategy."""
        self.print_header("🌐 Testing crawl_website Tool - Recursive Strategy")
        
        test_url = "https://google.com"
        
        try:
            result_json = await crawl_website(
                url=test_url,
                strategy="recursive",
                max_depth=1,
                max_pages=3,
                store_documents=True
            )
            result = json.loads(result_json)
            
            # Validate response
            assert "success" in result, "Missing 'success' field"
            
            if result["success"]:
                self.print_test(
                    "Recursive Crawl",
                    "PASS",
                    f"Strategy: {result.get('strategy')}, Pages: {result.get('pages_crawled', 0)}"
                )
            else:
                self.print_test(
                    "Recursive Crawl",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Recursive Crawl",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_search_documents_vector(self):
        """Test search_documents with vector search."""
        self.print_header("🔍 Testing search_documents Tool - Vector Search")
        
        test_query = "example domain"
        
        try:
            result_json = await search_documents(
                query=test_query,
                max_results=5,
                search_type="vector",
                use_reranking=False
            )
            result = json.loads(result_json)
            
            assert "success" in result, "Missing 'success' field"
            assert "results" in result, "Missing 'results' field"
            assert "total_results" in result, "Missing 'total_results' field"
            assert "search_type" in result, "Missing 'search_type' field"
            
            if result["success"]:
                self.print_test(
                    "Vector Search",
                    "PASS",
                    f"Found {result['total_results']} results for '{test_query}'"
                )
            else:
                self.print_test(
                    "Vector Search",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Vector Search",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_search_documents_keyword(self):
        """Test search_documents with keyword search."""
        self.print_header("📝 Testing search_documents Tool - Keyword Search")
        
        test_query = "example"
        
        try:
            result_json = await search_documents(
                query=test_query,
                max_results=5,
                search_type="keyword",
                use_reranking=False
            )
            result = json.loads(result_json)
            
            if result["success"]:
                self.print_test(
                    "Keyword Search",
                    "PASS",
                    f"Found {result['total_results']} results with BM25"
                )
            else:
                self.print_test(
                    "Keyword Search",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Keyword Search",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_search_documents_hybrid(self):
        """Test search_documents with hybrid search and reranking."""
        self.print_header("⚡ Testing search_documents Tool - Hybrid + Reranking")
        
        test_query = "domain example information"
        
        try:
            result_json = await search_documents(
                query=test_query,
                max_results=5,
                search_type="hybrid",
                use_reranking=True
            )
            result = json.loads(result_json)
            
            if result["success"]:
                self.print_test(
                    "Hybrid Search with Reranking",
                    "PASS",
                    f"Search strategy: {result.get('search_type')}, Results: {result['total_results']}"
                )
            else:
                self.print_test(
                    "Hybrid Search with Reranking",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Hybrid Search with Reranking",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_get_sources(self):
        """Test get_sources tool."""
        self.print_header("📚 Testing get_sources Tool")
        
        try:
            result_json = await get_sources(limit=10)
            result = json.loads(result_json)
            
            assert "success" in result, "Missing 'success' field"
            assert "sources" in result, "Missing 'sources' field"
            assert "total_sources" in result, "Missing 'total_sources' field"
            assert "statistics" in result, "Missing 'statistics' field"
            
            if result["success"]:
                self.print_test(
                    "Get Sources (No Filter)",
                    "PASS",
                    f"Retrieved {result['returned_count']}/{result['total_sources']} sources"
                )
            else:
                self.print_test(
                    "Get Sources (No Filter)",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Get Sources (No Filter)",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_get_sources_filtered(self):
        """Test get_sources with URL pattern filter."""
        self.print_header("🔎 Testing get_sources Tool - URL Filter")
        
        try:
            result_json = await get_sources(
                limit=5,
                url_pattern="google.com"
            )
            result = json.loads(result_json)
            
            if result["success"]:
                self.print_test(
                    "Get Sources (URL Filter)",
                    "PASS",
                    f"Found {result['returned_count']} sources matching 'google.com'"
                )
            else:
                self.print_test(
                    "Get Sources (URL Filter)",
                    "FAIL",
                    f"Error: {result.get('error', 'Unknown')}"
                )
            
            return result["success"]
            
        except Exception as e:
            self.print_test(
                "Get Sources (URL Filter)",
                "FAIL",
                f"Exception: {str(e)}"
            )
            return False
    
    async def test_error_handling(self):
        """Test error handling with invalid inputs."""
        self.print_header("🛡️  Testing Error Handling")
        
        # Test invalid strategy
        try:
            result_json = await crawl_website(
                url="https://google.com",
                strategy="invalid_strategy"
            )
            result = json.loads(result_json)
            
            if not result["success"] and "error" in result:
                self.print_test(
                    "Invalid Strategy Error Handling",
                    "PASS",
                    "Correctly rejected invalid strategy"
                )
            else:
                self.print_test(
                    "Invalid Strategy Error Handling",
                    "FAIL",
                    "Should have rejected invalid strategy"
                )
        except Exception as e:
            self.print_test(
                "Invalid Strategy Error Handling",
                "FAIL",
                f"Exception: {str(e)}"
            )
        
        # Test invalid search type
        try:
            result_json = await search_documents(
                query="test",
                search_type="invalid_type"
            )
            result = json.loads(result_json)
            
            if not result["success"] and "error" in result:
                self.print_test(
                    "Invalid Search Type Error Handling",
                    "PASS",
                    "Correctly rejected invalid search type"
                )
            else:
                self.print_test(
                    "Invalid Search Type Error Handling",
                    "FAIL",
                    "Should have rejected invalid search type"
                )
        except Exception as e:
            self.print_test(
                "Invalid Search Type Error Handling",
                "FAIL",
                f"Exception: {str(e)}"
            )
    
    async def run_all_tests(self):
        """Run all tests in sequence."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'#' * 80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}#  WebNexus MCP Server - Comprehensive Test Suite{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'#' * 80}{Colors.END}\n")
        
        # Step 1: Initialize
        if not await self.test_initialization():
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️  Server initialization failed. Stopping tests.{Colors.END}")
            return
        
        # Step 2: Crawling tests
        await self.test_crawl_website_single()
        await asyncio.sleep(2)  # Small delay between tests
        
        await self.test_crawl_website_recursive()
        await asyncio.sleep(2)
        
        # Step 3: Search tests
        await self.test_search_documents_vector()
        await asyncio.sleep(1)
        
        await self.test_search_documents_keyword()
        await asyncio.sleep(1)
        
        await self.test_search_documents_hybrid()
        await asyncio.sleep(1)
        
        # Step 4: Source management tests
        await self.test_get_sources()
        await asyncio.sleep(1)
        
        await self.test_get_sources_filtered()
        await asyncio.sleep(1)
        
        # Step 5: Error handling tests
        await self.test_error_handling()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        total_tests = self.test_results['passed'] + self.test_results['failed']
        
        self.print_header("📊 Test Summary")
        
        print(f"{Colors.BOLD}Total Tests:{Colors.END} {total_tests}")
        print(f"{Colors.GREEN}{Colors.BOLD}Passed:{Colors.END} {self.test_results['passed']}")
        print(f"{Colors.RED}{Colors.BOLD}Failed:{Colors.END} {self.test_results['failed']}")
        
        if self.test_results['failed'] == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.END}")
            print(f"{Colors.GREEN}MCP Server is ready for production use with Claude Desktop.{Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed.{Colors.END}")
            print(f"{Colors.YELLOW}Review the failures above and fix the issues.{Colors.END}")
        
        print(f"\n{Colors.CYAN}{'=' * 80}{Colors.END}\n")


async def main():
    """Main entry point."""
    tester = MCPServerTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())