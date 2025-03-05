# Lead Generation Dashboard

A Streamlit-based dashboard for scraping, reviewing, and approving company news leads before sending them to Slack.

## Features

-   **Company Selection**: Choose from a predefined list of companies or scrape all companies at once
-   **Time Range Selection**: Specify how far back to scrape news (1 day to 1 month)
-   **Lead Review**: Review and approve leads before sending them to Slack
-   **Lead Management**: View recent leads stored in the database
-   **Real-time Notifications**: Send approved leads directly to Slack
-   **Fallback Mode**: Can run without database connectivity in a limited mode

## Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd lead_gen_poc
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables in a `.env` file:

```
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Supabase (already set up through UI)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=your_pinecone_index_name

# Slack
SLACK_WEBHOOK_URL=your_slack_webhook_url
ENABLE_SLACK_NOTIFICATIONS=true

# Other settings
VECTOR_DIMENSION=1536
SIMILARITY_THRESHOLD=0.85
SCRAPING_INTERVAL=3600
MAX_RETRIES=3
RETRY_DELAY=5
```

## Running the Dashboard

Run the Streamlit app:

```bash
streamlit run app.py
```

Or use the provided script:

```bash
./run_app.sh
```

The dashboard will be available at `http://localhost:8501`.

## Using the Dashboard

### Basic Workflow

1. **Select a Company**: Choose a specific company from the dropdown or select "All Companies"
2. **Set Time Range**: Choose how far back to scrape (1 day to 1 month)
3. **Start Scraping**: Click the "Start Scraping" button to begin
4. **Review Leads**: Each lead will be displayed with details including:
    - Title and source
    - Relevance score
    - Description
    - Value types (categories of business value)
    - Suggested actions for CSMs
5. **Approve or Reject**: For each lead, choose to either:
    - Approve and send to Slack
    - Reject (will not be sent to Slack)
6. **View Recent Leads**: Click "View Recent Leads" to see recently stored leads

### Running Modes

The dashboard can run in two modes:

1. **Full Mode**: With database connectivity to Supabase and Pinecone

    - All features available including storage and retrieval
    - Send notifications to Slack
    - View recent leads

2. **Limited Mode**: Without database connectivity
    - Can still scrape and review leads
    - Cannot store leads or send to Slack
    - Useful for testing or when database is unavailable

### Troubleshooting

If you encounter the error `TypeError: Client.__init__() got an unexpected keyword argument 'proxy'`:

-   This is due to a version incompatibility in the Supabase client
-   Make sure you're using the correct version specified in requirements.txt
-   Run `pip install supabase==1.0.3` to install a compatible version

## Adding New Companies

To add new companies to the scraper, modify the `COMPANY_CATEGORIES` dictionary in `scrapers/company_scraper.py`:

```python
COMPANY_CATEGORIES = {
    "enterprise_tech": [
        "Coca Cola", "Delta Airlines", "The Home Depot", "IHG", "Black Knight",
        # Add new enterprise tech companies here
    ],
    "tech_giants": [
        "Uber", "Zillow", "Google", "Dropbox", "Roblox", "US Bank",
        # Add new tech giants here
    ],
    "d2c_ecommerce": [
        "TRUFF", "310 Nutrition", "MUTHA", "HiBAR", "Viome", "BIOHM",
        # Add new D2C/ecommerce companies here
    ]
    # You can also add new categories here
}
```

## Additional Info

-   **Simplified Mode**: For testing without database dependencies, run `streamlit run simple_app.py`
-   **Rate Limiting**: The scraper includes delays to avoid rate limiting by sources
-   **OpenAI Integration**: Uses GPT models for content analysis and valuation
-   **Error Handling**: The app includes robust error handling to prevent crashes

## License

[MIT License](LICENSE)
