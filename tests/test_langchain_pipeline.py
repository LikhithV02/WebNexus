"""
LangChain Documentation Pipeline Test

Tests the full WebNexus pipeline with LangChain documentation:
1. Crawl LangChain documentation pages
2. Store and chunk content with enhanced processing  
3. Generate embeddings with Stella EN 400M v5
4. Test enhanced search with keyword extraction
5. Test hybrid search with reranking
6. Validate end-to-end functionality
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from webnexus.services.crawling_service import crawling_service
from webnexus.services.search_service import search_service, SearchResponse
from webnexus.services.storage_service import storage_service
from webnexus.services.vector_service import vector_service
from webnexus.services.embedding_service import embedding_service
from webnexus.services.keyword_extractor import keyword_extractor


class LangChainPipelineTest:
    """Comprehensive LangChain documentation pipeline test"""
    
    def __init__(self):
        self.test_results = {
            "crawl_results": [],
            "search_results": [],
            "performance_metrics": {},
            "errors": []
        }
        
    def log(self, message: str, level: str = "INFO"):
        """Simple logging helper"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    async def test_crawling_pipeline(self) -> Dict[str, Any]:
        """Test crawling LangChain documentation"""
        self.log("=== Testing LangChain Crawling Pipeline ===")
        
        # Test URLs for LangChain documentation
        test_urls = [
            {
                "url": "https://python.langchain.com/docs/introduction/",
                "strategy": "single_page",
                "description": "LangChain Introduction (Single Page)"
            },
            {
                "url": "https://python.langchain.com/docs/concepts/",
                "strategy": "single_page", 
                "description": "LangChain Concepts (Single Page)"
            },
            {
                "url": "https://python.langchain.com/docs/tutorials/",
                "strategy": "recursive",
                "max_depth": 2,
                "max_pages": 10,
                "description": "LangChain Tutorials (Recursive)"
            }
        ]
        
        crawl_results = []
        
        for test_config in test_urls:
            self.log(f"Testing: {test_config['description']}")
            start_time = time.time()
            
            try:
                # Perform crawl based on strategy
                if test_config["strategy"] == "single_page":
                    result = await crawling_service.crawl_single_page(
                        url=test_config["url"],
                        store_documents=True
                    )
                elif test_config["strategy"] == "recursive":
                    result = await crawling_service.crawl_recursive(
                        start_url=test_config["url"],
                        max_depth=test_config.get("max_depth", 2),
                        max_pages=test_config.get("max_pages", 10),
                        store_documents=True
                    )
                
                crawl_time = time.time() - start_time
                
                # Analyze results
                success = result.get("success", False)
                documents_stored = result.get("documents_stored", 0)
                
                crawl_result = {
                    "config": test_config,
                    "success": success,
                    "documents_stored": documents_stored,
                    "crawl_time_seconds": round(crawl_time, 2),
                    "result": result
                }
                
                crawl_results.append(crawl_result)
                
                if success:
                    self.log(f"✅ SUCCESS: Crawled {documents_stored} documents in {crawl_time:.2f}s")
                else:
                    self.log(f"❌ FAILED: {result.get('error', 'Unknown error')}", "ERROR")
                    self.test_results["errors"].append(f"Crawl failed: {test_config['description']}")
                    
            except Exception as e:
                self.log(f"❌ EXCEPTION: {str(e)}", "ERROR")
                self.test_results["errors"].append(f"Crawl exception: {test_config['description']} - {str(e)}")
                crawl_results.append({
                    "config": test_config,
                    "success": False,
                    "error": str(e),
                    "crawl_time_seconds": time.time() - start_time
                })
        
        self.test_results["crawl_results"] = crawl_results
        
        # Summary
        successful_crawls = sum(1 for r in crawl_results if r["success"])
        total_documents = sum(r.get("documents_stored", 0) for r in crawl_results if r["success"])
        
        self.log(f"Crawling Summary: {successful_crawls}/{len(test_urls)} successful, {total_documents} documents stored")
        
        return {
            "successful_crawls": successful_crawls,
            "total_crawls": len(test_urls),
            "total_documents_stored": total_documents,
            "crawl_results": crawl_results
        }
    
    async def test_enhanced_search(self) -> Dict[str, Any]:
        """Test enhanced search with keyword extraction"""
        self.log("=== Testing Enhanced Search Capabilities ===")
        
        # Test queries focused on LangChain concepts
        test_queries = [
            "LangChain vector stores and embeddings",
            "document loaders and text splitters", 
            "LangChain agents and tools integration",
            "chain composition and prompt templates",
            "memory and conversation handling",
            "LangChain Python API examples"
        ]
        
        search_results = []
        
        for query in test_queries:
            self.log(f"Testing search: '{query}'")
            start_time = time.time()
            
            try:
                # Test different search approaches
                approaches = {}
                
                # 1. Enhanced keyword search (with keyword extraction)
                approaches["keyword_enhanced"] = await search_service.keyword_search(
                    query, top_k=5
                )
                
                # 2. Vector search  
                approaches["vector"] = await search_service.vector_search(
                    query, top_k=5
                )
                
                # 3. Hybrid search
                approaches["hybrid"] = await search_service.hybrid_search(
                    query, top_k=5
                )
                
                # 4. Hybrid with reranking
                approaches["hybrid_reranked"] = await search_service.hybrid_search_with_reranking(
                    query, rerank_strategy="hybrid"
                )
                
                search_time = time.time() - start_time
                
                # Analyze keyword extraction quality
                keywords = keyword_extractor.extract_keywords(query, max_keywords=10)
                search_terms = keyword_extractor.build_search_terms(keywords)
                
                result_summary = {
                    "query": query,
                    "keywords_extracted": keywords,
                    "search_terms_expanded": len(search_terms),
                    "search_time_seconds": round(search_time, 2),
                    "approach_results": {}
                }
                
                # Analyze each approach
                for approach_name, results in approaches.items():
                    # Handle both SearchResponse objects and list results
                    if isinstance(results, SearchResponse):
                        # For SearchResponse objects, access the .results attribute
                        actual_results = results.results
                        if actual_results:
                            result_summary["approach_results"][approach_name] = {
                                "result_count": len(actual_results),
                                "top_score": actual_results[0].combined_score,
                                "has_langchain_content": any("langchain" in str(r.content).lower() for r in actual_results[:3])
                            }
                        else:
                            result_summary["approach_results"][approach_name] = {
                                "result_count": 0,
                                "top_score": 0,
                                "has_langchain_content": False
                            }
                    elif isinstance(results, list) and results:
                        # For list results (vector_search, keyword_search)
                        result_summary["approach_results"][approach_name] = {
                            "result_count": len(results),
                            "top_score": results[0].get("combined_score", results[0].get("similarity_score", results[0].get("keyword_score", 0))),
                            "has_langchain_content": any("langchain" in str(r).lower() for r in results[:3])
                        }
                    else:
                        result_summary["approach_results"][approach_name] = {
                            "result_count": 0,
                            "top_score": 0,
                            "has_langchain_content": False
                        }
                
                search_results.append(result_summary)
                
                # Log results
                best_approach = max(
                    result_summary["approach_results"].items(),
                    key=lambda x: x[1]["top_score"]
                )
                
                self.log(f"✅ Best approach: {best_approach[0]} (score: {best_approach[1]['top_score']:.3f})")
                
            except Exception as e:
                self.log(f"❌ Search failed: {str(e)}", "ERROR")
                self.test_results["errors"].append(f"Search failed for query '{query}': {str(e)}")
        
        self.test_results["search_results"] = search_results
        
        # Calculate performance metrics
        avg_search_time = sum(r["search_time_seconds"] for r in search_results) / len(search_results) if search_results else 0
        successful_searches = sum(1 for r in search_results if any(a["result_count"] > 0 for a in r["approach_results"].values()))
        
        self.log(f"Search Summary: {successful_searches}/{len(test_queries)} successful, avg time: {avg_search_time:.2f}s")
        
        return {
            "successful_searches": successful_searches,
            "total_queries": len(test_queries),
            "average_search_time": avg_search_time,
            "search_results": search_results
        }
    
    async def test_keyword_extraction_quality(self) -> Dict[str, Any]:
        """Test keyword extraction enhancement quality"""
        self.log("=== Testing Keyword Extraction Quality ===")
        
        # Technical queries that should benefit from enhanced extraction
        test_cases = [
            {
                "query": "machine learning model deployment best practices production",
                "expected_preserved": ["machine", "learning", "model", "deployment", "production", "best_practices"],
                "technical_terms": True
            },
            {
                "query": "FastAPI JWT authentication with PostgreSQL database security",
                "expected_preserved": ["fastapi", "jwt", "authentication", "postgresql", "database", "security"],
                "technical_terms": True  
            },
            {
                "query": "React hooks useState useEffect optimization performance",
                "expected_preserved": ["react", "hooks", "usestate", "useeffect", "optimization", "performance"],
                "technical_terms": True
            },
            {
                "query": "how to implement vector search with embeddings",
                "expected_preserved": ["vector", "search", "embeddings", "howto"],
                "technical_terms": True
            }
        ]
        
        extraction_results = []
        
        for case in test_cases:
            query = case["query"]
            
            # Simple tokenization (original approach)
            simple_tokens = query.lower().split()
            
            # Enhanced extraction
            keywords = keyword_extractor.extract_keywords(query, max_keywords=15)
            search_terms = keyword_extractor.build_search_terms(keywords)
            
            # Calculate preservation rate for technical terms
            expected_terms = case.get("expected_preserved", [])
            preserved_count = sum(1 for term in expected_terms if term in keywords or term in search_terms)
            preservation_rate = preserved_count / len(expected_terms) if expected_terms else 0
            
            result = {
                "query": query,
                "simple_tokens": simple_tokens,
                "enhanced_keywords": keywords,
                "search_terms_count": len(search_terms),
                "expected_terms": expected_terms,
                "preserved_count": preserved_count,
                "preservation_rate": preservation_rate,
                "improvement_ratio": len(search_terms) / len(simple_tokens) if simple_tokens else 1
            }
            
            extraction_results.append(result)
            
            self.log(f"Query: '{query}'")
            self.log(f"  Simple: {len(simple_tokens)} tokens")
            self.log(f"  Enhanced: {len(keywords)} keywords → {len(search_terms)} search terms")
            self.log(f"  Technical term preservation: {preservation_rate:.1%}")
            self.log(f"  Improvement ratio: {result['improvement_ratio']:.2f}x")
        
        # Overall metrics
        avg_preservation = sum(r["preservation_rate"] for r in extraction_results) / len(extraction_results)
        avg_improvement = sum(r["improvement_ratio"] for r in extraction_results) / len(extraction_results)
        
        self.log(f"Keyword Extraction Summary:")
        self.log(f"  Average technical term preservation: {avg_preservation:.1%}")
        self.log(f"  Average search term expansion: {avg_improvement:.2f}x")
        
        return {
            "average_preservation_rate": avg_preservation,
            "average_improvement_ratio": avg_improvement,
            "extraction_results": extraction_results
        }
    
    async def test_database_storage(self) -> Dict[str, Any]:
        """Test database storage and vector indexing"""
        self.log("=== Testing Database Storage & Vector Indexing ===")
        
        try:
            # Get storage statistics
            storage_stats = storage_service.get_storage_stats()
            
            # Get vector service statistics  
            vector_stats = await vector_service.get_statistics()
            
            # Check database integrity
            db_check = {
                "total_documents": storage_stats.get("total_documents", 0),
                "total_chunks": storage_stats.get("total_chunks", 0),
                "total_embeddings": storage_stats.get("total_embeddings", 0),
                "vector_index_size": vector_stats.get("total_vectors", 0),
                "embedding_dimension": vector_stats.get("embedding_dimension", 0)
            }
            
            # Validate consistency
            consistency_checks = {
                "chunks_have_embeddings": db_check["total_chunks"] == db_check["total_embeddings"],
                "vectors_match_embeddings": db_check["total_embeddings"] == db_check["vector_index_size"],
                "proper_embedding_dimension": db_check["embedding_dimension"] == 1024
            }
            
            all_consistent = all(consistency_checks.values())
            
            self.log(f"Database Statistics:")
            self.log(f"  Documents: {db_check['total_documents']}")
            self.log(f"  Chunks: {db_check['total_chunks']}")
            self.log(f"  Embeddings: {db_check['total_embeddings']}")
            self.log(f"  Vector Index Size: {db_check['vector_index_size']}")
            self.log(f"  Embedding Dimension: {db_check['embedding_dimension']}")
            
            self.log(f"Consistency Checks:")
            for check, passed in consistency_checks.items():
                status = "✅" if passed else "❌"
                self.log(f"  {status} {check}")
            
            if all_consistent:
                self.log("✅ All database consistency checks passed")
            else:
                self.log("❌ Some database consistency issues found", "WARNING")
            
            return {
                "database_stats": db_check,
                "consistency_checks": consistency_checks,
                "all_consistent": all_consistent
            }
            
        except Exception as e:
            self.log(f"❌ Database testing failed: {str(e)}", "ERROR")
            self.test_results["errors"].append(f"Database test failed: {str(e)}")
            return {"error": str(e)}
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run the complete LangChain pipeline test"""
        self.log("🚀 Starting Comprehensive LangChain Pipeline Test")
        self.log("=" * 60)
        
        start_time = time.time()
        
        try:
            # Phase 1: Test crawling pipeline
            crawl_results = await self.test_crawling_pipeline()
            
            # Wait a bit for processing to complete
            await asyncio.sleep(2)
            
            # Phase 2: Test database storage
            storage_results = await self.test_database_storage()
            
            # Phase 3: Test keyword extraction quality
            extraction_results = await self.test_keyword_extraction_quality()
            
            # Phase 4: Test enhanced search (only if we have documents)
            if crawl_results.get("total_documents_stored", 0) > 0:
                search_results = await self.test_enhanced_search()
            else:
                self.log("⚠️ Skipping search tests - no documents were successfully crawled", "WARNING")
                search_results = {"skipped": True, "reason": "No documents available"}
            
            total_time = time.time() - start_time
            
            # Compile final results
            final_results = {
                "test_duration_seconds": round(total_time, 2),
                "crawling": crawl_results,
                "storage": storage_results,
                "keyword_extraction": extraction_results,
                "search": search_results,
                "errors": self.test_results["errors"],
                "overall_success": len(self.test_results["errors"]) == 0
            }
            
            # Print final summary
            self.log("=" * 60)
            self.log("🎯 COMPREHENSIVE TEST RESULTS")
            self.log("=" * 60)
            
            self.log(f"⏱️ Total Test Time: {total_time:.2f} seconds")
            self.log(f"🕷️ Crawling: {crawl_results.get('successful_crawls', 0)}/{crawl_results.get('total_crawls', 0)} successful")
            self.log(f"📚 Documents Stored: {crawl_results.get('total_documents_stored', 0)}")
            
            if storage_results and not storage_results.get("error"):
                self.log(f"🗄️ Database: {'✅' if storage_results.get('all_consistent') else '⚠️'} Consistent")
            
            self.log(f"🔍 Keyword Extraction: {extraction_results.get('average_improvement_ratio', 0):.2f}x improvement")
            
            if not search_results.get("skipped"):
                self.log(f"🔎 Search: {search_results.get('successful_searches', 0)}/{search_results.get('total_queries', 0)} successful")
                self.log(f"⚡ Avg Search Time: {search_results.get('average_search_time', 0):.2f}s")
            
            error_count = len(self.test_results["errors"])
            if error_count == 0:
                self.log("🎉 ALL TESTS PASSED - No errors encountered!")
            else:
                self.log(f"⚠️ {error_count} errors encountered:")
                for error in self.test_results["errors"]:
                    self.log(f"  - {error}")
            
            return final_results
            
        except Exception as e:
            self.log(f"❌ Comprehensive test failed with exception: {str(e)}", "ERROR")
            return {
                "error": str(e),
                "test_duration_seconds": time.time() - start_time,
                "errors": self.test_results["errors"]
            }


async def main():
    """Main test execution function"""
    try:
        # Initialize test runner
        test_runner = LangChainPipelineTest()
        
        # Run comprehensive test
        results = await test_runner.run_comprehensive_test()
        
        # Exit with proper code
        if results.get("overall_success", False) or len(results.get("errors", [])) == 0:
            print("\n✅ LangChain pipeline test completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ LangChain pipeline test completed with {len(results.get('errors', []))} errors")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())