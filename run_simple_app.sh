#!/bin/bash

# Activate virtual environment if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the simplified Streamlit app
streamlit run simple_app.py 