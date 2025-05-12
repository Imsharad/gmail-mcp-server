#!/usr/bin/env python3
"""
Gmail MCP Server - Provides Gmail functionality through the Model Context Protocol
"""

import os
import json
import logging
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Import MCP SDK
from fastmcp import FastMCP

# Import Gmail API module
from src.gmail_api import GmailAPI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("gmail")

# Initialize Gmail API client
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
TOKEN_FILE = os.getenv('TOKEN_FILE', 'token.json')
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
PREFERRED_PORT = int(os.getenv('SERVER_PORT', '8000'))
SERVER_PATH = os.getenv('SERVER_PATH', '/mcp')

# Initialize Gmail API
gmail_api = GmailAPI(CREDENTIALS_FILE, TOKEN_FILE)

# Try to authenticate
if not os.path.exists(CREDENTIALS_FILE):
    logger.error(f"Credentials file {CREDENTIALS_FILE} not found. Please set up your credentials.")
    raise FileNotFoundError(f"Credentials file {CREDENTIALS_FILE} not found")

auth_success = gmail_api.authenticate()
if not auth_success:
    logger.error("Gmail API authentication failed. Please check your credentials.")
    raise Exception("Gmail API authentication failed")

logger.info("Gmail API authentication successful.")

# Tool implementations
@mcp.tool()
async def list_emails(max_results: int = 10, label: str = "INBOX") -> str:
    """List emails from your Gmail inbox.
    
    Args:
        max_results: Maximum number of emails to return (default: 10)
        label: Gmail label to filter by (default: INBOX)
    
    Returns:
        A formatted string containing email information
    """
    # Use Gmail API
    query = f"label:{label}" if label else ""
    messages = gmail_api.list_messages(max_results=max_results, query=query)
    
    if not messages:
        return f"No emails found with label '{label}'."
    
    result = f"Found {len(messages)} emails with label '{label}':\n\n"
    
    for message in messages:
        read_status = "Read" if message["read"] else "Unread"
        result += f"ID: {message['id']}\n"
        result += f"From: {message['from']}\n"
        result += f"Subject: {message['subject']}\n"
        result += f"Date: {message['date']}\n"
        result += f"Status: {read_status}\n"
        result += "---\n"
    
    return result

@mcp.tool()
async def get_email(email_id: str) -> str:
    """Get the full content of a specific email.
    
    Args:
        email_id: The ID of the email to retrieve
    
    Returns:
        The full email content including headers and body
    """
    # Use Gmail API
    message = gmail_api.get_message(email_id)
    
    if not message:
        return f"Email with ID '{email_id}' not found."
    
    result = f"From: {message['from']}\n"
    result += f"To: {message['to']}\n"
    if message.get('cc'):
        result += f"CC: {message['cc']}\n"
    result += f"Subject: {message['subject']}\n"
    result += f"Date: {message['date']}\n"
    result += f"Labels: {', '.join(message['labels'])}\n"
    result += f"Status: {'Read' if message['read'] else 'Unread'}\n"
    result += f"\n{message['body']}"
    
    return result

@mcp.tool()
async def search_emails(query: str, max_results: int = 5) -> str:
    """Search for emails matching a query.
    
    Args:
        query: Search query to match against email fields
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        A formatted string containing matching email information
    """
    # Use Gmail API
    messages = gmail_api.list_messages(max_results=max_results, query=query)
    
    if not messages:
        return f"No emails found matching query '{query}'."
    
    result = f"Found {len(messages)} emails matching query '{query}':\n\n"
    
    for message in messages:
        read_status = "Read" if message["read"] else "Unread"
        result += f"ID: {message['id']}\n"
        result += f"From: {message['from']}\n"
        result += f"Subject: {message['subject']}\n"
        result += f"Date: {message['date']}\n"
        result += f"Status: {read_status}\n"
        result += "---\n"
    
    return result

@mcp.tool()
async def send_email(to: str, subject: str, body: str) -> str:
    """Send a new email.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
    
    Returns:
        Confirmation message
    """
    # Use Gmail API
    message_id = gmail_api.send_message(to, subject, body)
    
    if message_id:
        return f"Email sent successfully. Message ID: {message_id}"
    else:
        return "Failed to send email. Please check the logs for details."

@mcp.tool()
async def reply_to_email(email_id: str, body: str) -> str:
    """Reply to an existing email.
    
    Args:
        email_id: ID of the email to reply to
        body: Reply message content
    
    Returns:
        Confirmation message
    """
    # Use Gmail API
    message_id = gmail_api.reply_to_message(email_id, body)
    
    if message_id:
        return f"Reply sent successfully. Message ID: {message_id}"
    else:
        return "Failed to send reply. Please check the logs for details."

@mcp.tool()
async def delete_email(email_id: str) -> str:
    """Delete a single email.
    
    Args:
        email_id: ID of the email to delete
    
    Returns:
        Confirmation message
    """
    # Use Gmail API
    success = gmail_api.delete_message(email_id)
    
    if success:
        return f"Email with ID {email_id} deleted successfully."
    else:
        return f"Failed to delete email with ID {email_id}. Please check the logs for details."

@mcp.tool()
async def delete_emails(email_ids: List[str]) -> str:
    """Delete multiple emails.
    
    Args:
        email_ids: List of email IDs to delete
    
    Returns:
        Confirmation message with results
    """
    # Use Gmail API
    results = gmail_api.batch_delete_messages(email_ids)
    
    if results["success"] > 0 and results["failed"] == 0:
        return f"All {results['success']} emails were deleted successfully."
    elif results["success"] > 0 and results["failed"] > 0:
        return f"{results['success']} emails deleted successfully. {results['failed']} emails failed to delete: {', '.join(results['failed_ids'])}"
    else:
        return f"Failed to delete any emails. Please check the logs for details."

def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from the given port.
    
    Args:
        start_port: The preferred port to start checking from
        max_attempts: Maximum number of ports to check
        
    Returns:
        An available port number or -1 if no port is available
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((SERVER_HOST, port))
                # If we get here, the port is available
                return port
            except socket.error:
                logger.info(f"Port {port} is already in use, trying next port...")
                continue
    return -1

# Run the server
if __name__ == "__main__":
    logger.info("Starting Gmail MCP Server...")
    
    # Find an available port
    port = find_available_port(PREFERRED_PORT)
    
    if port == -1:
        logger.error(f"Could not find an available port after trying {PREFERRED_PORT} through {PREFERRED_PORT + 9}")
        raise RuntimeError("No available ports found")
    
    if port != PREFERRED_PORT:
        logger.warning(f"Preferred port {PREFERRED_PORT} was not available. Using port {port} instead.")
    
    logger.info(f"Server will run on {SERVER_HOST}:{port}{SERVER_PATH}")
    
    try:
        mcp.run(transport="streamable-http", host=SERVER_HOST, port=port, path=SERVER_PATH)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        raise
