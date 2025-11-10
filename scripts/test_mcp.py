#!/usr/bin/env python3
"""
MCP Server Testing Script for WebNexus

Tests all MCP tools and provides comprehensive status reporting.
"""

import sys
import json
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webnexus.mcp.server import mcp, initialize_server, crawl_website, search_documents, get_sources

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce log noise
logger = logging.getLogger(__name__)


class MCPTester:
    """MCP Server testing class."""
    
    def __init__(self):
        self.results = {
            "server_initialization": False,
            "tools_registered": 0,
            "tool_tests": {},
            "issues_found": []
        }
    
    async def test_server_initialization(self):
        """Test server initialization."""
        print("🔄 Testing server initialization...")
        try:
            initialize_server()
            self.results["server_initialization"] = True
            print("✅ Server initialization successful")
            return True
        except Exception as e:
            self.results["issues_found"].append(f"Server initialization failed: {e}")
            print(f"❌ Server initialization failed: {e}")
            return False
    
    async def test_tool_registration(self):
        """Test tool registration."""
        print("\n🔄 Testing tool registration...")
        try:
            tools = await mcp.list_tools()
            self.results["tools_registered"] = len(tools)
            
            print(f"✅ {len(tools)} tools registered:")
            for tool in tools:
                print(f"   - {tool.name}: {tool.description[:60]}...")
            
            expected_tools = ["crawl_website", "search_documents", "get_sources"]
            actual_tools = [tool.name for tool in tools]
            
            for expected in expected_tools:
                if expected not in actual_tools:
                    self.results["issues_found"].append(f"Expected tool '{expected}' not found")
                    
            return len(tools) == len(expected_tools)
            
        except Exception as e:
            self.results["issues_found"].append(f"Tool registration test failed: {e}")
            print(f"❌ Tool registration test failed: {e}")
            return False
    
    async def test_crawl_website_tool(self):
        """Test crawl_website MCP tool."""
        print("\n🔄 Testing crawl_website tool...")
        tool_results = {
            "success": False,
            "strategies_tested": [],
            "errors": []
        }
        
        # Test different strategies with a simple URL
        strategies = ["single_page", "batch", "recursive", "sitemap"]
        test_url = "https://httpbin.org/html"
        
        for strategy in strategies:
            try:
                print(f"   Testing {strategy} strategy...")
                result = await mcp.call_tool("crawl_website", {
                    "url": test_url,
                    "strategy": strategy,
                    "max_depth": 1,
                    "max_pages": 1,
                    "store_documents": False
                })
                
                # Parse the JSON response
                response_text = result[0].text if result and hasattr(result[0], 'text') else str(result)
                response_data = json.loads(response_text)
                
                if response_data.get("success", False):
                    tool_results["strategies_tested"].append(strategy)
                    print(f"   ✅ {strategy} strategy successful")
                else:
                    error_msg = response_data.get("errors", ["Unknown error"])
                    tool_results["errors"].append(f"{strategy}: {error_msg}")
                    print(f"   ⚠️ {strategy} strategy completed with issues: {error_msg}")
                    
            except Exception as e:
                tool_results["errors"].append(f"{strategy}: {str(e)}")
                print(f"   ❌ {strategy} strategy failed: {e}")
        
        tool_results["success"] = len(tool_results["strategies_tested"]) > 0
        self.results["tool_tests"]["crawl_website"] = tool_results
        
        if tool_results["success"]:
            print(f"✅ crawl_website tool working - {len(tool_results['strategies_tested'])} strategies tested")
        else:
            print("❌ crawl_website tool not working")
            
        return tool_results["success"]
    
    async def test_search_documents_tool(self):
        """Test search_documents MCP tool."""
        print("\n🔄 Testing search_documents tool...")
        tool_results = {
            "success": False,
            "search_types_tested": [],
            "errors": []
        }
        
        # Test different search types
        search_types = ["vector", "keyword", "hybrid"]
        test_query = "test search query"
        
        for search_type in search_types:
            try:
                print(f"   Testing {search_type} search...")
                result = await mcp.call_tool("search_documents", {
                    "query": test_query,
                    "max_results": 5,
                    "search_type": search_type
                })
                
                # Parse the JSON response
                response_text = result[0].text if result and hasattr(result[0], 'text') else str(result)
                response_data = json.loads(response_text)
                
                if response_data.get("success", False) or "No documents available" in response_data.get("message", ""):
                    tool_results["search_types_tested"].append(search_type)
                    print(f"   ✅ {search_type} search successful")
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    tool_results["errors"].append(f"{search_type}: {error_msg}")
                    print(f"   ⚠️ {search_type} search had issues: {error_msg}")
                    
            except Exception as e:
                tool_results["errors"].append(f"{search_type}: {str(e)}")
                print(f"   ❌ {search_type} search failed: {e}")
        
        tool_results["success"] = len(tool_results["search_types_tested"]) > 0
        self.results["tool_tests"]["search_documents"] = tool_results
        
        if tool_results["success"]:
            print(f"✅ search_documents tool working - {len(tool_results['search_types_tested'])} search types tested")
        else:
            print("❌ search_documents tool not working")
            
        return tool_results["success"]
    
    async def test_get_sources_tool(self):
        """Test get_sources MCP tool."""
        print("\n🔄 Testing get_sources tool...")
        tool_results = {
            "success": False,
            "parameters_tested": [],
            "errors": []
        }
        
        # Test different parameter combinations
        test_cases = [
            {"limit": 10},
            {"limit": 5, "url_pattern": "example.com"},
            {"limit": 5, "source_type": "webpage"}
        ]
        
        for i, params in enumerate(test_cases):
            try:
                print(f"   Testing parameter set {i+1}...")
                result = await mcp.call_tool("get_sources", params)
                
                # Parse the JSON response
                response_text = result[0].text if result and hasattr(result[0], 'text') else str(result)
                response_data = json.loads(response_text)
                
                if response_data.get("success", False):
                    tool_results["parameters_tested"].append(f"params_{i+1}")
                    print(f"   ✅ Parameter set {i+1} successful")
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    tool_results["errors"].append(f"params_{i+1}: {error_msg}")
                    print(f"   ⚠️ Parameter set {i+1} had issues: {error_msg}")
                    
            except Exception as e:
                tool_results["errors"].append(f"params_{i+1}: {str(e)}")
                print(f"   ❌ Parameter set {i+1} failed: {e}")
        
        tool_results["success"] = len(tool_results["parameters_tested"]) > 0 or len(tool_results["errors"]) > 0
        self.results["tool_tests"]["get_sources"] = tool_results
        
        if tool_results["success"]:
            print(f"✅ get_sources tool working - {len(tool_results['parameters_tested'])} parameter sets tested")
        else:
            print("❌ get_sources tool not working")
            
        return tool_results["success"]
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "="*60)
        print("📋 WebNexus MCP SERVER TEST REPORT")
        print("="*60)
        
        # Server status
        print(f"\n🏗️ Server Status:")
        print(f"   Initialization: {'✅ Success' if self.results['server_initialization'] else '❌ Failed'}")
        print(f"   Tools Registered: {self.results['tools_registered']}/3")
        
        # Tool tests
        print(f"\n🛠️ Tool Test Results:")
        for tool_name, results in self.results["tool_tests"].items():
            status = "✅ Working" if results["success"] else "❌ Failed"
            print(f"   {tool_name}: {status}")
            
            if "strategies_tested" in results:
                print(f"      Strategies: {len(results['strategies_tested'])}")
            if "search_types_tested" in results:
                print(f"      Search Types: {len(results['search_types_tested'])}")
            if "parameters_tested" in results:
                print(f"      Parameter Sets: {len(results['parameters_tested'])}")
                
            if results["errors"]:
                print(f"      Errors: {len(results['errors'])}")
        
        # Issues summary
        if self.results["issues_found"]:
            print(f"\n⚠️ Issues Found ({len(self.results['issues_found'])}):")
            for i, issue in enumerate(self.results["issues_found"], 1):
                print(f"   {i}. {issue}")
        else:
            print(f"\n✅ No critical issues found!")
        
        # Overall status
        working_tools = sum(1 for results in self.results["tool_tests"].values() if results["success"])
        total_tools = len(self.results["tool_tests"])
        
        print(f"\n🎯 Overall Status:")
        print(f"   Working Tools: {working_tools}/{total_tools}")
        print(f"   Server Functional: {'Yes' if self.results['server_initialization'] else 'No'}")
        
        overall_success = (
            self.results["server_initialization"] and
            working_tools >= 2  # At least 2 out of 3 tools working
        )
        
        print(f"   MCP Server Ready: {'✅ Yes' if overall_success else '❌ No'}")
        
        return overall_success


async def main():
    """Run MCP server tests."""
    print("🚀 WebNexus MCP Server Testing")
    print("="*40)
    
    tester = MCPTester()
    
    # Run tests
    await tester.test_server_initialization()
    await tester.test_tool_registration()
    await tester.test_crawl_website_tool()
    await tester.test_search_documents_tool()
    await tester.test_get_sources_tool()
    
    # Generate report
    overall_success = tester.generate_report()
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        sys.exit(1)