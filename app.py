import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import traceback
from typing import List, Dict, Any

from scrapers.company_scraper import CompanyScraper
from notifications.notifier import LeadNotifier

# Set page configuration
st.set_page_config(
    page_title="Lead Generation Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components
@st.cache_resource
def initialize_components():
    """Initialize and cache the system components."""
    try:
        # First initialize scraper without DB to avoid connection errors
        scraper = CompanyScraper(initialize_db=False)
        
        # Then try to initialize database connections
        try:
            from database.mongo_client import MongoDBManager
            from embeddings.vector_store import VectorStore
            
            # Try to create MongoDBManager and VectorStore explicitly
            try:
                db_manager = MongoDBManager()
                st.success("MongoDB connected successfully")
                vector_store = VectorStore()
                
                # If we get here, database initialization succeeded
                scraper.db = db_manager
                scraper.vector_store = vector_store
                scraper.has_db = True
                
                return {
                    "scraper": scraper,
                    "notifier": LeadNotifier(),
                    "vector_store": vector_store,
                    "db": db_manager,
                    "db_available": True
                }
            except Exception as db_error:
                error_msg = str(db_error)
                if "Authentication failed" in error_msg or "bad auth" in error_msg:
                    st.error("⚠️ MongoDB Authentication Failed: Please check your username and password in config.py")
                    st.info("You may need to update your MongoDB Atlas credentials or whitelist your IP address.")
                else:
                    st.error(f"Database connection error: {error_msg}")
                
                st.warning("Running in limited mode without database connection")
                # Return with only scraper initialized
                return {
                    "scraper": scraper,
                    "db_available": False
                }
        except Exception as db_error:
            st.warning(f"Database connection failed, running in limited mode: {str(db_error)}")
            # Return with only scraper initialized
            return {
                "scraper": scraper,
                "db_available": False
            }
    except Exception as e:
        st.error(f"Error initializing components: {str(e)}")
        st.code(traceback.format_exc())
        # Fallback to just the scraper without DB
        try:
            return {
                "scraper": CompanyScraper(initialize_db=False),
                "db_available": False
            }
        except Exception as e2:
            st.error(f"Critical error initializing scraper: {str(e2)}")
            return None

components = initialize_components()

if not components:
    st.error("Failed to initialize any components. Please check your configuration.")
    st.stop()

# Create sidebar for controls
st.sidebar.title("Lead Generation Controls")

if not components.get("db_available", False):
    st.sidebar.warning("⚠️ Running in limited mode without database connection")

# Target company selection
target_company_options = ["Couchbase", "Subkit", "Legion Technologies"]
selected_target = st.sidebar.selectbox(
    "Select Your Company",
    options=target_company_options
)

# Map display names to internal names
target_company_map = {
    "Couchbase": "couchbase",
    "Subkit": "subkit",
    "Legion Technologies": "legion"
}

# Initialize components with selected target company
@st.cache_resource
def initialize_components(target_company):
    """Initialize and cache the system components."""
    try:
        # First initialize scraper with target company
        scraper = CompanyScraper(target_company=target_company_map[target_company], initialize_db=False)
        
        # Then try to initialize database connections
        try:
            from database.mongo_client import MongoDBManager
            from embeddings.vector_store import VectorStore
            
            # Try to create MongoDBManager and VectorStore explicitly
            try:
                db_manager = MongoDBManager()
                st.success("MongoDB connected successfully")
                vector_store = VectorStore()
                
                # If we get here, database initialization succeeded
                scraper.db = db_manager
                scraper.vector_store = vector_store
                scraper.has_db = True
                
                return {
                    "scraper": scraper,
                    "notifier": LeadNotifier(),
                    "vector_store": vector_store,
                    "db": db_manager,
                    "db_available": True
                }
            except Exception as db_error:
                error_msg = str(db_error)
                if "Authentication failed" in error_msg or "bad auth" in error_msg:
                    st.error("⚠️ MongoDB Authentication Failed: Please check your username and password in config.py")
                    st.info("You may need to update your MongoDB Atlas credentials or whitelist your IP address.")
                else:
                    st.error(f"Database connection error: {error_msg}")
                
                st.warning("Running in limited mode without database connection")
                # Return with only scraper initialized
                return {
                    "scraper": scraper,
                    "db_available": False
                }
        except Exception as db_error:
            st.warning(f"Database connection failed, running in limited mode: {str(db_error)}")
            # Return with only scraper initialized
            return {
                "scraper": scraper,
                "db_available": False
            }
    except Exception as e:
        st.error(f"Error initializing components: {str(e)}")
        st.code(traceback.format_exc())
        return None

# Initialize components with selected target
components = initialize_components(selected_target)

# Get all companies for the selected target
def get_all_companies():
    """Get all companies for the selected target company."""
    return components["scraper"].COMPANY_RELATIONSHIPS[target_company_map[selected_target]]["companies"]

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
st.title("Lead Generation Dashboard")
st.write("Use this dashboard to scrape, review, and manage leads before sending them to Slack.")

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
                company_leads = components["scraper"]._fetch_news(comp, time_range)
                leads.extend(company_leads)
                progress_bar.progress((i + 1) / total_companies)
                time.sleep(1)  # Small delay to avoid rate limiting
        else:
            status_text.text(f"Scraping {company}...")
            leads = components["scraper"]._fetch_news(company, time_range)
            progress_bar.progress(1.0)
        
        status_text.text("Scraping completed!")
        return leads
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        st.code(traceback.format_exc())
        return []

def check_duplicate_lead(lead: Dict[str, Any], components: Dict[str, Any]) -> bool:
    """Check if a lead is a duplicate in both MongoDB and Pinecone."""
    try:
        # Check MongoDB first (faster)
        if components["db"].get_lead_by_url(lead["url"]):
            return True
            
        # Check Pinecone for semantic duplicates
        lead_text = f"{lead['company']} {lead['title']} {lead.get('description', '')}"
        if components["vector_store"].check_duplicate(lead_text):
            return True
            
        # Check session state for pending leads
        if 'pending_leads' in st.session_state:
            for pending_lead in st.session_state.pending_leads:
                if pending_lead['url'] == lead['url']:
                    return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking for duplicates: {str(e)}")
        return False

def filter_duplicates(leads: List[Dict[str, Any]], components: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter out duplicate leads from the list."""
    unique_leads = []
    for lead in leads:
        if not check_duplicate_lead(lead, components):
            unique_leads.append(lead)
    return unique_leads

def display_leads(leads):
    """Display leads and allow the user to approve them before sending to Slack."""
    if not leads:
        st.warning("No leads found. Try adjusting your search criteria.")
        return
    
    # Initialize pending_leads in session state if not exists
    if 'pending_leads' not in st.session_state:
        st.session_state.pending_leads = []
    
    # Add new leads to pending leads if they're not already there
    for lead in leads:
        if lead not in st.session_state.pending_leads:
            st.session_state.pending_leads.append(lead)
    
    st.success(f"Found {len(st.session_state.pending_leads)} leads. Review and approve them below.")
    
    # Group leads by company
    companies = sorted(set(lead["company"] for lead in st.session_state.pending_leads))
    leads_to_remove = []  # Track leads to remove
    
    for company in companies:
        company_leads = [lead for lead in st.session_state.pending_leads if lead["company"] == company]
        
        if not company_leads:  # Skip if no leads for this company
            continue
            
        st.subheader(f"{company} ({len(company_leads)} leads)")
        
        for i, lead in enumerate(company_leads):
            with st.expander(f"{lead['title']}", expanded=True):
                # Display lead details in the same format as Slack
                st.markdown("### 🔍 New Lead Alert")
                st.markdown(f"**Company:** {lead['company']}")
                st.markdown(f"**Title:** [{lead['title']}]({lead['url']})")
                
                # Display Why this matters section
                st.markdown("### Why this matters:")
                try:
                    value_types = json.loads(lead.get("value_types", "[]"))
                    if value_types:
                        st.markdown(f"**Value Types:** {', '.join(vtype.replace('_', ' ').title() for vtype in value_types)}")
                except json.JSONDecodeError:
                    st.write("Error parsing value types.")
                
                # Display relevance explanation
                if lead.get("relevance_explanation"):
                    st.markdown(f"**Relevance:** {lead['relevance_explanation']}")
                
                # Display CSM value explanation
                if lead.get("csm_value_explanation"):
                    st.markdown(f"**Business Impact:** {lead['csm_value_explanation']}")
                
                # Display action items
                st.markdown("### Suggested Actions:")
                try:
                    action_items = json.loads(lead.get("action_items", "[]"))
                    if action_items:
                        for action in action_items:
                            st.markdown(f"📌 {action}")
                    else:
                        st.write("No action items suggested.")
                except json.JSONDecodeError:
                    st.write("Error parsing action items.")
                
                # Display metadata and additional details directly
                st.markdown("### Additional Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Source:** {lead.get('source', 'Unknown')}")
                    st.markdown(f"**Category:** {lead.get('category', 'Unknown').replace('_', ' ').title()}")
                with col2:
                    st.markdown(f"**Relevance Score:** {lead.get('relevance_score', 'N/A')}/100")
                    st.markdown(f"**URL:** [{lead['url']}]({lead['url']})")

                if lead.get('description'):
                    st.markdown("### Full Description")
                    st.markdown(lead['description'])
                
                # Approval buttons
                col1, col2 = st.columns(2)
                
                # Show appropriate buttons based on database availability
                if components.get("db_available", False):
                    approve = col1.button("Approve & Send to Slack", key=f"approve_{lead['id']}")
                    reject = col2.button("Reject", key=f"reject_{lead['id']}")
                    
                    if approve:
                        with st.spinner("Sending to Slack..."):
                            try:
                                success = components["notifier"].notify(lead)
                                if success:
                                    st.success("Successfully sent to Slack!")
                                    leads_to_remove.append(lead)  # Mark for removal
                                else:
                                    st.error("Failed to send to Slack. Please try again.")
                            except Exception as e:
                                st.error(f"Error sending to Slack: {str(e)}")
                        
                    if reject:
                        st.info("Lead rejected and will not be sent to Slack.")
                        leads_to_remove.append(lead)  # Mark for removal
                else:
                    # In limited mode without database
                    approve = col1.button("Save Lead (Limited Mode)", key=f"limited_{lead['id']}")
                    if approve:
                        st.info("Running in limited mode without database connection. Lead details can be copied manually.")
    
    # Remove processed leads from session state
    if leads_to_remove:
        st.session_state.pending_leads = [lead for lead in st.session_state.pending_leads if lead not in leads_to_remove]
        st.rerun()  # Rerun the app to refresh the UI

# Scrape button
if st.sidebar.button("Start Scraping"):
    with st.spinner("Scraping in progress..."):
        scraped_leads = scrape_leads(selected_company, selected_time_range)
        
        # Filter out duplicates before displaying
        if components.get("db_available", False):
            unique_leads = filter_duplicates(scraped_leads, components)
            # Store new leads in session state
            if 'pending_leads' not in st.session_state:
                st.session_state.pending_leads = []
            # Add only new leads that aren't in pending_leads
            for lead in unique_leads:
                if lead not in st.session_state.pending_leads:
                    st.session_state.pending_leads.append(lead)
        else:
            st.session_state.pending_leads = scraped_leads
        
    # Display leads for review
    display_leads(st.session_state.pending_leads)
elif 'pending_leads' in st.session_state:
    # Display previously scraped leads that are still pending
    display_leads(st.session_state.pending_leads)

# Add a clear button to reset pending leads
if 'pending_leads' in st.session_state and len(st.session_state.pending_leads) > 0:
    if st.sidebar.button("Clear Pending Leads"):
        st.session_state.pending_leads = []
        st.experimental_rerun()

# Recent leads section - only show if database is available
if components.get("db_available", False):
    st.sidebar.markdown("---")
    if st.sidebar.button("View Recent Leads"):
        with st.spinner("Fetching recent leads..."):
            try:
                if "db" in components:
                    recent_leads = components["db"].get_recent_leads(10)
                    if recent_leads:
                        # Clear any existing pending leads
                        st.session_state.pending_leads = []
                        # Add recent leads to pending leads for display
                        st.session_state.pending_leads.extend(recent_leads)
                        st.success(f"Loaded {len(recent_leads)} recent leads")
                        # Force a rerun to update the display
                        st.experimental_rerun()
                    else:
                        st.warning("No recent leads found in the database.")
                else:
                    st.error("Database component not available")
            except Exception as e:
                st.error(f"Error fetching recent leads: {str(e)}")
                st.code(traceback.format_exc())

# Add statistics and info to sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("About")
st.sidebar.info(
    "This dashboard allows you to scrape news for companies, "
    "review leads, and send notifications to Slack."
) 