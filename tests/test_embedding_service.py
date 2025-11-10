"""
Test Embedding Service in Isolation

This script tests the embedding service to verify:
1. Model loading
2. Query embedding generation
3. Document embedding generation
4. Embedding dimensions
5. Basic functionality
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from webnexus.services.embedding_service import embedding_service


async def test_embedding_service():
    """Test the embedding service in isolation."""
    print("=" * 60)
    print("🧪 Testing Embedding Service")
    print("=" * 60)
    
    # Test 1: Check if model can be loaded
    print("\n[TEST 1] Checking model initialization...")
    try:
        # Force model loading by getting model info
        model_info = embedding_service.get_model_info()
        
        if embedding_service.model is None:
            print("❌ Model failed to load")
            return False
        
        print(f"✅ Model loaded successfully")
        print(f"   Model name: {model_info.get('model_name')}")
        print(f"   Device: {model_info.get('device')}")
        print(f"   Dimension: {model_info.get('dimension')}")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Generate query embeddings
    print("\n[TEST 2] Generating query embeddings...")
    try:
        test_queries = [
            "What is machine learning?",
            "How to use Python for data science?",
            "LangChain tutorial"
        ]
        
        query_embeddings = await embedding_service.embed_queries(test_queries)
        
        print(f"✅ Generated {len(query_embeddings)} query embeddings")
        print(f"   Embedding dimension: {len(query_embeddings[0])}")
        print(f"   Expected dimension: 1024")
        
        if len(query_embeddings[0]) != 1024:
            print(f"❌ Wrong embedding dimension: expected 1024, got {len(query_embeddings[0])}")
            return False
            
        # Check that embeddings are different
        if query_embeddings[0] == query_embeddings[1]:
            print("❌ All embeddings are identical (should be different)")
            return False
        
        print("✅ Query embeddings are unique")
        
    except Exception as e:
        print(f"❌ Error generating query embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Generate document embeddings
    print("\n[TEST 3] Generating document embeddings...")
    try:
        test_documents = [
            "Machine learning is a subset of artificial intelligence.",
            "Python is a popular programming language for data science.",
            "LangChain is a framework for building LLM applications."
        ]
        
        doc_embeddings = await embedding_service.embed_documents(test_documents)
        
        print(f"✅ Generated {len(doc_embeddings)} document embeddings")
        print(f"   Embedding dimension: {len(doc_embeddings[0])}")
        
        if len(doc_embeddings[0]) != 1024:
            print(f"❌ Wrong embedding dimension: expected 1024, got {len(doc_embeddings[0])}")
            return False
        
        print("✅ Document embeddings have correct dimension")
        
    except Exception as e:
        print(f"❌ Error generating document embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Verify query vs document embedding differences
    print("\n[TEST 4] Comparing query and document embeddings...")
    try:
        # Generate embeddings for the same text as query and document
        test_text = "LangChain is a framework for LLM applications"
        
        query_emb = await embedding_service.embed_queries([test_text])
        doc_emb = await embedding_service.embed_documents([test_text])
        
        # They should be different (query uses s2p_query prompt)
        if query_emb[0] == doc_emb[0]:
            print("⚠️ Query and document embeddings are identical (expected to be different due to prompts)")
        else:
            print("✅ Query and document embeddings are different (as expected)")
        
    except Exception as e:
        print(f"❌ Error comparing embeddings: {e}")
        return False
    
    # Test 5: Check embedding statistics
    print("\n[TEST 5] Checking embedding statistics...")
    try:
        stats = embedding_service.get_model_info()
        
        print(f"✅ Model statistics:")
        print(f"   Model name: {stats.get('model_name')}")
        print(f"   Device: {stats.get('device')}")
        print(f"   Embedding dimension: {stats.get('embedding_dimension')}")
        print(f"   Max sequence length: {stats.get('max_sequence_length')}")
        
    except Exception as e:
        print(f"❌ Error getting model info: {e}")
        return False
    
    # Test 6: Test batch processing
    print("\n[TEST 6] Testing batch processing...")
    try:
        # Create a larger batch
        large_batch = [f"This is test document number {i}" for i in range(20)]
        
        batch_embeddings = await embedding_service.embed_documents(large_batch)
        
        print(f"✅ Generated {len(batch_embeddings)} embeddings in batch")
        print(f"   All have dimension {len(batch_embeddings[0])}")
        
        if len(batch_embeddings) != 20:
            print(f"❌ Wrong number of embeddings: expected 20, got {len(batch_embeddings)}")
            return False
        
        print("✅ Batch processing works correctly")
        
    except Exception as e:
        print(f"❌ Error in batch processing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("🎉 ALL EMBEDDING SERVICE TESTS PASSED!")
    print("=" * 60)
    return True


async def main():
    """Main test execution."""
    try:
        success = await test_embedding_service()
        
        if success:
            print("\n✅ Embedding service is working correctly")
            sys.exit(0)
        else:
            print("\n❌ Embedding service has issues")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())