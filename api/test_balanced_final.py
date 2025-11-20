"""
Test the balanced approach that should:
1. Answer Zabbix questions when Zabbix context is available
2. Say "no information" for AI agent questions when only Deep Security context is available
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.helpers.document_analyzer import build_context_aware_prompt
from src.helpers.system_instructions import get_default_system_instructions

def test_zabbix_scenario():
    """Test that Zabbix questions get answered when Zabbix context is available"""
    
    print("✅ Test 1: SHOULD ANSWER - Zabbix Query with Zabbix Context")
    print("=" * 60)
    
    user_query = "What is Zabbix?"
    
    # Relevant Zabbix documents
    zabbix_documents = [
        {
            'content': 'Zabbix is an open-source monitoring software tool for diverse IT components, including networks, servers, virtual machines and cloud services. Zabbix provides monitoring metrics, among others network utilization, CPU load and disk space consumption. It offers monitoring via SNMP, ICMP, HTTP and other protocols.',
            'score': 0.95,
            'metadata': {
                'title': 'Zabbix Monitoring Software Documentation',
                'docLink': 'https://example.com/zabbix-docs'
            }
        }
    ]
    
    system_instructions = get_default_system_instructions()
    prompt = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=zabbix_documents,
        user_query=user_query
    )
    
    print(f"Query: '{user_query}'")
    print(f"Context: Contains detailed Zabbix information")
    print(f"Expected: Detailed answer about Zabbix WITH sources")
    
    # Check if prompt encourages answering
    if "provide comprehensive answers based on the available context" in system_instructions:
        print("✅ System encourages using relevant context")
    else:
        print("❌ System doesn't encourage using context")
    
    # Check if prompt allows sources inclusion
    if "Sources to include when answering:" in prompt:
        print("✅ Sources available for inclusion")
    else:
        print("❌ Sources not available")
    
    # Check if context looks comprehensive
    context_in_prompt = "Zabbix is an open-source monitoring software" in prompt
    print(f"✅ Context contains Zabbix info: {context_in_prompt}")

def test_irrelevant_scenario():
    """Test that AI agent questions don't get answered with Deep Security context"""
    
    print(f"\n❌ Test 2: SHOULD NOT ANSWER - AI Agent Query with Deep Security Context")
    print("=" * 70)
    
    user_query = "What is AI agent?"
    
    # Irrelevant Deep Security documents
    irrelevant_documents = [
        {
            'content': 'Installation et déploiement de l\'agent Deep Security de Trend Micro pour la protection antivirus et sécurité des systèmes informatiques. L\'agent Deep Security offre une protection en temps réel contre les logiciels malveillants.',
            'score': 0.65,
            'metadata': {
                'title': 'Installation et déploiement de l\'agent Deep Security de Trend Micro',
                'docLink': 'https://example.com/deep-security'
            }
        }
    ]
    
    system_instructions = get_default_system_instructions()
    prompt = build_context_aware_prompt(
        system_instructions=system_instructions,
        context_documents=irrelevant_documents,
        user_query=user_query
    )
    
    print(f"Query: '{user_query}'")
    print(f"Context: Contains Deep Security (antivirus) information")
    print(f"Expected: 'No information' response WITHOUT sources")
    
    # Check if prompt gives example of unrelated context
    if "completely unrelated to the question" in prompt:
        print("✅ Prompt mentions unrelated context scenarios")
    else:
        print("❌ Prompt doesn't guide on unrelated context")
    
    # Check the specific example given
    if "AI agents" in prompt and "antivirus software" in prompt:
        print("✅ Prompt gives specific example matching this scenario")
    else:
        print("❌ Prompt doesn't give specific guidance for this scenario")

def analyze_system_instructions():
    """Analyze the updated system instructions"""
    
    print(f"\n📋 System Instructions Analysis")
    print("=" * 35)
    
    system_instructions = get_default_system_instructions()
    
    # Check for balanced approach indicators
    checks = [
        ("provide comprehensive answers", "Encourages answering when possible"),
        ("when it relates to the user's question", "Requires relevance"),
        ("if the context is completely unrelated", "Clear exclusion criteria"),
        ("thoroughly", "Encourages detailed responses")
    ]
    
    for phrase, description in checks:
        if phrase in system_instructions:
            print(f"✅ {description}: Found")
        else:
            print(f"❌ {description}: Missing")
    
    # Show the context-based information section
    print(f"\n📝 Context-Based Rules:")
    print("-" * 25)
    
    lines = system_instructions.split('\n')
    in_context_section = False
    
    for line in lines:
        if '1. **Context-Based Information**:' in line:
            in_context_section = True
        elif line.startswith('2. **') and in_context_section:
            break
        elif in_context_section and line.strip():
            print(line)

def main():
    """Test the balanced approach"""
    print("⚖️ BALANCED APPROACH TEST: Fix Both Scenarios")
    print("=" * 55)
    
    test_zabbix_scenario()
    test_irrelevant_scenario()
    analyze_system_instructions()
    
    print(f"\n🎯 Expected Results:")
    print("1. Zabbix question → Detailed Zabbix answer + sources")
    print("2. AI agent question → 'No information' response, no sources")
    
    print(f"\n✅ Key Changes:")
    print("   • Removed overly restrictive instructions")
    print("   • Encouraged using context when it's relevant")
    print("   • Kept exclusion for truly unrelated context")
    print("   • Gave specific example (AI agents vs antivirus)")
    print("   • Made sources conditional but not forced")

if __name__ == "__main__":
    main()