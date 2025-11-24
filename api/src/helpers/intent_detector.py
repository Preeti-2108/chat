"""
Simple Intent Detector
Handles basic queries without needing RAG or LLM processing for cost and speed optimization.
"""

import logging
import time
from typing import Dict, Any, Generator

logger = logging.getLogger(__name__)

def is_simple_query(text: str) -> bool:
    """
    Detect if a query is simple and can be handled with predefined responses.
    
    Args:
        text: User input text
        
    Returns:
        True if query is simple, False if it needs RAG/LLM processing
    """
    if not text or not isinstance(text, str):
        return False
        
    text = text.lower().strip()
    
    # Simple greeting and conversation keywords
    simple_keywords = [
        # Greetings
        "hi", "hello", "hey", "good morning", "good evening", "good afternoon",
        "greetings", "howdy", "what's up", "wassup",
        
        # Thanks and acknowledgments
        "thank you", "thanks", "thx", "appreciate", "grateful",
        
        # Confirmations
        "ok", "okay", "alright", "sure", "yes", "no", "yep", "nope",
        "got it", "understood", "makes sense", "sounds good",
        
        # Basic identity questions
        "who are you", "what is your name", "what are you", "introduce yourself",
        
        # Name introductions  
        "my name is", "i am", "i'm", "call me", "you can call me",
        
        # Farewells
        "bye", "goodbye", "see you", "farewell", "catch you later", "take care",
        "talk to you later", "ttyl", "see ya",
        
        # Basic status/health checks
        "how are you", "what's up", "how's it going", "how are things",
        
        # Simple affirmations
        "great", "awesome", "perfect", "excellent", "wonderful", "nice",
        "cool", "good job", "well done"
    ]
    
    # Check for exact keyword matches
    for kw in simple_keywords:
        if kw in text:
            return True
    
    # Also treat very short messages as potentially simple
    word_count = len(text.split())
    if word_count <= 2:
        return True
    
    # Check for simple yes/no or one-word responses
    if text in ["yes", "no", "y", "n", "true", "false", "1", "0"]:
        return True
    
    return False

def get_simple_response(user_input: str) -> str:
    """
    Generate appropriate response for simple queries.
    
    Args:
        user_input: The user's simple query
        
    Returns:
        Predefined response string
    """
    if not user_input or not isinstance(user_input, str):
        return "Hello! How can I help you today?"
    
    user_input = user_input.lower().strip()
    
    # Specific greetings with time-based responses
    if "good morning" in user_input:
        return "Good morning! I hope you're having a great start to your day. How can I assist you?"
    
    if "good evening" in user_input:
        return "Good evening! I hope you've had a wonderful day. What can I help you with?"
    
    if "good afternoon" in user_input:
        return "Good afternoon! I hope your day is going well. How can I assist you?"
    
    # Name introductions - when someone introduces themselves (check this FIRST before general greetings)
    if ("my name is" in user_input or 
        "call me" in user_input or
        "you can call me" in user_input or
        (("i am" in user_input or "i'm" in user_input) and 
         not any(adj in user_input for adj in ["happy", "sad", "tired", "busy", "good", "fine", "ok", "great", "looking", "asking", "trying"]))):
        return "How are you doing? It's nice to meet you! How can I help you today?"
    
    # General greetings
    if any(greeting in user_input for greeting in ["hi", "hello", "hey"]):
        return "Hello! I'm here to help you with your questions. What would you like to know?"
    
    # Thanks
    if any(thanks in user_input for thanks in ["thank", "thx", "appreciate", "grateful"]):
        return "You're welcome! I'm glad I could help. Is there anything else you'd like to know?"
    
    # Identity questions
    if any(identity in user_input for identity in ["who are you", "what is your name", "what are you", "introduce"]):
        return "I'm your AI assistant, here to help answer your questions and provide information. How can I assist you today?"
    
    # Farewells
    if any(farewell in user_input for farewell in ["bye", "goodbye", "see you", "farewell", "take care"]):
        return "Goodbye! Have a great day! Feel free to come back if you have more questions."
    
    # Status checks
    if any(status in user_input for status in ["how are you", "what's up", "how's it going"]):
        return "I'm doing well and ready to help! What can I assist you with today?"
    
    # Confirmations and acknowledgments
    if any(confirm in user_input for confirm in ["ok", "okay", "alright", "sure", "got it", "understood"]):
        return "Great! Is there anything else I can help you with?"
    
    # Positive responses
    if any(positive in user_input for positive in ["great", "awesome", "perfect", "excellent", "wonderful", "nice", "cool"]):
        return "I'm glad to hear that! Is there anything else you'd like to know or discuss?"
    
    # Yes/No responses
    if user_input in ["yes", "y", "yep", "yeah"]:
        return "Understood! How can I help you further?"
    
    if user_input in ["no", "n", "nope", "nah"]:
        return "No problem! Let me know if you need anything else."
    
    # Default fallback for simple queries that don't match specific patterns
    return "Hello! I'm here to help you with your questions. What would you like to know?"
    # Generic fallback for other simple queries
    return "I'm here to help! Please feel free to ask me any questions you have."

def get_query_intent_info(user_input: str) -> Dict[str, Any]:
    """
    Get detailed information about the query intent for logging/analytics.
    
    Args:
        user_input: User query string
        
    Returns:
        Dictionary with intent classification details
    """
    is_simple = is_simple_query(user_input)
    
    intent_info = {
        "is_simple": is_simple,
        "word_count": len(user_input.split()) if user_input else 0,
        "character_count": len(user_input) if user_input else 0,
        "requires_rag": not is_simple,
        "requires_llm": not is_simple,
        "estimated_cost": 0.0 if is_simple else None,  # Simple queries cost nothing
        "estimated_latency_ms": 50 if is_simple else None  # Simple queries are very fast
    }
    
    if is_simple:
        intent_info["response_type"] = "predefined"
        intent_info["processing_method"] = "rule_based"
    else:
        intent_info["response_type"] = "generated"
        intent_info["processing_method"] = "rag_llm"
    
    return intent_info

def get_streaming_simple_response(user_input: str) -> Generator[str, None, None]:
    """
    Get a streaming simple response that simulates LLM word-by-word streaming.
    This maintains consistency with the existing streaming pattern.
    
    Args:
        user_input: User query text
        
    Yields:
        Individual words/chunks of the response for streaming
    """
    response = get_simple_response(user_input)
    
    # Split response into words for streaming
    words = response.split()
    
    for i, word in enumerate(words):
        # Add natural streaming delay (very small to maintain speed advantage)
        if i > 0:  # Don't delay the first word
            time.sleep(0.01)  # 10ms delay between words for natural feel
        
        # Yield word with space (except for last word)
        if i < len(words) - 1:
            yield word + " "
        else:
            yield word

def create_mock_streaming_response(response_text: str):
    """
    Create a mock streaming response object that matches LangChain's streaming interface.
    This allows simple responses to work with the existing WordLevelStreamingHandler.
    
    Args:
        response_text: The complete response text
        
    Returns:
        Generator that yields mock response chunks
    """
    class MockStreamingChunk:
        def __init__(self, content: str):
            self.content = content
            
        def __str__(self):
            return self.content
    
    words = response_text.split()
    
    for i, word in enumerate(words):
        # Small delay for natural streaming feel
        if i > 0:
            time.sleep(0.01)
            
        # Yield mock chunk with content
        if i < len(words) - 1:
            yield MockStreamingChunk(word + " ")
        else:
            yield MockStreamingChunk(word)

# Example usage and testing
if __name__ == "__main__":
    test_queries = [
        "Hello!",
        "Thank you so much",
        "How do I deploy Kubernetes pods?",
        "What is Docker?",
        "Bye!",
        "Who are you?",
        "ok",
        "Compare microservices vs monolith architecture",
        "Hey there",
        "What's the difference between REST and GraphQL APIs?"
    ]
    
    print("🧪 Testing Intent Detector:")
    print("=" * 50)
    
    for query in test_queries:
        is_simple = is_simple_query(query)
        intent_info = get_query_intent_info(query)
        
        print(f"Query: '{query}'")
        print(f"  Simple: {is_simple}")
        print(f"  Method: {intent_info['processing_method']}")
        
        if is_simple:
            response = get_simple_response(query)
            print(f"  Response: '{response}'")
        else:
            print(f"  → Needs RAG + LLM processing")
        print()