import asyncio
from datetime import datetime
from typing import Dict, Any, List
import uuid
import json

from scrapers.company_scraper import CompanyScraper
from database.mongo_client import MongoDBManager
from embeddings.vector_store import VectorStore
from notifications.notifier import LeadNotifier
from utils.logger import setup_logger
from config import SCRAPING_INTERVAL

# Set up logger
logger = setup_logger("lead_detection")

class LeadDetectionSystem:
    """Main system that orchestrates lead detection and processing."""
    
    def __init__(self):
        """Initialize all system components."""
        try:
            self.scraper = CompanyScraper()
            self.db = MongoDBManager()
            self.vector_store = VectorStore()
            self.notifier = LeadNotifier()
            logger.info("Lead detection system initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing lead detection system: {str(e)}")
            raise

    def process_lead(self, lead: Dict[str, Any]) -> bool:
        """Process a single lead through the pipeline."""
        try:
            # Add unique ID if not present
            if "id" not in lead:
                lead["id"] = str(uuid.uuid4())
                
            # Check for duplicates using vector similarity
            duplicate = self.vector_store.check_duplicate(lead["title"])
            if duplicate:
                logger.info(f"Duplicate lead detected for {lead['company']}: {lead['title']}")
                return False

            # Evaluate article relevance first
            relevance = self.scraper._evaluate_article_relevance(
                lead["company"],
                lead["title"],
                lead.get("description", "")
            )
            
            # Skip if not relevant enough
            if not relevance["is_relevant"] or relevance["relevance_score"] < 70:
                logger.info(f"Lead not relevant enough for {lead['company']}: {lead['title']} (Score: {relevance['relevance_score']})")
                return False
                
            # Evaluate CSM value
            csm_value = self.scraper._evaluate_csm_value(
                lead["company"],
                lead["title"],
                lead.get("description", "")
            )
            
            # Skip if no valuable insights for CSMs
            if not csm_value["is_valuable"] or csm_value["value_type"] == ["none"]:
                logger.info(f"Lead lacks CSM value for {lead['company']}: {lead['title']}")
                return False

            # Add evaluation results to lead data
            lead.update({
                "relevance_score": relevance["relevance_score"],
                "relevance_explanation": relevance["explanation"],
                "value_types": json.dumps(csm_value["value_type"]),
                "action_items": json.dumps(csm_value["action_items"]),
                "csm_value_explanation": csm_value["explanation"]
            })

            # Generate embedding for the lead
            lead_text = f"{lead['company']} {lead['title']} {lead.get('description', '')}"
            embedding = self.vector_store.generate_embedding(lead_text)

            # Store in MongoDB first
            stored_lead = self.db.store_lead(lead, embedding)
            if not stored_lead:
                logger.error(f"Failed to store lead in MongoDB: {lead['title']}")
                return False

            # Store in vector database
            vector_success = self.vector_store.insert_vector(
                id=lead["id"],
                vector=embedding,
                metadata={
                    "title": lead["title"],
                    "url": lead["url"],
                    "source": lead.get("source", "unknown"),
                    "company": lead["company"],
                    "relevance_score": relevance["relevance_score"],
                    "value_types": csm_value["value_type"]
                }
            )

            if not vector_success:
                logger.error(f"Failed to store vector for lead: {lead['title']}")
                # Cleanup MongoDB if vector store fails
                self.db.leads.delete_one({"id": lead["id"]})
                return False

            # Send notification
            logger.info(f"Attempting to send notification for lead: {lead['title']}")
            notification_success = self.notifier.notify(stored_lead)
            if not notification_success:
                logger.error(f"Failed to send notification for lead: {lead['title']}")
            else:
                logger.info(f"Successfully sent notification for lead: {lead['title']}")

            logger.info(f"Successfully processed lead for {lead['company']}: {lead['title']}")
            return True

        except Exception as e:
            logger.error(f"Error processing lead: {str(e)}")
            return False

    def process_leads(self, leads: List[Dict[str, Any]]) -> int:
        """Process multiple leads."""
        if not leads:
            return 0

        successful = 0
        for lead in leads:
            if self.process_lead(lead):
                successful += 1
        
        logger.info(f"Successfully processed {successful} out of {len(leads)} leads")
        return successful

    def run_scraping_cycle(self):
        """Run a single scraping cycle."""
        try:
            # Scrape new leads
            leads = self.scraper.scrape()
            if not leads:
                logger.warning("No leads found in this scraping cycle")
                return 0

            # Process the leads
            processed_count = self.process_leads(leads)
            return processed_count

        except Exception as e:
            logger.error(f"Error in scraping cycle: {str(e)}")
            return 0

    def start(self):
        """Run the lead detection system once."""
        logger.info("Starting lead detection system")
        try:
            processed_count = self.run_scraping_cycle()
            logger.info(f"Completed scraping cycle. Processed {processed_count} leads.")
            return processed_count
        except Exception as e:
            logger.error(f"Error in main execution: {str(e)}")
            return 0

if __name__ == "__main__":
    try:
        system = LeadDetectionSystem()
        processed_count = system.start()
        print(f"\nScraping completed. Processed {processed_count} leads.")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        raise 