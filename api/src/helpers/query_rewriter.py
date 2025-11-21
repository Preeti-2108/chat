"""
Fully Dynamic Query Rewriter for RAG Systems
"""

import logging
from typing import Optional
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain.schema.output_parser import JsonOutputParser

logger = logging.getLogger(__name__)

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

def build_query_rewriter(llm):
    if not llm:
        return None
    
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
