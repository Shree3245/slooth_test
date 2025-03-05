from pymongo import MongoClient
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from utils.logger import setup_logger

logger = setup_logger("database")

# MongoDB connection string
MONGO_HOST = "mongodb+srv://shree3245:a8hEUgpQ7yZaywZr@cluster0.ftwbuv0.mongodb.net/?retryWrites=true&w=majority"

class MongoDBManager:
    """Manages all MongoDB database operations."""
    
    def __init__(self, existing_client=None):
        """Initialize MongoDB client.
        
        Args:
            existing_client: An existing MongoDB client to use instead of creating a new one
        """
        try:
            if existing_client:
                # Use existing client if provided
                self.client = existing_client
                logger.info("Using existing MongoDB client")
            else:
                # Initialize MongoDB client with connection string
                self.client = MongoClient(MONGO_HOST)
                self.db = self.client.lead_gen  # Use the lead_gen database
                logger.info("MongoDB client initialized successfully")
                
                # Create indexes if not exist
                if "url_index" not in self.db.leads.index_information():
                    self.db.leads.create_index("url", unique=True)
                if "created_at_index" not in self.db.leads.index_information():
                    self.db.leads.create_index("created_at", direction=-1)
                    
        except Exception as e:
            logger.error(f"Error initializing MongoDB client: {str(e)}")
            raise

    def insert_lead(self, lead_data: Dict[str, Any], vector_embedding: List[float]) -> Optional[Dict[str, Any]]:
        """Insert a new lead with its vector embedding into the database."""
        try:
            # Convert vector embedding to list if it's numpy array
            if hasattr(vector_embedding, 'tolist'):
                vector_embedding = vector_embedding.tolist()
                
            data = {
                "id": lead_data["id"],
                "title": lead_data["title"],
                "url": lead_data["url"],
                "description": lead_data.get("description", ""),
                "source": lead_data.get("source", "unknown"),
                "company": lead_data["company"],
                "category": lead_data.get("category", "unknown"),
                "timestamp": lead_data.get("timestamp", datetime.utcnow().isoformat()),
                "vector_embedding": vector_embedding,
                "created_at": datetime.utcnow()
            }
            
            # Add other fields if present
            for key in ["relevance_score", "relevance_explanation", "value_types", "action_items", "csm_value_explanation"]:
                if key in lead_data:
                    data[key] = lead_data[key]
            
            result = self.db.leads.insert_one(data)
            
            if result.inserted_id:
                logger.info(f"Successfully inserted lead: {lead_data['title']}")
                return self.db.leads.find_one({"_id": result.inserted_id})
            return None
            
        except Exception as e:
            logger.error(f"Error inserting lead into MongoDB: {str(e)}")
            return None

    def get_lead_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve a lead by its URL to check for duplicates."""
        try:
            result = self.db.leads.find_one({"url": url})
            return result
        except Exception as e:
            logger.error(f"Error retrieving lead from MongoDB: {str(e)}")
            return None

    def get_recent_leads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the most recent leads."""
        try:
            cursor = self.db.leads.find().sort("created_at", -1).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error retrieving recent leads: {str(e)}")
            return []

    def search_leads_by_embedding(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar leads using vector similarity.
        
        Note: MongoDB doesn't have built-in vector similarity search like Pinecone.
        This is a simplified version that would need to be enhanced with a proper
        vector search solution for production use.
        """
        try:
            # For a proper implementation, consider using MongoDB Atlas Vector Search
            # or integrating with a dedicated vector database
            logger.warning("Vector similarity search not fully implemented in MongoDB")
            return self.get_recent_leads(limit)
        except Exception as e:
            logger.error(f"Error searching leads by embedding: {str(e)}")
            return []

if __name__ == "__main__":
    # Test the MongoDB manager
    try:
        manager = MongoDBManager()
        recent_leads = manager.get_recent_leads(5)
        print("Recent leads:")
        for lead in recent_leads:
            print(f"Title: {lead['title']}")
            print(f"URL: {lead['url']}")
            print("---")
    except Exception as e:
        print(f"Error testing MongoDB manager: {str(e)}") 