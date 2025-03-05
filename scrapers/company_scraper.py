import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time
import random
import uuid
import asyncio
import json
from urllib.parse import quote_plus, urljoin
import feedparser
import html
import re

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field

from config import MAX_RETRIES, RETRY_DELAY, OPENAI_API_KEY
from utils.logger import setup_logger
from database.mongo_client import MongoDBManager
from embeddings.vector_store import VectorStore
from notifications.notifier import LeadNotifier
from openai import OpenAI

# Set up logger
logger = setup_logger("scraper")

# LLM instruction for content extraction
INSTRUCTION_TO_LLM = """
Extract the following information from the news article:
1. The main content/text of the article
2. The article title
3. The publication date if available
4. Any company names mentioned
5. The main topics or themes

Format the response as a JSON object with these fields:
- content: the main text content
- title: the article title
- date: the publication date (if found)
- companies: array of company names mentioned
- topics: array of main topics/themes
"""

# Add this to the existing LLM instruction
DESCRIPTION_PROMPT = """
Given the following article content, create a detailed, well-structured summary that:
1. Captures the main points and key information
2. Removes any HTML formatting or artifacts
3. Maintains professional language and tone
4. Highlights relevant business implications
5. Is between 200-400 words

Article content:
{content}

Please provide a clean, professional summary that could be used in a business context.
"""

class NewsArticle(BaseModel):
    """Pydantic model for news article data."""
    url: str
    title: Optional[str]
    content: str
    date: Optional[str]
    companies: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

class CompanyScraper:
    """Scraper for company-specific news and updates."""
    
    # Company relationships for better context and evaluation
    COMPANY_RELATIONSHIPS = {
        "couchbase": {
            "name": "Couchbase",
            "companies": [
                "Coca Cola", "Delta Airlines", "The Home Depot", "IHG", "Black Knight",
                "Veem", "PWC", "Accesso", "Rollins", "NCR Voyix", "NCR Ateleos",
                "PGA Tour", "Hard Rock", "Equifax", "Chick-fil-A"
            ],
            "description": "Enterprise database and analytics solutions provider"
        },
        "subkit": {
            "name": "Subkit",
            "companies": [
                "TRUFF", "310 Nutrition", "MUTHA", "HiBAR", "Viome", "BIOHM",
                "Fulton Fish Market", "EBOOST", "Obvi", "Kuli Kuli", "Tiege Hanley",
                "MUD/WTR", "GoPure", "Wilde Chips"
            ],
            "description": "E-commerce and subscription management platform"
        },
        "legion": {
            "name": "Legion Technologies",
            "companies": ["Apple", "Microsoft", "Meta"],
            "description": "Intelligent Automation Powered by Legion Workforce Management"
        }
    }

    def __init__(self, target_company="couchbase", initialize_db=True, existing_mongo_client=None):
        """Initialize the company scraper with database connections.
        
        Args:
            target_company: The company we're evaluating news for (e.g., 'couchbase')
            initialize_db: Whether to initialize database connections
            existing_mongo_client: An existing MongoDB client to use instead of creating a new one
        """
        self.target_company = target_company.lower()
        if self.target_company not in self.COMPANY_RELATIONSHIPS:
            raise ValueError(f"Invalid target company: {target_company}")
            
        self.target_company_info = self.COMPANY_RELATIONSHIPS[self.target_company]
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        })
        
        # Initialize database connections if requested
        self.has_db = False
        if initialize_db:
            try:
                # Import here to avoid circular imports
                from database.mongo_client import MongoDBManager
                from embeddings.vector_store import VectorStore
                from notifications.notifier import LeadNotifier
                
                # Use existing client if provided, otherwise create a new one
                self.db = MongoDBManager(existing_client=existing_mongo_client)
                self.vector_store = VectorStore()
                self.has_db = True
                logger.info("Database connections initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization failed: {str(e)}")
                self.has_db = False

        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"OpenAI client initialization failed: {str(e)}")
            raise

        # Define the evaluation tools
        self.evaluation_tools = [
            {
                "type": "function",
                "function": {
                    "name": "evaluate_company_relevance",
                    "description": "Evaluate if the article is truly relevant to the target company",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "is_relevant": {
                                "type": "boolean",
                                "description": "Whether the article is genuinely about or significantly involves the target company"
                            },
                            "relevance_score": {
                                "type": "integer",
                                "description": "Relevance score from 0-100",
                                "minimum": 0,
                                "maximum": 100
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Brief explanation of why the article is or isn't relevant"
                            }
                        },
                        "required": ["is_relevant", "relevance_score", "explanation"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "evaluate_csm_value",
                    "description": "Evaluate if the article provides value for Customer Success Managers based on specific criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "is_valuable": {
                                "type": "boolean",
                                "description": "Whether the article provides value for CSMs"
                            },
                            "value_type": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "funding_round",
                                        "financial_health",
                                        "merger_acquisition",
                                        "strategic_partnership",
                                        "hiring_trends",
                                        "leadership_change",
                                        "market_expansion",
                                        "product_launch",
                                        "industry_trend",
                                        "competitive_insight",
                                        "public_sentiment",
                                        "digital_presence",
                                        "award_recognition",
                                        "challenge_opportunity",
                                        "none"
                                    ]
                                },
                                "description": "Types of value this article provides for CSMs"
                            },
                            "action_items": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Specific actions CSMs can take based on this information"
                            },
                            "financial_indicators": {
                                "type": "object",
                                "properties": {
                                    "funding_amount": {
                                        "type": "string",
                                        "description": "Amount of funding if mentioned"
                                    },
                                    "financial_health": {
                                        "type": "string",
                                        "description": "Indicators of financial health"
                                    }
                                }
                            },
                            "organizational_changes": {
                                "type": "object",
                                "properties": {
                                    "hiring_info": {
                                        "type": "string",
                                        "description": "Information about hiring or staffing changes"
                                    },
                                    "leadership_changes": {
                                        "type": "string",
                                        "description": "Information about executive or leadership changes"
                                    }
                                }
                            },
                            "market_insights": {
                                "type": "object",
                                "properties": {
                                    "industry_trends": {
                                        "type": "string",
                                        "description": "Relevant industry or market trends"
                                    },
                                    "competitive_landscape": {
                                        "type": "string",
                                        "description": "Information about competitive positioning"
                                    }
                                }
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Detailed explanation of the article's value for CSMs"
                            }
                        },
                        "required": ["is_valuable", "value_type", "action_items", "explanation"]
                    }
                }
            }
        ]

    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and return plain text."""
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            # Get text content
            text = soup.get_text(separator=' ')
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Remove URLs
            text = re.sub(r'http[s]?://\S+', '', text)
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            logger.error(f"Error cleaning HTML content: {str(e)}")
            return html_content

    def _generate_clean_description(self, content: str) -> str:
        """Generate a clean, well-structured description using GPT-4."""
        try:
            # Clean HTML first
            cleaned_content = self._clean_html_content(content)
            
            # Prepare prompt for GPT-4
            prompt = DESCRIPTION_PROMPT.format(content=cleaned_content)
            
            # Generate improved description using GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": "You are a professional business analyst tasked with creating clear, concise article summaries."},
                    {"role": "user", "content": prompt}
                ],
            )
            
            return response.choices[0].message.content.strip()
                        
        except Exception as e:
            logger.error(f"Error generating clean description: {str(e)}")
            return content

    def _evaluate_article_relevance(self, company: str, title: str, content: str) -> Dict[str, Any]:
        """Evaluate if the article is relevant to the target company's interests."""
        try:
            prompt = f"""
            Evaluate if this article about {company} is relevant to {self.target_company_info['name']}.
            
            Target Company Context:
            {self.target_company_info['name']} - {self.target_company_info['description']}
            
            Article:
            Title: {title}
            Content: {content}
            
            Consider ANY of these factors for relevance:
            1. Direct Business Impact:
               - Changes in company operations, strategy, or performance
               - New products, services, or initiatives
            
            2. Industry Trends:
               - Market changes that could affect the company
               - Technology adoption or digital transformation
            
            3. Relationship Opportunities:
               - Any news that could create conversation points
               - Updates that might affect their technology needs
            
            4. General Business Intelligence:
               - Leadership changes
               - Market expansion
               - New partnerships or collaborations
            
            Be inclusive in your evaluation - even indirect relationships or potential future implications should be considered relevant.
            Consider both immediate and long-term potential value.
            
            Provide your evaluation by calling the evaluate_company_relevance function.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": f"You are an expert at identifying business opportunities and relevant news for {self.target_company_info['name']}. Be inclusive and consider both direct and indirect relevance."},
                    {"role": "user", "content": prompt}
                ],
                tools=self.evaluation_tools[:1],
                tool_choice={"type": "function", "function": {"name": "evaluate_company_relevance"}}
            )
            
            # Extract the function call
            function_call = response.choices[0].message.tool_calls[0].function
            evaluation = json.loads(function_call.arguments)
            
            return evaluation
                
        except Exception as e:
            logger.error(f"Error evaluating article relevance: {str(e)}")
            return {"is_relevant": False, "relevance_score": 0, "explanation": "Error in evaluation"}

    def _evaluate_csm_value(self, company: str, title: str, content: str) -> Dict[str, Any]:
        """Evaluate if the article provides value for CSMs in the context of the target company."""
        try:
            prompt = f"""
            Evaluate if this article about {company} provides any potential value for Customer Success Managers at {self.target_company_info['name']}.
            
            Target Company Context:
            {self.target_company_info['name']} - {self.target_company_info['description']}
            
            Article:
            Title: {title}
            Content: {content}
            
            Consider ANY of these areas for potential value:
            1. Technology & Infrastructure:
               - Any technology-related changes or updates
               - Digital transformation initiatives
               - IT infrastructure changes
            
            2. Business Updates:
               - Company growth or changes
               - New locations or markets
               - Customer experience initiatives
               - Operational changes
            
            3. Relationship Building:
               - Conversation starters
               - Industry insights
               - Common challenges or opportunities
               - Success stories or achievements
            
            4. Future Opportunities:
               - Long-term strategic plans
               - Industry trends
               - Market positioning
               - Innovation initiatives
            
            Be inclusive in identifying value - consider both:
            1. Direct opportunities for immediate action
            2. Indirect value for relationship building
            3. Future potential for engagement
            4. General business intelligence
            
            Provide your evaluation by calling the evaluate_csm_value function.
            Consider ANY potential value as worth noting, even if indirect or future-focused.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": f"You are an expert at identifying valuable information for Customer Success Managers at {self.target_company_info['name']}. Be inclusive and consider both direct and indirect value opportunities."},
                    {"role": "user", "content": prompt}
                ],
                tools=self.evaluation_tools[1:],
                tool_choice={"type": "function", "function": {"name": "evaluate_csm_value"}}
            )
            
            # Extract the function call
            function_call = response.choices[0].message.tool_calls[0].function
            evaluation = json.loads(function_call.arguments)
            
            return evaluation
                
        except Exception as e:
            logger.error(f"Error evaluating CSM value: {str(e)}")
            return {"is_valuable": False, "value_type": ["none"], "action_items": [], "explanation": "Error in evaluation"}

    def _fetch_news(self, company: str, time_range: str = "7d") -> List[Dict[str, Any]]:
        """Fetch news for a company using Google News RSS feed.
        
        Args:
            company: The company name to search for
            time_range: Time range for the search (e.g., "1d", "7d", "30d")
        """
        leads = []
        
        try:
            # Create Google News RSS URL with time range
            url = f"https://news.google.com/rss/search?q={quote_plus(company)}+when:{time_range}"
            
            # Parse the RSS feed
            feed = feedparser.parse(url)
            
            # Process entries
            for entry in feed.entries[:10]:
                try:
                    # Clean and process the entry
                    title = html.unescape(entry.title)
                    raw_description = html.unescape(entry.description) if hasattr(entry, 'description') else ""
                    
                    # Generate clean description using GPT-4
                    clean_description = self._generate_clean_description(raw_description)
                    
                    # Evaluate article relevance with lower threshold (50 instead of 70)
                    relevance = self._evaluate_article_relevance(company, title, clean_description)
                    if not relevance["is_relevant"] or relevance["relevance_score"] < 50:
                        logger.info(f"Skipping low relevance article for {company}: {title} (Score: {relevance['relevance_score']})")
                        continue
                    
                    # Evaluate CSM value - more lenient now, accepting any value type
                    csm_value = self._evaluate_csm_value(company, title, clean_description)
                    
                    # Only skip if explicitly marked as not valuable
                    if not csm_value["is_valuable"]:
                        logger.info(f"Skipping non-valuable article for CSMs: {title}")
                        continue
                    
                    lead = {
                        "id": str(uuid.uuid4()),
                        "title": title,
                        "url": entry.link,
                        "description": clean_description,
                        "raw_description": raw_description,
                        "source": "Google News",
                        "company": company,
                        "category": self._get_company_category(company),
                        "timestamp": datetime.now().isoformat(),
                        "relevance_score": relevance["relevance_score"],
                        "relevance_explanation": relevance["explanation"],
                        "value_types": json.dumps(csm_value["value_type"]),
                        "action_items": json.dumps(csm_value["action_items"]),
                        "csm_value_explanation": csm_value["explanation"]
                    }
                    
                    leads.append(lead)
                    
                except Exception as e:
                    logger.error(f"Error processing news entry for {company}: {str(e)}")
                    continue

            time.sleep(RETRY_DELAY)
            
        except Exception as e:
            logger.error(f"Error fetching news for {company}: {str(e)}")
        
        return leads

    def process_and_store_lead(self, lead: Dict[str, Any]) -> bool:
        """Process and store a single lead in both Pinecone and MongoDB."""
        try:
            # Check if URL already exists in MongoDB
            existing_lead = self.db.get_lead_by_url(lead["url"])
            if existing_lead:
                logger.info(f"Duplicate lead detected for {lead['company']}: {lead['title']}")
                return False

            # Generate embedding
            lead_text = f"{lead['company']} {lead['title']} {lead.get('description', '')}"
            embedding = self.vector_store.generate_embedding(lead_text)

            # Check for similar content in Pinecone
            duplicate = self.vector_store.check_duplicate(lead_text)
            if duplicate:
                logger.info(f"Similar lead detected for {lead['company']}: {lead['title']}")
                return False

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
                    "company": lead["company"]
                }
            )

            if not vector_success:
                logger.error(f"Failed to store vector for lead: {lead['title']}")
                # Cleanup MongoDB if vector store fails
                self.db.leads.delete_one({"id": lead["id"]})
                return False

            # Send notification only after successful storage in both databases
            notifier = LeadNotifier()
            notification_success = notifier.notify(stored_lead)
            if not notification_success:
                logger.error(f"Failed to send notification for lead: {lead['title']}")
                # Note: We don't rollback storage on notification failure
                # as the lead is still valid and stored properly

            logger.info(f"Successfully processed and stored lead: {lead['title']}")
            return True

        except Exception as e:
            logger.error(f"Error processing lead: {str(e)}")
            return False

    def scrape(self, company=None, time_range="7d") -> List[Dict[str, Any]]:
        """Scrape news and return leads for each company.
        
        Args:
            company: Optional specific company to scrape (if None, scrape all companies)
            time_range: Time range for the search (e.g., "1d", "7d", "30d")
        """
        leads = []
        
        # Get list of companies
        if company is not None and company != "All Companies":
            companies = [company]
        else:
            companies = [
                company for companies in self.COMPANY_RELATIONSHIPS.values() 
                for company in companies
            ]
        
        # Process each company sequentially
        for company in companies:
            logger.info(f"Processing company: {company}")
            
            try:
                # Fetch leads for the company without storing them
                company_leads = self._fetch_news(company, time_range)
                leads.extend(company_leads)
                logger.info(f"Successfully processed {len(company_leads)} leads for {company}")
                
                # Add delay between companies
                time.sleep(RETRY_DELAY)
                
            except Exception as e:
                logger.error(f"Error processing {company}: {str(e)}")
                continue
        
        logger.info(f"Successfully processed {len(leads)} total leads")
        return leads

    def _get_company_category(self, company: str) -> str:
        """Get the category for a specific company."""
        for category, companies in self.COMPANY_RELATIONSHIPS.items():
            if company in companies["companies"]:
                return category
        return "unknown"

if __name__ == "__main__":
    # Test the scraper
    scraper = CompanyScraper()
    results = scraper.scrape()
    print(f"Found and stored {len(results)} leads:")
    
    # Group and display results by company category
    by_category = {}
    for result in results:
        category = result["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(result)
        
        for category, leads in by_category.items():
            print(f"\n=== {category.upper()} ({len(leads)} leads) ===")
            for lead in leads[:3]:  # Show first 3 leads per category
                print(f"\nCompany: {lead['company']}")
                print(f"Title: {lead['title']}")
                print(f"Source: {lead['source']}")
                print("---")