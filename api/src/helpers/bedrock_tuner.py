"""
Bedrock Knowledge Base Tuning Helper

Provides dynamic parameter optimization for AWS Bedrock Knowledge Base queries
to achieve better retrieval accuracy based on query characteristics and performance metrics.

Key Features:
- Query-specific parameter tuning (numberOfResults, search types)
- Dynamic threshold adjustment based on query complexity
- Performance-based optimization
- A/B testing support for parameter combinations
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BedrockKnowledgeBaseTuner:
    """
    Advanced tuning system for Bedrock Knowledge Base retrieval optimization.
    Dynamically adjusts retrieval parameters based on query characteristics.
    """
    
    def __init__(self):
        self.performance_history = {}
        self.optimization_rules = self._build_optimization_rules()
        self.query_patterns = self._build_query_patterns()
    
    def _build_optimization_rules(self) -> Dict[str, Dict]:
        """Build rules for parameter optimization based on query types"""
        return {
            "incident_support": {
                "numberOfResults": 8,  # More results for comprehensive support info
                "searchType": "SEMANTIC",
                "description": "Support and incident queries need comprehensive coverage"
            },
            "procedural_how_to": {
                "numberOfResults": 6,  # Moderate results for step-by-step procedures
                "searchType": "SEMANTIC",
                "description": "How-to queries need focused procedural information"
            },
            "comparison_analysis": {
                "numberOfResults": 10,  # More results for comparison queries
                "searchType": "SEMANTIC", 
                "description": "Comparison queries need diverse perspective coverage"
            },
            "troubleshooting": {
                "numberOfResults": 7,  # Balanced results for troubleshooting
                "searchType": "SEMANTIC",
                "description": "Troubleshooting needs focused but comprehensive information"
            },
            "general_information": {
                "numberOfResults": 5,  # Standard results for general queries
                "searchType": "SEMANTIC",
                "description": "General information queries use standard settings"
            },
            "specific_lookup": {
                "numberOfResults": 3,  # Fewer results for specific lookups
                "searchType": "SEMANTIC",
                "description": "Specific lookups need precise, focused results"
            }
        }
    
    def _build_query_patterns(self) -> Dict[str, List[str]]:
        """Build patterns to classify queries for optimization"""
        return {
            "incident_support": [
                "incident", "support ticket", "create ticket", "open case", 
                "report issue", "help desk", "support request", "escalate"
            ],
            "procedural_how_to": [
                "how to", "steps to", "process for", "procedure", 
                "guide", "tutorial", "instructions", "setup"
            ],
            "comparison_analysis": [
                "compare", "versus", "vs", "difference between", 
                "better than", "advantages", "disadvantages", "pros and cons"
            ],
            "troubleshooting": [
                "troubleshoot", "error", "problem", "issue", "fix", 
                "resolve", "debug", "not working", "failure"
            ],
            "specific_lookup": [
                "what is", "define", "definition of", "meaning of",
                "explain", "describe", "tell me about"
            ]
        }
    
    def classify_query_for_optimization(self, query: str) -> str:
        """
        Classify query to determine optimal retrieval strategy.
        
        Args:
            query: User query string
            
        Returns:
            Query classification for optimization
        """
        query_lower = query.lower()
        
        # Check each pattern category
        for category, patterns in self.query_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                logger.info(f"Query classified as: {category}")
                return category
        
        # Default classification
        return "general_information"
    
    def get_optimized_retrieval_config(self, query: str, env: str = 'dev', 
                                     vector_db: str = None, 
                                     base_config: Dict = None) -> Dict[str, Any]:
        """
        Get dynamically optimized retrieval configuration.
        
        Args:
            query: User query
            env: Environment (dev, prod, etc.)
            vector_db: Vector database ID
            base_config: Base configuration to enhance
            
        Returns:
            Optimized retrieval configuration
        """
        if not vector_db:
            vector_db = "872051E8-E5C8-4AD1-83A8-ADB347D6C2CC"
        
        # Classify query for optimization
        query_type = self.classify_query_for_optimization(query)
        optimization_rule = self.optimization_rules.get(query_type, self.optimization_rules["general_information"])
        
        # Build optimized configuration
        optimized_config = {
            "vectorSearchConfiguration": {
                "numberOfResults": optimization_rule["numberOfResults"],
                "overrideSearchType": optimization_rule["searchType"],
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
        
        # Apply performance-based adjustments if we have history
        optimized_config = self._apply_performance_adjustments(
            optimized_config, query, query_type
        )
        
        logger.info(f"Optimized config for {query_type}: {optimization_rule['numberOfResults']} results")
        
        return optimized_config
    
    def _apply_performance_adjustments(self, config: Dict, query: str, query_type: str) -> Dict:
        """
        Apply performance-based adjustments to the configuration.
        """
        # Get performance history for this query type
        type_history = self.performance_history.get(query_type, {})
        
        # If we have performance data, make micro-adjustments
        if type_history:
            avg_success_rate = type_history.get('avg_success_rate', 0.5)
            avg_response_time = type_history.get('avg_response_time', 2.0)
            
            # Adjust number of results based on success rate
            current_results = config["vectorSearchConfiguration"]["numberOfResults"]
            
            if avg_success_rate < 0.6:  # Low success rate
                # Increase results by 1-2 for better coverage
                adjusted_results = min(current_results + 2, 15)
                config["vectorSearchConfiguration"]["numberOfResults"] = adjusted_results
                logger.info(f"Increased results to {adjusted_results} due to low success rate ({avg_success_rate:.2f})")
            
            elif avg_success_rate > 0.8 and avg_response_time > 3.0:  # High success but slow
                # Decrease results by 1 for faster response
                adjusted_results = max(current_results - 1, 3)
                config["vectorSearchConfiguration"]["numberOfResults"] = adjusted_results
                logger.info(f"Decreased results to {adjusted_results} for faster response")
        
        return config
    
    def record_query_performance(self, query: str, query_type: str, 
                               response_time: float, success: bool, 
                               documents_found: int, user_satisfied: bool = None):
        """
        Record performance metrics for continuous optimization.
        
        Args:
            query: The original query
            query_type: Classification of the query
            response_time: Total response time in seconds
            success: Whether the query returned useful results
            documents_found: Number of documents retrieved
            user_satisfied: Optional user satisfaction indicator
        """
        timestamp = datetime.now()
        
        # Initialize history for this query type if needed
        if query_type not in self.performance_history:
            self.performance_history[query_type] = {
                'queries': [],
                'total_queries': 0,
                'successful_queries': 0,
                'avg_response_time': 0.0,
                'avg_documents': 0.0,
                'avg_success_rate': 0.0
            }
        
        type_history = self.performance_history[query_type]
        
        # Record this query
        query_record = {
            'timestamp': timestamp,
            'query': query[:100],  # Store first 100 chars for analysis
            'response_time': response_time,
            'success': success,
            'documents_found': documents_found,
            'user_satisfied': user_satisfied
        }
        
        type_history['queries'].append(query_record)
        type_history['total_queries'] += 1
        
        if success:
            type_history['successful_queries'] += 1
        
        # Update averages (simple moving average for recent performance)
        recent_queries = type_history['queries'][-20:]  # Last 20 queries
        
        type_history['avg_response_time'] = sum(q['response_time'] for q in recent_queries) / len(recent_queries)
        type_history['avg_documents'] = sum(q['documents_found'] for q in recent_queries) / len(recent_queries)
        type_history['avg_success_rate'] = sum(q['success'] for q in recent_queries) / len(recent_queries)
        
        logger.info(f"Recorded performance for {query_type}: {response_time:.2f}s, success: {success}")
    
    def get_optimization_insights(self) -> Dict[str, Any]:
        """
        Get insights about current optimization performance.
        
        Returns:
            Dictionary with performance insights and recommendations
        """
        insights = {
            'query_types_analyzed': list(self.performance_history.keys()),
            'total_queries_processed': sum(
                h['total_queries'] for h in self.performance_history.values()
            ),
            'performance_by_type': {},
            'recommendations': []
        }
        
        # Analyze each query type
        for query_type, history in self.performance_history.items():
            if history['total_queries'] > 0:
                insights['performance_by_type'][query_type] = {
                    'total_queries': history['total_queries'],
                    'success_rate': history['avg_success_rate'],
                    'avg_response_time': history['avg_response_time'],
                    'avg_documents': history['avg_documents']
                }
                
                # Generate recommendations
                if history['avg_success_rate'] < 0.6:
                    insights['recommendations'].append(
                        f"Consider increasing document retrieval for {query_type} queries (current success rate: {history['avg_success_rate']:.1%})"
                    )
                
                if history['avg_response_time'] > 4.0:
                    insights['recommendations'].append(
                        f"Consider optimizing {query_type} queries for speed (current avg: {history['avg_response_time']:.1f}s)"
                    )
        
        return insights
    
    def export_tuning_config(self) -> Dict[str, Any]:
        """
        Export current tuning configuration for backup or replication.
        
        Returns:
            Complete tuning configuration
        """
        return {
            'optimization_rules': self.optimization_rules,
            'query_patterns': self.query_patterns,
            'performance_history_summary': {
                qtype: {
                    'total_queries': history['total_queries'],
                    'avg_success_rate': history['avg_success_rate'],
                    'avg_response_time': history['avg_response_time']
                }
                for qtype, history in self.performance_history.items()
            },
            'export_timestamp': datetime.now().isoformat()
        }


# Global instance for easy import
bedrock_tuner = BedrockKnowledgeBaseTuner()

def get_tuned_retrieval_config(query: str, env: str = 'dev', vector_db: str = None) -> Dict[str, Any]:
    """
    Convenience function to get tuned retrieval configuration.
    
    Args:
        query: User query
        env: Environment 
        vector_db: Vector database ID
        
    Returns:
        Optimized retrieval configuration
    """
    return bedrock_tuner.get_optimized_retrieval_config(query, env, vector_db)

# Example usage and testing
if __name__ == "__main__":
    test_queries = [
        ("How to open an incident on microsoft?", "incident_support"),
        ("Steps to deploy kubernetes pods", "procedural_how_to"),
        ("Compare docker vs podman", "comparison_analysis"),
        ("Troubleshoot connection timeout error", "troubleshooting"),
        ("What is microservices architecture", "specific_lookup")
    ]
    
    print("🔧 Testing Bedrock Optimization:")
    print("=" * 50)
    
    tuner = BedrockKnowledgeBaseTuner()
    
    for query, expected_type in test_queries:
        config = tuner.get_optimized_retrieval_config(query)
        num_results = config["vectorSearchConfiguration"]["numberOfResults"]
        
        print(f"Query: \"{query}\"")
        print(f"  Optimized Results: {num_results}")
        print(f"  Expected Type: {expected_type}")
        print()