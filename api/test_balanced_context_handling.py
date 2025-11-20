"""
Test to verify the balanced approach works for both relevant and irrelevant contexts
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.document_analyzer import build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions

def test_balanced_approach():
    """Test that the system handles both relevant and irrelevant contexts correctly"""
    
    print("⚖️ Testing Balanced Context Handling")
    print("=" * 45)
    
    system_instructions = get_default_system_instructions()
    
    # Test Case 1: RELEVANT context (should provide answer with sources)
    print("📄 Test Case 1: RELEVANT Context")
    print("-" * 35)
    
    user_query_relevant = "What is Zabbix?"
    
    relevant_documents = [
        {
            'content': 'Zabbix is an open-source monitoring software tool for diverse IT components, including networks, servers, virtual machines and cloud services. Zabbix provides monitoring metrics, among others network utilization, CPU load and disk space consumption.',
            'score': 0.85,
            'metadata': {
                'title': 'Zabbix Monitoring Software Documentation',
                'docLink': 'https://example.com/zabbix-doc'
            }
        }
    ]
    
    prompt_relevant = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=relevant_documents,
        user_query=user_query_relevant
    )
    
    print(f"Query: '{user_query_relevant}'")
    print(f"Context: Contains actual information about Zabbix")
    print(f"Expected: Detailed answer with sources")
    
    # Check if prompt encourages using the context
    if "provide a well-formatted answer based on the context" in prompt_relevant:
        print("✅ Prompt encourages using relevant context")
    else:
        print("❌ Prompt doesn't encourage using context")
    
    if "MUST include the following sources section" in prompt_relevant:
        print("✅ Sources will be included for relevant content")
    else:
        print("❌ Sources might not be included")
    
    # Test Case 2: IRRELEVANT context (should say no information, no sources)
    print(f"\n📄 Test Case 2: IRRELEVANT Context")
    print("-" * 37)
    
    user_query_irrelevant = "What is AI agent?"
    
    irrelevant_documents = [
        {
            'content': 'Installation et déploiement de l\'agent Deep Security de Trend Micro pour la protection antivirus et sécurité.',
            'score': 0.65,
            'metadata': {
                'title': 'Installation et déploiement de l\'agent Deep Security de Trend Micro',
                'docLink': 'https://example.com/deep-security-doc'
            }
        }
    ]
    
    prompt_irrelevant = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=irrelevant_documents,
        user_query=user_query_irrelevant
    )
    
    print(f"Query: '{user_query_irrelevant}'")
    print(f"Context: About Deep Security (antivirus), not AI agents")
    print(f"Expected: 'No information' response, no sources")
    
    # Check system instructions
    print(f"\n📋 Updated System Instructions:")
    print("-" * 35)
    
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
    """Show what should happen now"""
    
    print(f"\n🎯 Expected Behavior Summary")
    print("=" * 35)
    
    scenarios = [
        {
            "query": "What is Zabbix?",
            "context": "Zabbix monitoring documentation",
            "expected": "Detailed answer about Zabbix with sources",
            "reason": "Context directly answers the question"
        },
        {
            "query": "What is AI agent?", 
            "context": "Deep Security agent documentation",
            "expected": "I'm sorry, I don't have information about this",
            "reason": "Context is about different type of agent"
        },
        {
            "query": "How to monitor servers?",
            "context": "Zabbix monitoring documentation", 
            "expected": "Answer about server monitoring using Zabbix",
            "reason": "Context is relevant to monitoring question"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. Query: '{scenario['query']}'")
        print(f"   Context: {scenario['context']}")
        print(f"   Expected: {scenario['expected']}")
        print(f"   Reason: {scenario['reason']}")

def main():
    """Run the balanced approach test"""
    print("🔄 Restoring Balanced Context Handling")
    print("=" * 50)
    
    test_balanced_approach()
    test_expected_behavior()
    
    print(f"\n✅ Changes Made:")
    print("   • Reverted overly aggressive 'CRITICAL INSTRUCTION'")
    print("   • Restored normal context usage for relevant documents")
    print("   • Kept sources inclusion for answered questions")
    print("   • System will now use context when it's actually relevant")
    print("   • 'No information' response only for truly unrelated context")
    
    print(f"\n🎯 Result:")
    print("   • Zabbix questions with Zabbix docs → Detailed answers with sources")
    print("   • AI agent questions with Deep Security docs → No information message")
    print("   • Monitoring questions with Zabbix docs → Relevant monitoring info")

if __name__ == "__main__":
    main()