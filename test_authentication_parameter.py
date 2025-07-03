#!/usr/bin/env python3
"""
Test script to verify the authentication parameter handling
"""

import sys
import os

# Add the src directory to the path to import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'api', 'src'))

from helpers.cognito_auth import extract_token_from_event

def test_authentication_parameter():
    """Test various authentication parameter scenarios"""
    
    print("Testing authentication parameter extraction...")
    
    # Test 1: authentication parameter in lowercase
    event1 = {
        'queryStringParameters': {
            'authentication': 'test-token-lowercase'
        }
    }
    token1 = extract_token_from_event(event1)
    print(f"Test 1 (lowercase 'authentication'): {token1}")
    assert token1 == 'test-token-lowercase', f"Expected 'test-token-lowercase', got '{token1}'"
    
    # Test 2: Authentication parameter with first letter capitalized
    event2 = {
        'queryStringParameters': {
            'Authentication': 'test-token-capitalized'
        }
    }
    token2 = extract_token_from_event(event2)
    print(f"Test 2 (capitalized 'Authentication'): {token2}")
    assert token2 == 'test-token-capitalized', f"Expected 'test-token-capitalized', got '{token2}'"
    
    # Test 3: AUTHENTICATION parameter in uppercase
    event3 = {
        'queryStringParameters': {
            'AUTHENTICATION': 'test-token-uppercase'
        }
    }
    token3 = extract_token_from_event(event3)
    print(f"Test 3 (uppercase 'AUTHENTICATION'): {token3}")
    assert token3 == 'test-token-uppercase', f"Expected 'test-token-uppercase', got '{token3}'"
    
    # Test 4: Legacy token parameter (should still work)
    event4 = {
        'queryStringParameters': {
            'token': 'test-token-legacy'
        }
    }
    token4 = extract_token_from_event(event4)
    print(f"Test 4 (legacy 'token'): {token4}")
    assert token4 == 'test-token-legacy', f"Expected 'test-token-legacy', got '{token4}'"
    
    # Test 5: Priority test - authentication should take precedence over token
    event5 = {
        'queryStringParameters': {
            'authentication': 'test-token-priority',
            'token': 'test-token-legacy-ignored'
        }
    }
    token5 = extract_token_from_event(event5)
    print(f"Test 5 (priority test): {token5}")
    assert token5 == 'test-token-priority', f"Expected 'test-token-priority', got '{token5}'"
    
    # Test 6: Authorization header (should still work)
    event6 = {
        'queryStringParameters': {},
        'headers': {
            'Authorization': 'Bearer test-token-header'
        }
    }
    token6 = extract_token_from_event(event6)
    print(f"Test 6 (Authorization header): {token6}")
    assert token6 == 'test-token-header', f"Expected 'test-token-header', got '{token6}'"
    
    # Test 7: No authentication parameter or header
    event7 = {
        'queryStringParameters': {
            'other_param': 'some_value'
        }
    }
    token7 = extract_token_from_event(event7)
    print(f"Test 7 (no authentication): {token7}")
    assert token7 is None, f"Expected None, got '{token7}'"
    
    print("\n✅ All tests passed! Authentication parameter handling is working correctly.")
    print("\nSupported parameter names:")
    print("- authentication (preferred)")
    print("- Authentication")  
    print("- AUTHENTICATION")
    print("- token (legacy support)")
    print("\nAlso supports Authorization header with Bearer token format.")

if __name__ == "__main__":
    test_authentication_parameter()
