"""
Fully Dynamic Query Rewriter for RAG Systems
Works with or without LangChain dependencies
"""

import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

# Try to import LangChain components, fallback if not available
try:
    from langchain.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableSequence
    from langchain.schema.output_parser import JsonOutputParser
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain components loaded successfully")
except ImportError:
    logger.warning("LangChain not available - using fallback query rewriter")
    LANGCHAIN_AVAILABLE = False

DYNAMIC_REWRITE_PROMPT = """
You are an intelligent Query Rewriter for document retrieval systems.

Transform the user query into the most effective form for finding relevant documents.

Core principles:
1. Preserve the user intent completely
2. Use formal technical language that appears in documentation
3. Be explicit - remove ambiguous words and pronouns
4. Convert questions into declarative search terms
5. Expand abbreviated terms to full forms
6. Use terminology that would appear in official documents

Transformation patterns:
- "How to X" becomes "Steps to X" or "Procedure for X"
- "Can I" becomes "Permission for" or "Authorization to"
- "Issue with" becomes "Troubleshooting" or "Problem resolution for"
- Informal terms become formal equivalents
- Brand names get full context
- Action words become process words

Output only the rewritten query in this JSON format:
{
  "rewritten_query": "<optimized query for document retrieval>"
}
"""

class DirectLLMRewriter:
    """
    Fallback query rewriter that works without LangChain
    """
    def __init__(self, llm):
        self.llm = llm
    
    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """
        Invoke the LLM directly for query rewriting
        """
        user_query = inputs.get("query", "")
        
        # Create a simple prompt
        prompt = f"{DYNAMIC_REWRITE_PROMPT}\n\nUser query: {user_query}"
        
        try:
            # Try to use the LLM directly
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke([{"role": "user", "content": prompt}])
                content = response.content if hasattr(response, 'content') else str(response)
            else:
                # Fallback for different LLM interfaces
                content = str(self.llm(prompt))
            
            # Try to parse JSON from response
            try:
                # Look for JSON in the response
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    result = json.loads(json_str)
                    return result
            except:
                pass
            
            # If JSON parsing fails, return original query
            return {"rewritten_query": user_query}
            
        except Exception as e:
            logger.error(f"DirectLLMRewriter failed: {e}")
            return {"rewritten_query": user_query}

def build_query_rewriter(llm):
    """
    Build query rewriter with or without LangChain
    """
    if not llm:
        logger.warning("No LLM provided for query rewriting")
        return None
    
    if LANGCHAIN_AVAILABLE:
        # Use LangChain if available
        prompt = ChatPromptTemplate.from_messages([
            ("system", DYNAMIC_REWRITE_PROMPT),
            ("user", "{query}")
        ])
        
        parser = JsonOutputParser()
        
        return RunnableSequence([
            prompt,
            llm,
            parser
        ])
    else:
        # Return a simple wrapper for direct LLM use
        logger.info("Using fallback query rewriter without LangChain")
        return DirectLLMRewriter(llm)

def safe_rewrite_query(rewriter, user_query: str) -> str:
    if not rewriter or not user_query:
        return user_query
        
    try:
        result = rewriter.invoke({"query": user_query})
        rewritten = result.get("rewritten_query", "").strip()
        
        if rewritten and len(rewritten) > 3 and rewritten != user_query:
            logger.info(f"Query rewritten: '{user_query}' -> '{rewritten}'")
            return rewritten
        else:
            return user_query
            
    except Exception as e:
        logger.error(f"Query rewriting failed: {e}")
        return user_query
