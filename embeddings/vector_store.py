import pinecone
from openai import OpenAI
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from pinecone import Pinecone

from config import (
    PINECONE_API_KEY,
    PINECONE_ENVIRONMENT,
    PINECONE_INDEX_NAME,
    OPENAI_API_KEY,
    VECTOR_DIMENSION,
    SIMILARITY_THRESHOLD
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStore:
    """Manages vector embeddings and similarity search using Pinecone."""
    
    def __init__(self):
        """Initialize Pinecone and OpenAI clients."""
        try:
            # Initialize Pinecone with new API
            self.pc = Pinecone(api_key=PINECONE_API_KEY)
            
            # Create index if it doesn't exist
            existing_indexes = [index.name for index in self.pc.list_indexes()]
            if PINECONE_INDEX_NAME not in existing_indexes:
                self.pc.create_index(
                    name=PINECONE_INDEX_NAME,
                    dimension=VECTOR_DIMENSION,
                    metric="cosine",
                    spec={
                        "serverless": {
                            "cloud": "aws",
                            "region": "us-east-1"
                        }
                    }
                )
            
            self.index = self.pc.Index(PINECONE_INDEX_NAME)
            
            # Initialize OpenAI with API key
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key is not set")
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            
            logger.info("Vector store initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing vector store: {str(e)}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a given text using OpenAI's API."""
        try:
            if not text.strip():
                raise ValueError("Empty text provided for embedding generation")
                
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                encoding_format="float"
            )
            
            # Extract the embedding values
            embedding = response.data[0].embedding
            
            # Validate embedding dimension
            if len(embedding) != VECTOR_DIMENSION:
                raise ValueError(f"Generated embedding dimension {len(embedding)} does not match expected dimension {VECTOR_DIMENSION}")
                
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def insert_vector(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """Insert a vector with metadata into Pinecone."""
        try:
            if not id or not vector or not metadata:
                raise ValueError("Missing required parameters for vector insertion")
                
            self.index.upsert(
                vectors=[(id, vector, metadata)]
            )
            logger.info(f"Successfully inserted vector for ID: {id}")
            return True
        except Exception as e:
            logger.error(f"Error inserting vector: {str(e)}")
            return False

    def find_similar(self, vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Find similar vectors in Pinecone."""
        try:
            if not vector:
                raise ValueError("No vector provided for similarity search")
                
            results = self.index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True
            )
            return results["matches"]
        except Exception as e:
            logger.error(f"Error finding similar vectors: {str(e)}")
            return []

    def check_duplicate(self, text: str, threshold: float = SIMILARITY_THRESHOLD) -> Optional[Dict[str, Any]]:
        """Check if a similar lead already exists based on text similarity."""
        try:
            if not text.strip():
                raise ValueError("Empty text provided for duplicate check")
                
            # Generate embedding for the text
            embedding = self.generate_embedding(text)
            
            # Query Pinecone for similar leads
            results = self.find_similar(embedding, top_k=1)
            
            if results and results[0]["score"] > threshold:
                return results[0]
            return None
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {str(e)}")
            return None

    def delete_vector(self, id: str) -> bool:
        """Delete a vector from Pinecone by ID."""
        try:
            if not id:
                raise ValueError("No ID provided for vector deletion")
                
            self.index.delete(ids=[id])
            logger.info(f"Successfully deleted vector with ID: {id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting vector: {str(e)}")
            return False

    def bulk_insert_vectors(self, vectors: List[tuple]) -> bool:
        """Bulk insert vectors into Pinecone."""
        try:
            if not vectors:
                raise ValueError("No vectors provided for bulk insertion")
                
            self.index.upsert(vectors=vectors)
            logger.info(f"Successfully bulk inserted {len(vectors)} vectors")
            return True
        except Exception as e:
            logger.error(f"Error bulk inserting vectors: {str(e)}")
            return False

if __name__ == "__main__":
    # Test the vector store
    try:
        store = VectorStore()
        
        # Test embedding generation
        test_text = "Example startup lead for testing"
        embedding = store.generate_embedding(test_text)
        print(f"Generated embedding of length: {len(embedding)}")
        
        # Test vector insertion
        success = store.insert_vector(
            id="test_1",
            vector=embedding,
            metadata={"title": test_text, "source": "test"}
        )
        print(f"Vector insertion {'successful' if success else 'failed'}")
        
        # Test similarity search
        similar = store.find_similar(embedding)
        print(f"Found {len(similar)} similar vectors")
        
    except Exception as e:
        print(f"Error testing vector store: {str(e)}") 