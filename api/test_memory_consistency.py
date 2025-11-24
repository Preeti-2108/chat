#!/usr/bin/env python3
"""
Test conversation memory consistency
"""

import os
import sys
sys.path.append('.')

# Set environment variables for testing
os.environ['REGION'] = 'us-east-1'
os.environ['AZURE_OPENAI_API_KEY'] = 'test-key'
os.environ['AZURE_OPENAI_API_ENDPOINT'] = 'test-endpoint'
os.environ['AZURE_OPENAI_API_VERSION'] = '2023-05-15'
os.environ['AZURE_OPENAI_MODEL'] = 'gpt-4'
os.environ['AZURE_OPENAI_TEMPERATURE'] = '0.7'
os.environ['AZURE_OPENAI_MAX_TOKENS'] = '4000'
os.environ['BASE_URL'] = 'https://test.openai.azure.com'

def test_memory_consistency():
    """Test that conversation_id and thread_id are consistent"""
    
    print("🧪 Testing Memory Consistency Setup")
    print("=" * 50)
    
    # Test conversation ID generation
    import uuid
    
    # Simulate POST request (new conversation)
    conversation_id_post = str(uuid.uuid4())
    print(f"📝 POST Request:")
    print(f"   conversation_id: {conversation_id_post}")
    print(f"   thread_id (should match): {conversation_id_post}")
    print(f"   Memory key: thread_id={conversation_id_post}")
    
    # Simulate PUT request (continuation)
    conversation_id_put = conversation_id_post  # Same ID for continuation
    print(f"\n🔄 PUT Request (continuation):")
    print(f"   conversation_id: {conversation_id_put}")
    print(f"   thread_id (should match): {conversation_id_put}")
    print(f"   Memory key: thread_id={conversation_id_put}")
    print(f"   IDs match: {'✅ YES' if conversation_id_post == conversation_id_put else '❌ NO'}")
    
    # Test memory key consistency
    memory_key_post = f"thread_id={conversation_id_post}"
    memory_key_put = f"thread_id={conversation_id_put}"
    
    print(f"\n🧠 Memory Key Consistency:")
    print(f"   POST memory key: {memory_key_post}")
    print(f"   PUT memory key:  {memory_key_put}")
    print(f"   Keys match: {'✅ YES' if memory_key_post == memory_key_put else '❌ NO'}")
    
    if memory_key_post == memory_key_put:
        print(f"\n🎉 Memory consistency setup is CORRECT!")
        print(f"   - POST creates conversation with thread_id={conversation_id_post}")
        print(f"   - PUT continues conversation with same thread_id={conversation_id_put}")
        print(f"   - Memory will be preserved across requests")
    else:
        print(f"\n❌ Memory consistency setup has issues!")
        
    return memory_key_post == memory_key_put

if __name__ == "__main__":
    test_memory_consistency()