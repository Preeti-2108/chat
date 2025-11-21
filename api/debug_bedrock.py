"""
Debug script to test Bedrock Knowledge Base responses
Run this to see what Bedrock returns for specific queries
"""

import boto3
import os
from botocore.config import Config

# Configuration (update these with your values)
KNOWLEDGE_BASE_ID = os.getenv('KNOWLEDGE_BASE_ID', 'YOUR_KB_ID')
AWS_REGION = os.getenv('REGION', 'us-east-1')

def test_bedrock_query(query: str, max_results: int = 5):
    """
    Test a specific query against Bedrock Knowledge Base
    """
    print(f"\n🔍 Testing query: '{query}'")
    print("=" * 50)
    
    try:
        # Setup Bedrock client
        config = Config(
            region_name=AWS_REGION,
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        bedrock_client = boto3.client('bedrock-agent-runtime', config=config)
        
        # Basic retrieval configuration
        retrieval_config = {
            'vectorSearchConfiguration': {
                'numberOfResults': max_results
            }
        }
        
        # Make the call
        response = bedrock_client.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration=retrieval_config
        )
        
        # Analyze results
        if 'retrievalResults' in response:
            results = response['retrievalResults']
            print(f"📊 Results found: {len(results)}")
            
            if not results:
                print("❌ No documents found!")
                return
            
            for i, result in enumerate(results):
                score = result.get('score', 0)
                content = result.get('content', {}).get('text', '')
                location = result.get('location', {})
                uri = location.get('s3Location', {}).get('uri', 'No URI')
                
                print(f"\n📄 Result {i+1}:")
                print(f"   Score: {score:.4f}")
                print(f"   URI: {uri}")
                print(f"   Content (first 300 chars): '{content[:300]}...'")
                
                # Check for key terms
                french_terms = ['licence', 'support des', 'windows', 'microsoft']
                english_terms = ['license', 'support', 'incident', 'ticket']
                
                found_french = [term for term in french_terms if term in content.lower()]
                found_english = [term for term in english_terms if term in content.lower()]
                
                print(f"   French terms found: {found_french}")
                print(f"   English terms found: {found_english}")
                print(f"   Likely language: {'French' if found_french else 'English' if found_english else 'Unknown'}")
                
        else:
            print("❌ No retrievalResults in response!")
            print(f"Response keys: {list(response.keys())}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Test problematic queries"""
    print("🔍 BEDROCK KNOWLEDGE BASE DEBUGGING")
    print("=" * 60)
    
    # Test the problematic queries
    test_queries = [
        "Do you have any information about microsoft?",
        "How to open an incident on microsoft?", 
        "Support Windows Microsoft",
        "Windows license support",
        "Support des Licences Windows",  # This should work
        "Microsoft support",
        "incident microsoft",
        "microsoft incident"
    ]
    
    for query in test_queries:
        test_bedrock_query(query, max_results=3)
        
    print(f"\n🎯 ANALYSIS COMPLETE")
    print("Look for:")
    print("- Are French documents being returned for English queries?")
    print("- What are the similarity scores?") 
    print("- Is the content relevant?")

if __name__ == "__main__":
    main()