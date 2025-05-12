#!/usr/bin/env python3
"""
Test script for Gmail email deletion functionality
"""

import os
import sys
import json
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Gmail API module
from src.gmail_api import GmailAPI

# Load environment variables
load_dotenv()

def main():
    """Test the email deletion functionality."""
    # Initialize Gmail API client
    credentials_file = os.getenv('CREDENTIALS_FILE', 'credentials.json')
    token_file = os.getenv('TOKEN_FILE', 'token.json')
    
    logger.info(f"Using credentials file: {credentials_file}")
    logger.info(f"Using token file: {token_file}")
    
    if not os.path.exists(credentials_file):
        logger.error(f"Credentials file {credentials_file} not found.")
        return
        
    # Initialize Gmail API
    gmail_api = GmailAPI(credentials_file, token_file)
    
    # Authenticate
    auth_success = gmail_api.authenticate()
    if not auth_success:
        logger.error("Authentication failed.")
        return
        
    logger.info("Authentication successful.")
    
    # List recent emails
    logger.info("Listing the 5 most recent emails...")
    messages = gmail_api.list_messages(max_results=5)
    
    if not messages:
        logger.info("No emails found.")
        return
        
    # Display message info
    for i, message in enumerate(messages):
        print(f"\nEmail {i+1}:")
        print(f"ID: {message['id']}")
        print(f"From: {message['from']}")
        print(f"Subject: {message['subject']}")
        print(f"Date: {message['date']}")
        
    # Ask for email to delete
    delete_option = input("\nDo you want to delete a single email or multiple emails? (single/multiple/none): ").strip().lower()
    
    if delete_option == "single":
        email_index = int(input("Enter the number of the email to delete (1-5): "))
        
        if 1 <= email_index <= len(messages):
            message_id = messages[email_index-1]['id']
            confirm = input(f"Are you sure you want to delete email with subject '{messages[email_index-1]['subject']}'? (yes/no): ")
            
            if confirm.lower() == "yes":
                result = gmail_api.delete_message(message_id)
                if result:
                    print(f"Email deleted successfully.")
                else:
                    print(f"Failed to delete email.")
        else:
            print("Invalid email number.")
            
    elif delete_option == "multiple":
        indices = input("Enter the numbers of emails to delete (comma-separated, e.g., 1,3,5): ")
        try:
            email_indices = [int(idx.strip()) for idx in indices.split(",")]
            
            # Validate indices
            valid_indices = [idx for idx in email_indices if 1 <= idx <= len(messages)]
            
            if valid_indices:
                message_ids = [messages[idx-1]['id'] for idx in valid_indices]
                print("The following emails will be deleted:")
                for idx in valid_indices:
                    print(f" - {messages[idx-1]['subject']}")
                
                confirm = input("Are you sure you want to delete these emails? (yes/no): ")
                
                if confirm.lower() == "yes":
                    results = gmail_api.batch_delete_messages(message_ids)
                    print(f"Results: {results['success']} succeeded, {results['failed']} failed")
                    if results['failed_ids']:
                        print(f"Failed IDs: {results['failed_ids']}")
            else:
                print("No valid email numbers provided.")
        except Exception as e:
            print(f"Error processing input: {e}")
    
    print("Test completed.")

if __name__ == "__main__":
    main() 