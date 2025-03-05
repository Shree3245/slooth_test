import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
from typing import List, Dict, Any
import logging

from config import MAX_RETRIES, RETRY_DELAY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechCrunchScraper:
    """Scraper for TechCrunch startup news."""
    
    BASE_URL = "https://techcrunch.com/startups/"
    
    @staticmethod
    def _parse_article(article_element) -> Dict[str, Any]:
        """Parse a single article element and extract relevant information."""
        try:
            title = article_element.find("h2", class_="post-block__title").get_text(strip=True)
            link = article_element.find("a", class_="post-block__title__link")["href"]
            timestamp = article_element.find("time")["datetime"]
            
            # Extract additional metadata if available
            description = article_element.find("div", class_="post-block__content")
            description = description.get_text(strip=True) if description else ""
            
            return {
                "title": title,
                "url": link,
                "timestamp": timestamp,
                "description": description,
                "source": "TechCrunch",
                "category": "startup"
            }
        except Exception as e:
            logger.error(f"Error parsing article: {str(e)}")
            return None

    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape TechCrunch for startup news articles."""
        leads = []
        retries = MAX_RETRIES
        
        while retries > 0:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = requests.get(self.BASE_URL, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, "html.parser")
                articles = soup.find_all("div", class_="post-block")
                
                for article in articles:
                    article_data = self._parse_article(article)
                    if article_data:
                        leads.append(article_data)
                
                logger.info(f"Successfully scraped {len(leads)} leads from TechCrunch")
                return leads
                
            except requests.RequestException as e:
                logger.error(f"Error scraping TechCrunch: {str(e)}")
                retries -= 1
                if retries > 0:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error("Max retries reached. Giving up.")
                    return []
            
            except Exception as e:
                logger.error(f"Unexpected error while scraping: {str(e)}")
                return []

if __name__ == "__main__":
    # Test the scraper
    scraper = TechCrunchScraper()
    results = scraper.scrape()
    for result in results:
        print(f"Title: {result['title']}")
        print(f"URL: {result['url']}")
        print(f"Timestamp: {result['timestamp']}")
        print("---") 