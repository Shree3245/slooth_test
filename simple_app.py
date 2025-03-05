import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import os
import sys

# Add the project root to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.company_scraper import CompanyScraper

# Set page configuration
st.set_page_config(
    page_title="Lead Generation Dashboard (Simple)",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize the scraper
def initialize_scraper():
    """Initialize the scraper without database connections."""
    try:
        # Initialize without database connections
        scraper = CompanyScraper(initialize_db=False, existing_mongo_client=None)
        return scraper
    except Exception as e:
        st.error(f"Error initializing scraper: {str(e)}")
        return None

scraper = initialize_scraper()

if not scraper:
    st.error("Failed to initialize scraper. Please check your configuration.")
    st.stop()

# Create sidebar for controls
st.sidebar.title("Lead Generation Controls")

# Get all companies from the scraper
def get_all_companies():
    """Get all companies from the scraper categories."""
    all_companies = []
    for category, companies in scraper.COMPANY_CATEGORIES.items():
        all_companies.extend(companies)
    return sorted(all_companies)

# Company selection
company_options = ["All Companies"] + get_all_companies()
selected_company = st.sidebar.selectbox(
    "Select Company to Scrape",
    options=company_options
)

# Time range selection
time_range_options = {
    "1 Day": "1d",
    "2 Days": "2d",
    "3 Days": "3d",
    "5 Days": "5d",
    "1 Week": "7d",
    "2 Weeks": "14d",
    "1 Month": "30d"
}
selected_time_range_display = st.sidebar.selectbox(
    "How Far Back to Scrape",
    options=list(time_range_options.keys())
)
selected_time_range = time_range_options[selected_time_range_display]

# Main content area
st.title("Lead Generation Dashboard (Simple Version)")
st.write("This simplified dashboard allows you to scrape and review leads without database integration.")

# Function to scrape leads based on selected options
def scrape_leads(company, time_range):
    """Scrape leads for the selected company and time range."""
    st.info(f"Scraping {'all companies' if company == 'All Companies' else company} for the past {time_range}...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    leads = []
    
    try:
        if company == "All Companies":
            companies = get_all_companies()
            total_companies = len(companies)
            
            for i, comp in enumerate(companies):
                status_text.text(f"Scraping {comp}... ({i+1}/{total_companies})")
                company_leads = scraper._fetch_news(comp, time_range)
                leads.extend(company_leads)
                progress_bar.progress((i + 1) / total_companies)
                time.sleep(0.5)  # Small delay to avoid rate limiting
        else:
            status_text.text(f"Scraping {company}...")
            leads = scraper._fetch_news(company, time_range)
            progress_bar.progress(1.0)
        
        status_text.text("Scraping completed!")
        return leads
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        return []

# Function to display leads
def display_leads(leads):
    """Display leads for review."""
    if not leads:
        st.warning("No leads found. Try adjusting your search criteria.")
        return
    
    st.success(f"Found {len(leads)} leads. Review them below.")
    
    # Group leads by company
    companies = sorted(set(lead["company"] for lead in leads))
    
    for company in companies:
        company_leads = [lead for lead in leads if lead["company"] == company]
        
        st.subheader(f"{company} ({len(company_leads)} leads)")
        
        for i, lead in enumerate(company_leads):
            with st.expander(f"{lead['title']}", expanded=True):
                # Display lead details
                st.markdown(f"**Source:** {lead.get('source', 'Unknown')}")
                st.markdown(f"**URL:** [{lead['url']}]({lead['url']})")
                st.markdown(f"**Relevance Score:** {lead.get('relevance_score', 'N/A')}")
                
                # Display description
                st.markdown("### Description")
                st.write(lead.get("description", "No description available"))
                
                # Display value types as tags
                st.markdown("### Value Types")
                try:
                    value_types = json.loads(lead.get("value_types", "[]"))
                    if value_types:
                        col1, col2, col3 = st.columns(3)
                        for j, vtype in enumerate(value_types):
                            if j % 3 == 0:
                                col1.markdown(f"- {vtype.replace('_', ' ').title()}")
                            elif j % 3 == 1:
                                col2.markdown(f"- {vtype.replace('_', ' ').title()}")
                            else:
                                col3.markdown(f"- {vtype.replace('_', ' ').title()}")
                    else:
                        st.write("No value types identified.")
                except json.JSONDecodeError:
                    st.write("Error parsing value types.")
                
                # Display action items
                st.markdown("### Suggested Actions")
                try:
                    action_items = json.loads(lead.get("action_items", "[]"))
                    if action_items:
                        for action in action_items:
                            st.markdown(f"- {action}")
                    else:
                        st.write("No action items suggested.")
                except json.JSONDecodeError:
                    st.write("Error parsing action items.")
                
                # Mock approval buttons (no actual functionality in simple version)
                col1, col2 = st.columns(2)
                approve = col1.button("Approve (Demo Only)", key=f"approve_{lead['id']}")
                reject = col2.button("Reject (Demo Only)", key=f"reject_{lead['id']}")
                
                if approve:
                    st.success("This is a demo version without actual Slack integration.")
                if reject:
                    st.info("Lead rejected in demo mode.")

# Scrape button
if st.sidebar.button("Start Scraping"):
    with st.spinner("Scraping in progress..."):
        scraped_leads = scrape_leads(selected_company, selected_time_range)
        st.session_state.leads = scraped_leads  # Store leads in session state
        
    # Display leads for review
    display_leads(scraped_leads)
elif 'leads' in st.session_state:
    # Display previously scraped leads
    display_leads(st.session_state.leads)

# Add statistics and info to sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("About")
st.sidebar.info(
    "This is a simplified version of the Lead Generation Dashboard "
    "without database or Slack integration. Use it for testing the scraping functionality."
) 