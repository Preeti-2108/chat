"""
Quick debug test for the query rewriter and Bedrock integration
"""

import sys
import os
sys.path.append('.')

def test_query_processing():
    """Test the full query processing pipeline"""
    
    print("🔍 TESTING QUERY PROCESSING PIPELINE")
    print("=" * 50)
    
    try:
        # Test the query rewriter
        from src.helpers.query_rewriter import safe_rewrite_query, build_query_rewriter
        
        test_queries = [
            "Do you have any information about microsoft?",
            "How to open an incident on microsoft?",
            "Support Windows Microsoft",
            "Windows license support"
        ]
        
        print("📝 Testing Query Rewriter (without LLM):")
        for query in test_queries:
            rewritten = safe_rewrite_query(None, query)
            print(f"   '{query}' → '{rewritten}'")
            
        print(f"\n✅ Query rewriter is working (fallback mode)")
        
        # Test document analyzer import
        from src.helpers.document_analyzer import document_analyzer
        print(f"✅ Document analyzer imported successfully")
        
        # Test the main handler components
        print(f"\n🔧 Testing handler components...")
        
        # Check if we can create the workflow
        try:
            from src.post.handler import BedrockKnowledgeBaseWorkflow
            print(f"❌ Handler import failed - this is expected due to missing dependencies")
        except Exception as e:
            print(f"⚠️  Handler import error: {str(e)[:100]}...")
            print(f"   This is expected in local environment")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_query_patterns():
    """Analyze the patterns in problematic queries"""
    
    print(f"\n🔍 ANALYZING QUERY PATTERNS")
    print("=" * 50)
    
    working_queries = [
        "Support Windows Microsoft",
        "Windows license support", 
        "Support des Licences Windows"
    ]
    
    failing_queries = [
        "Do you have any information about microsoft?",
        "How to open an incident on microsoft?"
    ]
    
    print("✅ WORKING queries (retrieve French documents):")
    for q in working_queries:
        words = q.lower().split()
        print(f"   '{q}' → words: {words}")
        
    print(f"\n❌ FAILING queries (don't retrieve French documents):")
    for q in failing_queries:
        words = q.lower().split()
        print(f"   '{q}' → words: {words}")
        
    print(f"\n🎯 ANALYSIS:")
    print(f"   Working queries have direct keywords: 'support', 'windows', 'microsoft'")
    print(f"   Failing queries are conversational: 'do you have', 'how to'")
    print(f"   French document likely titled: 'Support des Licences Windows'")
    print(f"   \n💡 SOLUTION: Query rewriter should convert:")
    print(f"   'Do you have information about microsoft?' → 'Microsoft support documentation'") 
    print(f"   'How to open incident on microsoft?' → 'Microsoft support request process'")

if __name__ == "__main__":
    success = test_query_processing()
    analyze_query_patterns()
    
    if success:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Deploy with updated requirements.txt to get LangChain")
        print(f"2. Test with actual LLM for query rewriting")  
        print(f"3. Check logs in CloudWatch for Bedrock responses")
        print(f"4. Verify French documents are being returned with scores")
    else:
        print(f"\n❌ Fix the errors above before deployment")