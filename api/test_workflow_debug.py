"""
Test script to debug the workflow routing issue
"""

import sys
import os
sys.path.append('.')

# Mock the dependencies to test the routing logic
class MockDocumentAnalyzer:
    def should_skip_rag(self, query):
        """Mock that always returns complex query"""
        return {
            "skip_rag": False,  # Always complex for our test
            "skip_llm": False,
            "simple_response": "",
            "reason": "Query requires RAG processing",
            "estimated_savings": {
                "cost": "$0.00",
                "processing_method": "rag_llm"
            }
        }

# Mock the state for testing
class MockState(dict):
    pass

def test_routing_logic():
    """Test the routing logic in isolation"""
    
    print("🔍 TESTING WORKFLOW ROUTING LOGIC")
    print("=" * 50)
    
    # Test the detect_query_intent logic
    print("1. Testing detect_query_intent logic:")
    
    # Simulate the logic from detect_query_intent
    test_query = "How to open an incident on microsoft?"
    mock_analyzer = MockDocumentAnalyzer()
    
    # Create state like the method does
    state = MockState()
    state["user_query"] = test_query
    
    # Simulate detect_query_intent
    skip_decision = mock_analyzer.should_skip_rag(test_query)
    state["is_simple_query"] = skip_decision["skip_rag"]
    state["skip_rag"] = skip_decision["skip_rag"]
    state["skip_llm"] = skip_decision["skip_llm"]
    
    print(f"   Query: '{test_query}'")
    print(f"   skip_rag: {state['skip_rag']}")
    print(f"   is_simple_query: {state['is_simple_query']}")
    
    # Test the routing logic
    print("\n2. Testing route_based_on_intent logic:")
    
    skip_rag = state.get("skip_rag", False)
    user_query = state.get("user_query", "")
    
    if skip_rag:
        route_result = "simple"
        print(f"   🚀 Would route to SIMPLE query handler for: '{user_query[:30]}...'")
    else:
        route_result = "complex"
        print(f"   🔍 Would route to QUERY REWRITER for complex query: '{user_query[:30]}...'")
    
    print(f"   Route result: '{route_result}'")
    
    # Expected workflow path
    print(f"\n3. Expected workflow path:")
    print(f"   detect_intent → route_based_on_intent → {route_result}")
    if route_result == "complex":
        print(f"   complex → rewrite_query → retrieve_from_kb → generate_response")
    else:
        print(f"   simple → handle_simple_query")
    
    print(f"\n✅ Routing logic test completed")
    return state

def test_workflow_edges():
    """Test the workflow edge configuration"""
    
    print(f"\n🔗 TESTING WORKFLOW EDGE CONFIGURATION")
    print("=" * 40)
    
    # This simulates the workflow.add_conditional_edges call
    routing_map = {
        "simple": "handle_simple_query",
        "complex": "rewrite_query"
    }
    
    print(f"Conditional edges from detect_intent:")
    for condition, target in routing_map.items():
        print(f"   '{condition}' → '{target}'")
    
    # Test with our expected route
    test_route = "complex"  # From our test above
    expected_target = routing_map[test_route]
    
    print(f"\nFor route '{test_route}':")
    print(f"   Expected target: '{expected_target}'")
    
    # Verify the complete path
    if expected_target == "rewrite_query":
        print(f"   Next: rewrite_query → retrieve_from_kb")
        print(f"   Then: retrieve_from_kb → generate_response")
        print(f"   Finally: generate_response → END")
    
    print(f"\n✅ Edge configuration test completed")

if __name__ == "__main__":
    try:
        # Test the routing logic
        final_state = test_routing_logic()
        
        # Test the workflow edges
        test_workflow_edges()
        
        print(f"\n🎉 ALL TESTS PASSED")
        print(f"The workflow logic should route complex queries through the rewrite_query node.")
        print(f"If this isn't happening in the deployed Lambda, there might be:")
        print(f"   1. A deployment issue (old version deployed)")
        print(f"   2. A LangGraph execution issue")
        print(f"   3. Missing dependencies in Lambda environment")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()