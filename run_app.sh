#!/bin/bash

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "myenv" ]; then
    echo "Activating virtual environment..."
    source myenv/bin/activate
else
    echo "No virtual environment found. Continuing with system Python..."
fi

# Run the Streamlit app
echo "Starting Streamlit app..."
streamlit run app.py 