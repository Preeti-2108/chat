"""
Test script for Intent Detector streaming functionality
Verifies that simple responses use the same streaming pattern as LLM responses.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.intent_detector import (
    is_simple_query, 
    get_simple_response, 
    get_streaming_simple_response,
    create_mock_streaming_response,
    get_query_intent_info
)

def test_streaming_functionality():
    """Test the streaming functionality for simple responses"""
    
    print("🧪 Testing Intent Detector Streaming Functionality")
    print("=" * 60)
    
    test_cases = [
        "Hello!",
        "Thank you so much!",
        "Who are you?",
        "Goodbye!",
        "How are you doing today?",
        "What's a complex technical question about microservices?"  # This should NOT be simple
    ]
    
    for query in test_cases:
        print(f"\nQuery: '{query}'")
        
        # Check if it's a simple query
        is_simple = is_simple_query(query)
        print(f"  Is Simple: {is_simple}")
        
        if is_simple:
            # Test regular response
            simple_response = get_simple_response(query)
            print(f"  Response: '{simple_response}'")
            
            # Test streaming response generator
            print(f"  Streaming chunks:")
            chunks = list(get_streaming_simple_response(query))
            for i, chunk in enumerate(chunks):
                print(f"    Chunk {i+1}: '{chunk}'")
            
            # Test mock streaming response (for WordLevelStreamingHandler)
            print(f"  Mock streaming chunks:")
            mock_chunks = list(create_mock_streaming_response(simple_response))
            for i, chunk in enumerate(mock_chunks):
                print(f"    Mock Chunk {i+1}: '{chunk.content}'")
            
            # Test intent info
            intent_info = get_query_intent_info(query)
            print(f"  Processing Method: {intent_info['processing_method']}")
            print(f"  Estimated Latency: {intent_info['estimated_latency_ms']}ms")
        else:
            print(f"  → Needs RAG + LLM processing")
    
    print(f"\n✅ Streaming functionality test completed!")

def test_performance_comparison():
    """Compare performance between simple and complex queries"""
    
    print(f"\n📊 Performance Comparison")
    print("=" * 40)
    
    simple_queries = ["Hello!", "Thanks!", "Who are you?"]
    complex_queries = [
        "What are the best practices for Kubernetes deployment?",
        "Explain microservices architecture patterns",
        "How do I configure Docker networking?"
    ]
    
    print("Simple Queries (Optimized):")
    for query in simple_queries:
        intent_info = get_query_intent_info(query)
        print(f"  '{query[:30]}...' → {intent_info['estimated_latency_ms']}ms")
    
    print("\nComplex Queries (Needs RAG+LLM):")
    for query in complex_queries:
        intent_info = get_query_intent_info(query)
        latency = "Unknown (RAG+LLM dependent)" if intent_info['estimated_latency_ms'] is None else f"{intent_info['estimated_latency_ms']}ms"
        print(f"  '{query[:30]}...' → {latency}")

if __name__ == "__main__":
    test_streaming_functionality()
    test_performance_comparison()