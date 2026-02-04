"""
Document Analysis Helper
Handles document selection, complexity assessment, and source formatting.
Reduces redundancy in document processing logic.
Now includes simple query detection for optimization.
"""

import logging
from typing import List, Dict, Any
from .intent_detector import is_simple_query, get_simple_response, get_query_intent_info

logger = logging.getLogger(__name__)

class DocumentAnalyzer:
    """Handles analysis and selection of optimal documents for AI responses."""
    
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.max_context_tokens = max_tokens * 0.6  # Reserve 40% for response
    
    def assess_query_complexity(self, user_query: str) -> str:
        """
        Assess query complexity to determine retrieval strategy.
        Now includes simple query detection to skip RAG/LLM for basic interactions.
        
        Args:
            user_query: The user's query string
            
        Returns:
            'simple', 'moderate', or 'complex'
        """
        # First check if it's a simple conversational query
        if is_simple_query(user_query):
            logger.info("Detected simple conversational query")
            return 'simple'
        
        query_lower = user_query.lower()
        
        # Complex query patterns
        complex_patterns = [
            'multiple', 'several', 'various', 'different',
            'compare', 'versus', 'vs', 'difference between',
            'troubleshoot', 'diagnose', 'analyze', 'investigate',
            'step by step', 'detailed', 'comprehensive',
            'issue', 'problem', 'error', 'failure', 'bug',
            'and', '&', 'also', 'additionally', 'furthermore'
        ]
        
        # Simple query patterns  
        simple_patterns = [
            'what is', 'define', 'meaning of',
            'how to', 'show me', 'explain',
            'list', 'give me', 'provide'
        ]
        
        complex_score = sum(1 for pattern in complex_patterns if pattern in query_lower)
        simple_score = sum(1 for pattern in simple_patterns if pattern in query_lower)
        
        # Additional complexity indicators
        word_count = len(user_query.split())
        has_technical_terms = any(term in query_lower for term in [
            'kubernetes', 'docker', 'pod', 'container', 'service',
            'deployment', 'configmap', 'secret', 'ingress', 'api', 'database'
        ])
        
        if complex_score >= 2 or word_count > 15 or (complex_score >= 1 and has_technical_terms):
            return 'complex'
        elif simple_score >= 1 and word_count <= 8:
            return 'simple'
        else:
            return 'moderate'
    
    def should_skip_rag(self, user_query: str) -> Dict[str, Any]:
        """
        Determine if the query should skip RAG processing entirely.
        
        Args:
            user_query: The user's query string
            
        Returns:
            Dictionary with skip decision and simple response if applicable
        """
        intent_info = get_query_intent_info(user_query)
        
        if intent_info["is_simple"]:
            simple_response = get_simple_response(user_query)
            logger.info(f"Query can skip RAG - Simple conversational query detected")
            
            return {
                "skip_rag": True,
                "skip_llm": True, 
                "simple_response": simple_response,
                "reason": "Simple conversational query",
                "estimated_savings": {
                    "cost": "100%",
                    "latency_ms": intent_info["estimated_latency_ms"],
                    "processing_method": intent_info["processing_method"]
                }
            }
        
        return {
            "skip_rag": False,
            "skip_llm": False,
            "simple_response": None,
            "reason": "Complex query requires RAG + LLM processing"
        }
    
    def select_optimal_documents(self, context_documents: List[Dict], user_query: str) -> List[Dict]:
        """
        Select optimal documents based on query complexity and token limits.
        
        Args:
            context_documents: List of document dictionaries with 'content', 'score', etc.
            user_query: The user's query string
            
        Returns:
            List of selected documents optimized for the query
        """
        if not context_documents:
            return []
            
        query_complexity = self.assess_query_complexity(user_query)
        
        # Simple query indicators
        query_lower = user_query.lower()
        is_complex_query = query_complexity == 'complex'
        is_simple_query = query_complexity == 'simple'
        
        current_tokens = 0
        selected_docs = []
        
        # Sort documents by relevance score (highest first)
        sorted_docs = sorted(context_documents, key=lambda x: x.get('score', 0), reverse=True)
        
        # Log the scores for debugging
        scores_preview = [f"{doc.get('score', 0):.3f}" for doc in sorted_docs[:5]]
        logger.info(f"Document scores: {', '.join(scores_preview)}")
        
        # 🔍 DEBUG: Log query complexity assessment
        logger.info(f"🔍 [DOC SELECTION] Query complexity assessed as: '{query_complexity}'")
        logger.info(f"🔍 [DOC SELECTION] Available documents: {len(sorted_docs)}")
        logger.info(f"🔍 [DOC SELECTION] Max context tokens: {self.max_context_tokens}")
        
        for doc in sorted_docs:
            content = doc.get('content', '').strip()
            doc_score = doc.get('score', 0)
            
            # Skip documents with no content
            if not content or len(content) < 10:
                logger.warning(f"Skipping document with insufficient content (length: {len(content)})")
                continue
            
            doc_tokens = len(content) / 4  # Rough token estimation
            
            # 🔧 LOWERED THRESHOLDS: More inclusive document selection
            # Check if this is a Microsoft-related query
            is_microsoft_query = any(term in user_query.lower() for term in ['microsoft', 'incident', 'support', 'ticket'])
            
            # Use lower thresholds for Microsoft queries
            if is_microsoft_query:
                threshold_complex = 0.1  # Very low threshold
                threshold_simple = 0.1
                threshold_default = 0.1
                logger.info(f"🔧 [MICROSOFT] Using low thresholds for Microsoft query")
            else:
                threshold_complex = 0.25  # Lowered from 0.3
                threshold_simple = 0.3    # Lowered from 0.5  
                threshold_default = 0.3   # Lowered from 0.4
            
            # Decision logic based on query complexity
            if is_complex_query:
                # For complex queries, prioritize more documents up to token limit
                if (current_tokens + doc_tokens <= self.max_context_tokens and 
                    len(selected_docs) < 4 and doc_score > threshold_complex):
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Complex query: Added document with score {doc_score:.3f} (threshold: {threshold_complex})")
            elif is_simple_query:
                # For simple queries, use fewer but highest-quality documents
                if (len(selected_docs) < 1 or 
                    (len(selected_docs) < 2 and doc_score > threshold_simple)):
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Simple query: Added document with score {doc_score:.3f} (threshold: {threshold_simple})")
            else:
                # Default behavior for moderate complexity
                if len(selected_docs) < 3 and doc_score > threshold_default:
                    selected_docs.append(doc)
                    current_tokens += doc_tokens
                    logger.info(f"Default: Added document with score {doc_score:.3f} (threshold: {threshold_default})")
            
            # Stop if we've reached reasonable limits
            if current_tokens >= self.max_context_tokens:
                logger.info(f"Token limit reached. Using {len(selected_docs)} documents.")
                break
        
        # 🔧 IMPROVED FALLBACK: Be more aggressive about including documents
        if not selected_docs and sorted_docs:
            # Take top 2 documents as fallback instead of just 1
            logger.warning(f"⚠️ [DOC SELECTION] No documents met thresholds! Using aggressive fallback...")
            for i, doc in enumerate(sorted_docs[:2]):
                if doc.get('content', '').strip():
                    selected_docs.append(doc)
                    logger.info(f"🔧 Aggressive fallback: Added document {i+1} with score {doc.get('score', 0):.3f}")
        
        # 🔍 SPECIAL CASE: For Microsoft/incident queries, be extra lenient
        if len(selected_docs) == 0:
            query_lower = user_query.lower()
            if any(term in query_lower for term in ['microsoft', 'incident', 'support', 'ticket']):
                logger.warning(f"🚨 [MICROSOFT QUERY] No documents selected for Microsoft query! Using emergency fallback...")
                # Take ALL available documents for Microsoft queries
                for doc in sorted_docs[:3]:
                    if doc.get('content', '').strip():
                        selected_docs.append(doc)
                        logger.info(f"🚨 Emergency: Added Microsoft doc with score {doc.get('score', 0):.3f}")
        
        scores_list = [f"{doc.get('score', 0):.3f}" for doc in selected_docs]
        logger.info(f"✅ [DOC SELECTION] Final selection: {len(selected_docs)} documents. Scores: {scores_list}")
        
        if len(selected_docs) == 0:
            logger.error(f"❌ [DOC SELECTION] CRITICAL: No documents selected despite {len(sorted_docs)} available!")
        
        return selected_docs
    
    def assess_context_relevance(self, user_query: str, selected_docs: List[Dict]) -> float:
        """
        Assess if the selected documents are relevant to the user's query using semantic matching.
        
        Args:
            user_query: The user's question
            selected_docs: List of selected document dictionaries
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not selected_docs or not user_query:
            return 0.0
        
        query_lower = user_query.lower()
        
        # Extract key concepts from the query
        query_keywords = set()
        
        # Common synonyms and cross-language mappings
        concept_mappings = {
            'incident': ['incident', 'ticket', 'support', 'problem', 'issue'],
            'microsoft': ['microsoft', 'ms', 'office', 'windows', 'azure'],
            'open': ['open', 'create', 'ouvrir', 'créer', 'new', 'submit'],
            'support': ['support', 'help', 'aide', 'assistance', 'service'],
            'procedure': ['procedure', 'procédure', 'process', 'steps', 'how'],
            'licence': ['license', 'licence', 'licensing', 'activation', 'key']
        }
        
        # Find concepts in query
        for concept, synonyms in concept_mappings.items():
            if any(synonym in query_lower for synonym in synonyms):
                query_keywords.add(concept)
        
        # Score documents based on concept overlap
        total_score = 0.0
        max_possible_score = 0.0
        
        for doc in selected_docs:
            content = doc.get('content', '').lower()
            doc_score = doc.get('score', 0.0)
            
            # Count concept matches in document
            concept_matches = 0
            for concept, synonyms in concept_mappings.items():
                if concept in query_keywords:
                    max_possible_score += 1.0
                    if any(synonym in content for synonym in synonyms):
                        concept_matches += 1
            
            # Weighted by document score from Bedrock
            document_relevance = (concept_matches / max(len(query_keywords), 1)) * doc_score
            total_score += document_relevance
        
        # Normalize score
        if max_possible_score > 0:
            final_score = min(total_score / max_possible_score, 1.0)
        else:
            final_score = 0.0
        
        logger.info(f"🎯 [RELEVANCE] Query concepts: {query_keywords}")
        logger.info(f"🎯 [RELEVANCE] Relevance score: {final_score:.3f}")
        
        return final_score
    
    def build_sources_text(self, selected_docs: List[Dict]) -> str:
        """
        Build formatted sources text with clickable links for inclusion in AI responses.
        
        Args:
            selected_docs: List of selected document dictionaries
            
        Returns:
            Formatted sources text with markdown links
        """
        if not selected_docs:
            return ""
        
        sources_lines = ["", "---", "**Sources:**"]
        
        for i, doc in enumerate(selected_docs, 1):
            metadata = doc.get('metadata', {})
            title = metadata.get('title', f'Document {i}')
            doc_link = metadata.get('docLink', '')
            
            if doc_link:
                # Create markdown link format
                source_line = f"{i}. [{title}]({doc_link})"
            else:
                # Just show the title if no link available
                source_line = f"{i}. {title}"
            
            sources_lines.append(source_line)
        
        # Add instruction for AI to include these sources
        sources_text = "\n".join(sources_lines)
        sources_text += "\n\n**INSTRUCTION: Include the above sources at the end of your response when answering based on the provided context.**"
        
        return sources_text
    
    def build_context_string(self, selected_docs: List[Dict]) -> str:
        """
        Build the context string from selected documents.
        
        Args:
            selected_docs: List of selected document dictionaries
            
        Returns:
            Concatenated context string with document separators
        """
        if not selected_docs:
            return ""
        
        return "\n\n---DOCUMENT SEPARATOR---\n\n".join([
            doc['content'] for doc in selected_docs if doc.get('content', '').strip()
        ])
    
    def get_retrieval_config(self, user_query: str, env: str = 'dev', vector_db: str = None) -> Dict[str, Any]:
        """
        Get retrieval configuration based on query complexity.
        
        Args:
            user_query: The user's query
            env: Environment (dev, prod, etc.)
            vector_db: Vector database ID
            
        Returns:
            Retrieval configuration dictionary
        """
        if not vector_db:
            vector_db = "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"
            
        query_complexity = self.assess_query_complexity(user_query)
        results_count = min(10 if query_complexity == 'complex' else 5, 10)  # Max 10 for complex
        
        retrieval_config = {
            "vectorSearchConfiguration": {
                "numberOfResults": results_count,
                "overrideSearchType": "SEMANTIC",
                "filter": {
                    "andAll": [
                        {"equals": {"key": "knowledgeBaseId", "value": vector_db}},
                        {
                            "startsWith": {
                                "key": "x-amz-bedrock-kb-source-uri",
                                "value": f"s3://docops-kb-{env}/{vector_db}/",
                            }
                        },
                    ]
                }
            }
        }
        
        logger.info(f"Query complexity: {query_complexity}, retrieving {results_count} documents")
        return retrieval_config
    
    def process_retrieval_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process Bedrock retrieval results into standardized document format.
        
        Args:
            response: Raw response from Bedrock agent client
            
        Returns:
            List of processed document dictionaries
        """
        context_documents = []
        
        for i, result in enumerate(response.get('retrievalResults', []), 1):
            metadata = result.get('metadata', {})
            content_text = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            
            document_info = {
                'content': content_text,
                'score': score,
                'metadata': metadata
            }
            context_documents.append(document_info)
            
            # Enhanced logging for debugging
            title = metadata.get('title', 'N/A')
            logger.info(f"Document {i}: Title='{title}', Score={score:.3f}, Content_length={len(content_text)}")

        logger.info(f"Retrieved {len(context_documents)} documents from Knowledge Base")
        return context_documents


# Multi-Query RAG Enhancement
class MultiQueryDocumentAnalyzer(DocumentAnalyzer):
    """
    Enhanced DocumentAnalyzer with multi-query RAG capabilities.
    Extends base functionality with query variation support.
    """
    
    def combine_multi_query_results(self, query_results: List[Dict[str, Any]], original_query: str) -> List[Dict]:
        """
        Combine and deduplicate results from multiple query variations.
        
        Args:
            query_results: List of result dictionaries from different query variations
            original_query: The original user query for context
            
        Returns:
            Combined and optimized document list
        """
        all_documents = []
        seen_content_hashes = set()
        
        # Combine all documents from different query variations
        for result in query_results:
            documents = result.get('documents', [])
            query_variant = result.get('query_variant', original_query)
            
            for doc in documents:
                # Create content hash to identify duplicates
                content = doc.get('content', '')
                content_hash = hash(content[:200])  # Use first 200 chars as fingerprint
                
                if content_hash not in seen_content_hashes:
                    seen_content_hashes.add(content_hash)
                    
                    # Add metadata about which query found this document
                    doc['source_query'] = query_variant
                    doc['multi_query_source'] = True
                    
                    all_documents.append(doc)
        
        # Re-score documents based on relevance to original query
        scored_documents = self._rescore_for_original_query(all_documents, original_query)
        
        # Apply final document selection logic
        final_documents = self.select_optimal_documents(scored_documents, original_query)
        
        logger.info(f"Multi-Query RAG: Combined {len(all_documents)} unique documents, selected {len(final_documents)} final")
        
        return final_documents
    
    def _rescore_for_original_query(self, documents: List[Dict], original_query: str) -> List[Dict]:
        """
        Re-score documents based on relevance to the original query.
        This helps ensure the best documents rise to the top after multi-query combination.
        """
        query_terms = set(original_query.lower().split())
        
        for doc in documents:
            content = doc.get('content', '').lower()
            original_score = doc.get('score', 0)
            
            # Calculate term overlap bonus
            content_terms = set(content.split())
            overlap_ratio = len(query_terms.intersection(content_terms)) / len(query_terms) if query_terms else 0
            
            # Adjust score based on term overlap (small boost for direct relevance)
            adjusted_score = original_score + (overlap_ratio * 0.1)  # Max 10% boost
            doc['adjusted_score'] = min(adjusted_score, 1.0)  # Cap at 1.0
            doc['original_score'] = original_score
            doc['term_overlap_ratio'] = overlap_ratio
        
        # Sort by adjusted score
        documents.sort(key=lambda x: x.get('adjusted_score', 0), reverse=True)
        
        return documents


# Global instances for easy import and use
document_analyzer = DocumentAnalyzer()
multi_query_analyzer = MultiQueryDocumentAnalyzer()


def build_context_aware_prompt(system_instructions: str, 
                              context_documents: List[Dict], 
                              user_query: str,
                              max_tokens: int = 4000) -> str:
    """
    Build a context-aware prompt with proper document selection and formatting.
    
    This consolidates the prompt building logic that appears multiple times.
    
    Args:
        system_instructions: The base system instructions
        context_documents: List of available documents
        user_query: The user's question
        max_tokens: Maximum token limit for the model
        
    Returns:
        Complete prompt string ready for the AI model
    """
    analyzer = DocumentAnalyzer(max_tokens)
    
    if context_documents:
        # Enhanced context selection for complex queries
        selected_docs = analyzer.select_optimal_documents(context_documents, user_query)
        context = analyzer.build_context_string(selected_docs)
        
        # Log the context for debugging
        logger.info(f"Context documents found: {len(context_documents)}")
        logger.info(f"Selected documents: {len(selected_docs)}")
        logger.info(f"Context content length: {len(context)} characters")
        

        
        # Check if we have meaningful content
        if context.strip() and len(context.strip()) > 10:
            # 🎯 SMART RELEVANCE CHECK: Assess if context is actually relevant
            relevance_score = analyzer.assess_context_relevance(user_query, selected_docs)
            
            # Build sources text
            sources_text = analyzer.build_sources_text(selected_docs)
            
            if relevance_score >= 0.3:  # Context seems relevant
                prompt = f"""{system_instructions}

Context:
{context}

User Question: {user_query}

Please provide a comprehensive answer based on the context above following the system guidelines. Always include the source references at the end of your response.

{sources_text}"""
                
                logger.info(f"✅ [RELEVANCE] High relevance ({relevance_score:.3f}) - using direct answer approach")
            else:
                # Lower relevance, but still let AI decide with more flexible approach
                prompt = f"""{system_instructions}

Context:
{context}

User Question: {user_query}

Please answer based on the available context if it's relevant to the question. If you provide an answer using the context, always include the source references at the end.

{sources_text}"""
                
                logger.info(f"⚠️ [RELEVANCE] Lower relevance ({relevance_score:.3f}) - using flexible approach")

            # Log key information for debugging
            logger.info(f"🤖 [PROMPT] Context: {len(context)} chars, Docs: {len(selected_docs)}")
        else:
            # No meaningful content found in documents
            logger.warning("Documents retrieved but no meaningful content found")
            prompt = f"""{system_instructions}

User Question: {user_query}

Since the retrieved documents do not contain sufficient information to answer your query, please respond with: "I'm sorry, I don't have information about this in my knowledge base." """
    else:
        prompt = f"""{system_instructions}

User Question: {user_query}

Since no specific context is available from the vector database, please respond with: "I'm sorry, I don't have information about this in my knowledge base." """
    
    return prompt