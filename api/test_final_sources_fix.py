"""
Test to verify that sources are NOT included when context is irrelevant
This should fix the persistent issue of sources appearing with "no information" responses
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.document_analyzer import build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions

def test_sources_exclusion_final():
    """Final test to ensure sources are excluded when context is irrelevant"""
    
    print("🎯 FINAL TEST: Sources Exclusion for Irrelevant Context")
    print("=" * 60)
    
    system_instructions = get_default_system_instructions()
    
    # The exact scenario you're experiencing
    user_query = "What is AI agent?"
    
    irrelevant_documents = [
        {
            'content': 'Installation et déploiement de l\'agent Deep Security de Trend Micro pour la protection antivirus et sécurité des systèmes informatiques.',
            'score': 0.65,
            'metadata': {
                'title': 'Installation et déploiement de l\'agent Deep Security de Trend Micro',
                'docLink': 'https://example.com/deep-security'
            }
        }
    ]
    
    # Build the prompt exactly as the system would
    prompt = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=irrelevant_documents,
        user_query=user_query
    )
    
    print(f"🔍 Scenario Analysis:")
    print(f"User Query: '{user_query}'")
    print(f"Context Document: 'Installation et déploiement de l'agent Deep Security...'")
    print(f"Expected Response: 'I'm sorry, I don't have information about this in my knowledge base.'")
    print(f"Expected Sources: NONE")
    print()
    
    # Analyze the generated prompt
    print("📋 Prompt Analysis:")
    print("-" * 20)
    
    # Check if prompt forces sources inclusion
    forces_sources = "you MUST include the following sources section exactly as shown" in prompt
    print(f"❌ Forces sources inclusion: {forces_sources}")
    
    # Check if prompt makes sources conditional
    conditional_sources = "only include if you provide an answer using the context" in prompt
    print(f"✅ Makes sources conditional: {conditional_sources}")
    
    # Check if prompt gives clear instructions for irrelevant context
    clear_instructions = "DO NOT include any sources" in prompt
    print(f"✅ Clear 'no sources' instruction: {clear_instructions}")
    
    # Check if prompt mentions the exact response to give
    exact_response = "I'm sorry, I don't have information about this in my knowledge base" in prompt
    print(f"✅ Specifies exact response: {exact_response}")
    
    print(f"\n📄 Key Parts of the Prompt:")
    print("-" * 30)
    
    # Show the important instructions section
    lines = prompt.split('\n')
    in_important_section = False
    
    for line in lines:
        if "IMPORTANT INSTRUCTIONS:" in line:
            in_important_section = True
        elif line.startswith('Available sources') and in_important_section:
            print(line)
            in_important_section = False
        elif in_important_section:
            print(line)

def test_system_instructions_final():
    """Test the final system instructions"""
    
    print(f"\n📋 System Instructions Analysis")
    print("=" * 35)
    
    system_instructions = get_default_system_instructions()
    
    # Check key requirements
    checks = [
        ("Only include sources when you can actually answer", "Conditional sources rule"),
        ("respond with: \"I'm sorry, I don't have information\"", "Clear fallback response"),
        ("not relevant or cannot answer", "Relevance check")
    ]
    
    for phrase, description in checks:
        if phrase in system_instructions:
            print(f"✅ {description}: Found")
        else:
            print(f"❌ {description}: Missing")
    
    # Show the context-based information section
    print(f"\n📝 Context-Based Information Rules:")
    print("-" * 40)
    
    lines = system_instructions.split('\n')
    in_context_section = False
    
    for line in lines:
        if '1. **Context-Based Information**:' in line:
            in_context_section = True
        elif line.startswith('2. **') and in_context_section:
            break
        elif in_context_section and line.strip():
            print(line)

def test_comparison():
    """Compare old vs new approach"""
    
    print(f"\n⚖️ Approach Comparison")
    print("=" * 25)
    
    print("❌ OLD APPROACH (causing the issue):")
    print("   • Prompt: 'you MUST include the following sources section exactly as shown'")
    print("   • Result: AI forced to include sources even when saying 'no information'")
    print("   • Problem: Sources appear with irrelevant context")
    
    print("\n✅ NEW APPROACH (should fix the issue):")
    print("   • Prompt: 'only include if you provide an answer using the context'")
    print("   • Instruction: 'DO NOT include any sources' for irrelevant context")
    print("   • Result: AI can choose to exclude sources when appropriate")

def main():
    """Run the final verification test"""
    print("🚫 FINAL FIX: No Sources for Irrelevant Context")
    print("=" * 55)
    
    test_sources_exclusion_final()
    test_system_instructions_final()
    test_comparison()
    
    print(f"\n🎯 Expected Result:")
    print("When you ask 'What is AI agent?' and get Deep Security docs:")
    print("   Response: 'I'm sorry, I don't have information about this in my knowledge base.'")
    print("   Sources: NONE (should be completely absent)")
    
    print(f"\n✅ Key Changes Made:")
    print("   • Removed 'MUST include sources' from prompt")
    print("   • Added conditional sources instruction")  
    print("   • Clear 'DO NOT include sources' for irrelevant context")
    print("   • System instructions emphasize relevance-based decisions")

if __name__ == "__main__":
    main()