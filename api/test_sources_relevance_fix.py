"""
Test to verify that sources are not included when context is irrelevant
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.document_analyzer import build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions

def test_no_sources_when_irrelevant():
    """Test that sources are not included when documents don't answer the question"""
    
    print("🧪 Testing Sources Exclusion for Irrelevant Context")
    print("=" * 55)
    
    # Simulate the scenario you encountered
    user_query = "What is AI agent?"
    
    # Simulate retrieved documents that don't answer the question
    mock_documents = [
        {
            'content': 'Installation et déploiement de l\'agent Deep Security de Trend Micro pour la protection antivirus et sécurité.',
            'score': 0.65,
            'metadata': {
                'title': 'Installation et déploiement de l\'agent Deep Security de Trend Micro',
                'docLink': 'https://example.com/deep-security-doc'
            }
        }
    ]
    
    system_instructions = get_default_system_instructions()
    
    # Build the prompt as the system would
    prompt = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=mock_documents,
        user_query=user_query
    )
    
    print(f"User Query: '{user_query}'")
    print(f"Retrieved Document: 'Installation et déploiement de l'agent Deep Security...'")
    print()
    
    print("📋 Generated Prompt Analysis:")
    print("-" * 35)
    
    # Check if the prompt includes the critical instruction
    if "CRITICAL INSTRUCTION" in prompt:
        print("✅ Prompt includes CRITICAL INSTRUCTION about source inclusion")
    else:
        print("❌ Prompt missing CRITICAL INSTRUCTION")
    
    # Check if it tells AI to exclude sources for irrelevant context
    if "do NOT include any sources" in prompt:
        print("✅ Prompt instructs to exclude sources for irrelevant context")
    else:
        print("❌ Prompt doesn't clearly instruct to exclude sources")
    
    # Check if sources are provided but conditionally
    if "Available sources (ONLY include if you use the context to answer)" in prompt:
        print("✅ Sources provided conditionally")
    else:
        print("❌ Sources not provided conditionally")
    
    print("\n📄 Key Parts of the Prompt:")
    print("-" * 30)
    
    # Extract and show the critical instruction part
    lines = prompt.split('\n')
    in_critical_section = False
    
    for line in lines:
        if "CRITICAL INSTRUCTION" in line:
            in_critical_section = True
        elif line.startswith('Available sources') and in_critical_section:
            print(line)
            in_critical_section = False
        elif in_critical_section:
            print(line)

def test_system_instructions_update():
    """Test that system instructions have been updated correctly"""
    
    print(f"\n📋 System Instructions Analysis")
    print("=" * 35)
    
    system_instructions = get_default_system_instructions()
    
    # Check for key phrases
    checks = [
        ("CRITICAL: NEVER include sources", "Sources exclusion rule"),
        ("when the context documents do not actually answer", "Relevance check"),
        ("Only include sources when you can provide a meaningful answer", "Conditional sources rule")
    ]
    
    for phrase, description in checks:
        if phrase in system_instructions:
            print(f"✅ {description}: Found")
        else:
            print(f"❌ {description}: Missing")
    
    # Show the updated context-based information section
    print(f"\n📝 Context-Based Information Section:")
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

def test_expected_behavior():
    """Show expected behavior for the problematic scenario"""
    
    print(f"\n🎯 Expected Behavior for Your Scenario")
    print("=" * 45)
    
    scenario = {
        "user_query": "What is AI agent?",
        "retrieved_docs": ["Installation et déploiement de l'agent Deep Security de Trend Micro"],
        "expected_response": "I'm sorry, I don't have information about this in my knowledge base.",
        "should_include_sources": False,
        "reasoning": "Deep Security agent is about antivirus/security software, not AI agents"
    }
    
    print(f"User Query: '{scenario['user_query']}'")
    print(f"Retrieved: {scenario['retrieved_docs'][0][:50]}...")
    print(f"Expected Response: '{scenario['expected_response']}'")
    print(f"Should Include Sources: {scenario['should_include_sources']}")
    print(f"Reasoning: {scenario['reasoning']}")
    
    print(f"\n🔍 How the AI Should Reason:")
    print("1. User asks about 'AI agent'")
    print("2. Retrieved document is about 'Deep Security agent' (antivirus)")
    print("3. These are completely different topics")
    print("4. Context cannot answer the user's question")
    print("5. Response: Simple 'no information' message")
    print("6. Sources: EXCLUDED (context not relevant)")

def main():
    """Run all tests"""
    print("🚫 No Sources for Irrelevant Context - Fix Verification")
    print("=" * 60)
    
    test_no_sources_when_irrelevant()
    test_system_instructions_update()
    test_expected_behavior()
    
    print(f"\n✅ Summary of Changes:")
    print("   • Document analyzer now provides conditional sources instructions")
    print("   • AI told to exclude sources when context doesn't answer question")
    print("   • System instructions emphasize relevance-based source inclusion")
    print("   • Clear distinction between having documents vs having relevant documents")

if __name__ == "__main__":
    main()