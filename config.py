import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys and Credentials
MONGO_HOST = os.getenv("MONGO_HOST")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Pinecone Configuration
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
VECTOR_DIMENSION = 1536  # OpenAI ada-002 embedding dimension

# Scraping Configuration
SCRAPING_INTERVAL = 3600  # 1 hour in seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
BATCH_SIZE = 5  # Number of companies to process in each batch
MAX_CONCURRENT_REQUESTS = 3  # Maximum number of concurrent requests

# Lead Detection Settings
SIMILARITY_THRESHOLD = 0.85  # Threshold for duplicate detection
MAX_LEADS_PER_QUERY = 5

# Notification Settings
ENABLE_SLACK_NOTIFICATIONS = True
ENABLE_EMAIL_NOTIFICATIONS = False  # For future implementation 