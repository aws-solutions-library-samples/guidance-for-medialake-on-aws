"""
Base embedding store interface for semantic search implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Standardized search result format"""
    hits: List[Dict[str, Any]]
    total_results: int
    aggregations: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None


class BaseEmbeddingStore(ABC):
    """Abstract base class for embedding store implementations"""
    
    def __init__(self, logger, metrics):
        self.logger = logger
        self.metrics = metrics
    
    @abstractmethod
    def build_semantic_query(self, params) -> Dict[str, Any]:
        """
        Build a semantic search query for the specific embedding store.
        
        Args:
            params: Search parameters
            
        Returns:
            Query object specific to the embedding store
        """
        pass
    
    @abstractmethod
    def execute_search(self, query: Dict[str, Any], params) -> SearchResult:
        """
        Execute the search query against the embedding store.
        
        Args:
            query: Query object from build_semantic_query
            params: Original search parameters
            
        Returns:
            SearchResult with standardized format
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the embedding store is available and properly configured.
        
        Returns:
            True if the store is available, False otherwise
        """
        pass
    
    def search(self, params) -> SearchResult:
        """
        Main search method that orchestrates the search process.
        
        Args:
            params: Search parameters
            
        Returns:
            SearchResult with standardized format
        """
        if not self.is_available():
            raise Exception(f"{self.__class__.__name__} is not available or configured")
        
        query = self.build_semantic_query(params)
        return self.execute_search(query, params)