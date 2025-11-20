"""
Query Rewriting and Expansion Helper

This module improves semantic similarity by rewriting user queries into multiple variations
that are more likely to match document content. Addresses the core issue where users
phrase queries differently than document terminology.

Key Features:
- Terminology mapping (e.g., "incident" → "support request", "ticket")
- Query expansion with synonyms and related terms
- Context-aware rewriting based on domain (Microsoft, Kubernetes, etc.)
- Multiple query variations for better vector search coverage
"""

import logging
import re
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI

logger = logging.getLogger(__name__)

class QueryRewriter:
    """
    Advanced query rewriting for improved semantic similarity in RAG systems.
    Transforms user queries into document-friendly variations.
    """
    
    def __init__(self):
        self.terminology_mappings = self._build_terminology_mappings()
        self.domain_expansions = self._build_domain_expansions()
    
    def _build_terminology_mappings(self) -> Dict[str, List[str]]:
        """Build mappings from user terms to document terms"""
        return {
            # Support/Incident terminology
            "incident": ["support request", "support ticket", "help request", "service request"],
            "open incident": ["create support request", "submit support ticket", "new support case"],
            "file incident": ["create support request", "submit support ticket"],
            "raise ticket": ["create support request", "submit support case"],
            
            # Action mappings
            "open": ["create", "submit", "start", "initiate"],
            "file": ["create", "submit", "report"],
            "raise": ["create", "submit", "escalate"],
            
            # Microsoft specific
            "microsoft": ["microsoft azure", "azure", "office 365", "microsoft 365"],
            
            # Technical terms
            "deploy": ["deployment", "configure", "setup", "install"],
            "issue": ["problem", "error", "trouble", "failure"],
            "setup": ["configure", "install", "deployment", "initialization"]
        }
    
    def _build_domain_expansions(self) -> Dict[str, List[str]]:
        """Build domain-specific query expansions"""
        return {
            "microsoft": [
                "azure portal", "microsoft support", "azure support", "office 365 admin",
                "microsoft 365", "azure subscription", "microsoft technical support"
            ],
            "kubernetes": [
                "k8s", "container orchestration", "pod deployment", "cluster management",
                "kubectl", "kubernetes cluster", "container deployment"
            ],
            "docker": [
                "containerization", "docker container", "docker image", "container runtime",
                "docker compose", "container deployment"
            ],
            "support": [
                "help desk", "technical support", "customer service", "support center",
                "help center", "assistance", "troubleshooting"
            ]
        }
    
    def rewrite_query_basic(self, user_query: str) -> List[str]:
        """
        Basic query rewriting using terminology mappings and expansions.
        Fast method that doesn't require LLM calls.
        """
        query_lower = user_query.lower()
        rewritten_queries = [user_query]  # Always include original
        
        # Apply terminology mappings
        for user_term, doc_terms in self.terminology_mappings.items():
            if user_term in query_lower:
                for doc_term in doc_terms:
                    # Replace term while preserving context
                    new_query = re.sub(
                        r'\b' + re.escape(user_term) + r'\b', 
                        doc_term, 
                        user_query, 
                        flags=re.IGNORECASE
                    )
                    if new_query != user_query and new_query not in rewritten_queries:
                        rewritten_queries.append(new_query)
        
        # Apply domain expansions
        for domain, expansions in self.domain_expansions.items():
            if domain in query_lower:
                for expansion in expansions:
                    # Add domain-specific context
                    expanded_query = f"{user_query} {expansion}"
                    if expanded_query not in rewritten_queries:
                        rewritten_queries.append(expanded_query)
        
        # Generate procedural variations for "how to" queries
        if "how to" in query_lower:
            # Extract the action part
            action_match = re.search(r'how to (.+)', query_lower)
            if action_match:
                action = action_match.group(1)
                procedural_variations = [
                    f"steps to {action}",
                    f"process for {action}",
                    f"{action} procedure",
                    f"{action} guide",
                    f"instructions for {action}"
                ]
                rewritten_queries.extend(procedural_variations)
        
        # Limit to top 5 variations to avoid overwhelming the system
        return rewritten_queries[:5]
    
    def rewrite_query_advanced(self, user_query: str, llm_model=None) -> List[str]:
        """
        Advanced query rewriting using LLM for contextual understanding.
        More accurate but requires LLM call - use for complex queries.
        """
        if not llm_model:
            # Fallback to basic rewriting if no LLM available
            return self.rewrite_query_basic(user_query)
        
        try:
            rewrite_prompt = f"""
You are a query rewriting expert for a technical documentation search system.

Original Query: "{user_query}"

Rewrite this query into 3-4 variations that would better match technical documentation:

1. Use formal technical terminology (e.g., "incident" → "support request")
2. Add specific product context (e.g., "microsoft" → "microsoft azure")  
3. Use document-style language (e.g., "how to open" → "procedure to create")
4. Include procedural keywords (e.g., "steps", "process", "guide")

Return only the rewritten queries, one per line, without numbers or bullets.
Focus on terminology that would appear in official technical documentation.
"""

            messages = [HumanMessage(content=rewrite_prompt)]
            response = llm_model.invoke(messages)
            
            # Parse LLM response
            llm_queries = []
            if hasattr(response, 'content'):
                lines = response.content.strip().split('\n')
                for line in lines:
                    cleaned_line = line.strip().strip('•-*123456789. ')
                    if cleaned_line and len(cleaned_line) > 5:
                        llm_queries.append(cleaned_line)
            
            # Combine with basic rewriting for comprehensive coverage
            basic_queries = self.rewrite_query_basic(user_query)
            all_queries = basic_queries + llm_queries
            
            # Remove duplicates while preserving order
            seen = set()
            unique_queries = []
            for query in all_queries:
                if query.lower() not in seen:
                    seen.add(query.lower())
                    unique_queries.append(query)
            
            return unique_queries[:6]  # Limit to 6 total variations
            
        except Exception as e:
            logger.error(f"Advanced query rewriting failed: {e}")
            return self.rewrite_query_basic(user_query)
    
    def select_best_rewrite_strategy(self, user_query: str, complexity: str) -> str:
        """
        Select the appropriate rewriting strategy based on query complexity.
        """
        query_lower = user_query.lower()
        
        # Use advanced rewriting for complex support/incident queries
        if any(term in query_lower for term in ["incident", "support", "how to", "troubleshoot"]):
            return "advanced"
        
        # Use advanced for multi-part or comparison queries
        if any(term in query_lower for term in ["compare", "difference", "vs", "versus", "multiple"]):
            return "advanced"
        
        # Use basic for simple queries or when LLM not needed
        return "basic"
    
    def get_query_variations(self, user_query: str, complexity: str = "moderate", llm_model=None) -> Dict[str, Any]:
        """
        Main method to get query variations with metadata.
        
        Returns:
            Dictionary with variations, strategy used, and metadata
        """
        strategy = self.select_best_rewrite_strategy(user_query, complexity)
        
        if strategy == "advanced" and llm_model:
            variations = self.rewrite_query_advanced(user_query, llm_model)
        else:
            variations = self.rewrite_query_basic(user_query)
        
        return {
            "original_query": user_query,
            "variations": variations,
            "strategy": strategy,
            "variation_count": len(variations),
            "complexity": complexity,
            "has_llm_rewrite": strategy == "advanced" and llm_model is not None
        }

# Global instance for easy import
query_rewriter = QueryRewriter()

def rewrite_query_for_better_similarity(user_query: str, complexity: str = "moderate", llm_model=None) -> List[str]:
    """
    Convenience function to get query variations for improved similarity.
    
    Args:
        user_query: Original user query
        complexity: Query complexity level
        llm_model: Optional LLM model for advanced rewriting
        
    Returns:
        List of query variations ordered by expected relevance
    """
    result = query_rewriter.get_query_variations(user_query, complexity, llm_model)
    return result["variations"]

# Example usage and testing
if __name__ == "__main__":
    test_queries = [
        "How to open an incident on microsoft?",
        "Do you have any information about microsoft?", 
        "How to deploy kubernetes pods?",
        "Microsoft support ticket creation",
        "Troubleshoot docker container issues"
    ]
    
    print("🔧 Testing Query Rewriting:")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\nOriginal: \"{query}\"")
        variations = query_rewriter.rewrite_query_basic(query)
        
        print("Variations:")
        for i, variation in enumerate(variations, 1):
            print(f"  {i}. {variation}")