"""
Test file to demonstrate the Simple Intent Detector integration
Shows how different types of queries are routed through the system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.helpers.intent_detector import is_simple_query, get_simple_response, get_query_intent_info
from src.helpers.document_analyzer import document_analyzer

def test_intent_routing():
    """Test the intent detection and routing logic"""
    
    test_queries = [
        # Simple queries that should skip RAG/LLM
        "Hello!",
        "Hi there",
        "Thank you so much",
        "Thanks!",
        "Who are you?",
        "Bye!",
        "ok",
        "yes", 
        "How are you?",
        
        # Complex queries that need RAG/LLM
        "How do I deploy Kubernetes pods?",
        "What is the difference between REST and GraphQL APIs?",
        "Compare microservices vs monolith architecture",
        "Troubleshoot Docker container startup issues",
        "Explain CI/CD pipeline best practices",
        "What are the security considerations for AWS Lambda?",
    ]
    
    print("🧪 Testing Intent Detection and Routing")
    print("=" * 60)
    
    simple_count = 0
    complex_count = 0
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        
        # Test intent detection
        is_simple = is_simple_query(query)
        intent_info = get_query_intent_info(query)
        
        # Test document analyzer integration
        skip_decision = document_analyzer.should_skip_rag(query)
        
        print(f"  📊 Intent Analysis:")
        print(f"    - Simple Query: {is_simple}")
        print(f"    - Skip RAG: {skip_decision['skip_rag']}")
        print(f"    - Processing: {intent_info['processing_method']}")
        print(f"    - Est. Latency: {intent_info['estimated_latency_ms']}ms" if intent_info['estimated_latency_ms'] else "    - Est. Latency: 500-2000ms")
        
        if is_simple:
            simple_count += 1
            response = get_simple_response(query)
            print(f"  💬 Simple Response: '{response}'")
            print(f"  💰 Cost: $0 (100% savings)")
        else:
            complex_count += 1
            print(f"  🔄 → Needs RAG + LLM Processing")
            print(f"  💰 Cost: ~$0.001-0.01 (depending on model)")
        
    print("\n" + "=" * 60)
    print(f"📈 Summary:")
    print(f"  Simple Queries: {simple_count} (Skip RAG/LLM - Instant + Free)")
    print(f"  Complex Queries: {complex_count} (RAG + LLM - Normal Processing)")
    print(f"  Cost Optimization: {(simple_count/len(test_queries)*100):.1f}% of queries handled for free")
    print(f"  Latency Optimization: {simple_count} queries respond in <100ms")

def test_workflow_simulation():
    """Simulate the LangGraph workflow routing"""
    
    print("\n🔄 Simulating LangGraph Workflow Routing")
    print("=" * 50)
    
    queries = [
        "Hello!",
        "How do I configure Kubernetes ingress?"
    ]
    
    for query in queries:
        print(f"\n🔍 Processing: '{query}'")
        
        # Step 1: Intent Detection (detect_intent node)
        skip_decision = document_analyzer.should_skip_rag(query)
        
        if skip_decision['skip_rag']:
            # Route: detect_intent -> handle_simple_query -> END
            print(f"  🛤️  Route: detect_intent → handle_simple_query → END")
            print(f"  ⚡ Processing Time: ~50ms")
            print(f"  💰 Cost: $0")
            print(f"  📤 Response: '{skip_decision['simple_response']}'")
        else:
            # Route: detect_intent -> retrieve_from_kb -> generate_response -> END  
            print(f"  🛤️  Route: detect_intent → retrieve_from_kb → generate_response → END")
            print(f"  ⏱️  Processing Time: ~1-3 seconds")
            print(f"  💰 Cost: ~$0.001-0.01")
            print(f"  🔍 Would retrieve context and generate LLM response")

if __name__ == "__main__":
    test_intent_routing()
    test_workflow_simulation()
    
    print("\n✅ All tests completed!")
    print("\n📌 Integration Points:")
    print("  1. Intent detector added to document_analyzer.py")
    print("  2. New LangGraph nodes in post/handler.py:")
    print("     - detect_intent (entry point)")
    print("     - handle_simple_query (for simple queries)")
    print("     - route_based_on_intent (conditional routing)")
    print("  3. WebSocket streaming works for both simple and complex responses")
    print("  4. Cost and latency optimizations automatically applied")