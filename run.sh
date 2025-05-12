#!/bin/bash

# Navigate to the script's directory (project root)
cd "$(dirname "$0")"

# --- Combined initialization logic ---
echo "Setting up environment..."

# Check if python3 is available
if ! command -v python3 &> /dev/null
then
    echo "python3 could not be found. Please install Python 3."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv'..."
    python3 -m venv venv > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment. If you are in a non-standard shell, you might need to adjust this."
    exit 1
fi

# Upgrade pip
pip install --upgrade pip > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Warning: Failed to upgrade pip."
    # Not exiting here, as it might still be usable if upgrade fails but pip works
fi

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to install dependencies from requirements.txt."
        exit 1
    fi
else
    echo "requirements.txt not found. Please ensure it exists in the project root."
    exit 1
fi
# --- End of combined initialization logic ---

# Run the server
echo "Starting Gmail MCP Server... (Press CTRL+C to stop)"
export PYTHONPATH="$PWD:$PYTHONPATH" # Add project root to PYTHONPATH
python src/server.py

echo "Server stopped." 