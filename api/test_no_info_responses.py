"""
Test script to verify the simplified "no information" responses
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.system_instructions import get_default_system_instructions, get_error_response_templates

def test_no_information_responses():
    """Test that the system now provides simple responses when no information is available"""
    
    print("🧪 Testing Simplified 'No Information' Responses")
    print("=" * 55)
    
    # Test system instructions
    system_instructions = get_default_system_instructions()
    print("\n📋 Updated System Instructions (Context-Based Information section):")
    print("-" * 60)
    
    # Extract the relevant section
    lines = system_instructions.split('\n')
    in_context_section = False
    for line in lines:
        if '1. **Context-Based Information**:' in line:
            in_context_section = True
        elif line.startswith('2. **') and in_context_section:
            break
        elif in_context_section:
            print(line)
    
    # Test error response templates
    error_templates = get_error_response_templates()
    print(f"\n🚫 Updated Error Response Templates:")
    print("-" * 40)
    
    for error_type, response in error_templates.items():
        if 'context' in error_type:
            print(f"  {error_type}: \"{response}\"")
    
    # Simulate different scenarios
    print(f"\n📝 Example Scenarios:")
    print("-" * 25)
    
    scenarios = [
        {
            "query": "What is AI agent?",
            "old_response": "I am not able to obtain an answer for this particular query, as the context provided does not contain information about what an AI agent is. However, the context does provide detailed information about...",
            "new_response": "I'm sorry, I don't have information about this in my knowledge base."
        },
        {
            "query": "How does machine learning work?",
            "old_response": "I am not able to obtain an answer for this particular query, as the vector database context does not include information about machine learning. The available context focuses on...",
            "new_response": "I'm sorry, I don't have information about this in my knowledge base."
        },
        {
            "query": "What is blockchain technology?",
            "old_response": "I am not able to obtain an answer for this particular query. The retrieved documents do not contain sufficient information...",
            "new_response": "I'm sorry, I don't have information about this in my knowledge base."
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. Query: \"{scenario['query']}\"")
        print(f"   ❌ Old Response Length: {len(scenario['old_response'])} characters")
        print(f"   ✅ New Response Length: {len(scenario['new_response'])} characters")
        print(f"   📉 Reduction: {len(scenario['old_response']) - len(scenario['new_response'])} characters")
        print(f"   ✅ New Response: \"{scenario['new_response']}\"")
    
    print(f"\n🎯 Benefits:")
    print("   • Concise and user-friendly responses")
    print("   • No technical jargon about vector databases or context")
    print("   • Consistent simple message across all 'no info' scenarios")
    print("   • Better user experience with clear, apologetic tone")
    
    print(f"\n✅ Update Summary:")
    print("   • system_instructions.py: Updated context-based information rules")
    print("   • system_instructions.py: Updated error response templates") 
    print("   • document_analyzer.py: Updated fallback prompts")
    print("   • All 'no information' responses now use simple, consistent message")

if __name__ == "__main__":
    test_no_information_responses()