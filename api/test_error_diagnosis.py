"""
Comprehensive test to identify potential runtime issues that could cause internal server errors
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_imports():
    """Test all imports to identify missing dependencies"""
    print("🔍 Testing Imports...")
    
    try:
        from src.helpers.intent_detector import (
            is_simple_query, 
            get_simple_response, 
            create_mock_streaming_response,
            get_query_intent_info
        )
        print("✅ Intent detector imports successful")
    except Exception as e:
        print(f"❌ Intent detector import error: {e}")
        return False
    
    try:
        from src.helpers.system_instructions import (
            get_default_system_instructions, 
            get_error_response_templates
        )
        print("✅ System instructions imports successful")
    except Exception as e:
        print(f"❌ System instructions import error: {e}")
        return False
    
    try:
        from src.helpers.document_analyzer import document_analyzer
        print("✅ Document analyzer imports successful")
    except Exception as e:
        print(f"❌ Document analyzer import error: {e}")
        return False
    
    return True

def test_intent_detector_functionality():
    """Test intent detector functions for runtime errors"""
    print("\n🧪 Testing Intent Detector Functions...")
    
    try:
        from src.helpers.intent_detector import (
            is_simple_query, 
            get_simple_response, 
            create_mock_streaming_response
        )
        
        # Test with valid inputs
        test_queries = ["hello", "thank you", "what is kubernetes?", ""]
        
        for query in test_queries:
            try:
                is_simple = is_simple_query(query)
                response = get_simple_response(query)
                stream_gen = create_mock_streaming_response(response)
                chunks = list(stream_gen)  # Consume generator
                
                print(f"✅ Query '{query}' processed successfully")
            except Exception as e:
                print(f"❌ Error processing query '{query}': {e}")
                return False
        
        # Test with edge cases
        edge_cases = [None, 123, [], {}]
        for case in edge_cases:
            try:
                is_simple = is_simple_query(case)
                response = get_simple_response(case)
                print(f"✅ Edge case {type(case)} handled")
            except Exception as e:
                print(f"❌ Error with edge case {type(case)}: {e}")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Intent detector functionality error: {e}")
        return False

def test_system_instructions():
    """Test system instructions for formatting issues"""
    print("\n📋 Testing System Instructions...")
    
    try:
        from src.helpers.system_instructions import (
            get_default_system_instructions, 
            get_error_response_templates
        )
        
        instructions = get_default_system_instructions()
        templates = get_error_response_templates()
        
        # Check if instructions are properly formatted
        if not isinstance(instructions, str) or len(instructions) < 100:
            print("❌ System instructions appear malformed")
            return False
            
        # Check if templates are properly formatted
        if not isinstance(templates, dict) or len(templates) == 0:
            print("❌ Error templates appear malformed")
            return False
            
        print("✅ System instructions properly formatted")
        return True
        
    except Exception as e:
        print(f"❌ System instructions error: {e}")
        return False

def test_mock_streaming_compatibility():
    """Test mock streaming response compatibility with WordLevelStreamingHandler"""
    print("\n🔄 Testing Mock Streaming Compatibility...")
    
    try:
        from src.helpers.intent_detector import create_mock_streaming_response
        
        response_text = "Hello! How can I help you today?"
        mock_generator = create_mock_streaming_response(response_text)
        
        # Test that generator yields objects with content attribute
        chunks = list(mock_generator)
        
        for i, chunk in enumerate(chunks):
            if not hasattr(chunk, 'content'):
                print(f"❌ Chunk {i} missing 'content' attribute")
                return False
            
            if not isinstance(chunk.content, str):
                print(f"❌ Chunk {i} content is not string: {type(chunk.content)}")
                return False
        
        print(f"✅ Mock streaming generated {len(chunks)} valid chunks")
        return True
        
    except Exception as e:
        print(f"❌ Mock streaming compatibility error: {e}")
        return False

def test_document_analyzer_syntax():
    """Test document analyzer for syntax issues"""
    print("\n📄 Testing Document Analyzer...")
    
    try:
        from src.helpers.document_analyzer import build_context_aware_prompt
        
        # Test with minimal parameters
        test_prompt = build_context_aware_prompt(
            user_query="test query",
            context_documents=[],
            system_instructions="test instructions"
        )
        
        if not isinstance(test_prompt, str):
            print("❌ build_context_aware_prompt not returning string")
            return False
            
        # Check if the new simple message is properly formatted
        if '"I\'m sorry, I don\'t have information about this in my knowledge base." ' not in test_prompt:
            print("❌ Updated message not found in prompt")
            return False
            
        print("✅ Document analyzer functioning properly")
        return True
        
    except Exception as e:
        print(f"❌ Document analyzer error: {e}")
        return False

def main():
    """Run all tests"""
    print("🔧 Internal Server Error Diagnostic Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_intent_detector_functionality,
        test_system_instructions,
        test_mock_streaming_compatibility,
        test_document_analyzer_syntax
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\n🚨 POTENTIAL ISSUE FOUND IN: {test.__name__}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed - code should work without internal server errors")
        print("\n🔍 If you're still getting internal server errors, check:")
        print("   • Environment variables (AZURE_OPENAI_API_KEY, etc.)")
        print("   • Network connectivity to Azure OpenAI")
        print("   • DynamoDB table permissions")
        print("   • Lambda function memory/timeout settings")
    else:
        print("❌ Issues found - these may cause internal server errors")

if __name__ == "__main__":
    main()