from supabase import create_client, Client
import logging
from config import SUPABASE_URL, SUPABASE_KEY
from utils.logger import setup_logger

logger = setup_logger("database.setup")

def setup_supabase_tables():
    """Set up the necessary tables in Supabase."""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Create leads table with updated schema
        # client.table("leads").create({
        #     "id": "text primary key",
        #     "title": "text not null",
        #     "url": "text unique not null",
        #     "description": "text",
        #     "source": "text",
        #     "company": "text not null",
        #     "category": "text",
        #     "timestamp": "timestamp with time zone",
        #     "vector_embedding": "vector(1536)",
        #     "created_at": "timestamp with time zone default timezone('utc'::text, now())",
        
        # })

        #     "raw_description": "text",
        #     "relevance_score": "integer",
        #     "relevance_explanation": "text",
        #     "value_types": "text[]",
        #     "action_items": "text[]",
        #     "csm_value_explanation": "text"

        
        logger.info("Successfully set up Supabase tables")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up Supabase tables: {str(e)}")
        return False

if __name__ == "__main__":
    setup_supabase_tables() 