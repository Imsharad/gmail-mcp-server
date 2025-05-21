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
from src.gmail_api import GmailClient

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

# Initialize Gmail API (now the client facade)
gmail_client = GmailClient(CREDENTIALS_FILE, TOKEN_FILE)

# Try to authenticate (authentication is now handled within GmailClient.__init__)
if not os.path.exists(CREDENTIALS_FILE):
    logger.error(f"Credentials file {CREDENTIALS_FILE} not found. Please set up your credentials.")
    raise FileNotFoundError(f"Credentials file {CREDENTIALS_FILE} not found")

# Check if the client authenticated successfully
if not gmail_client.authenticated:
    logger.error("Gmail API authentication failed. Please check your credentials or logs.")
    raise Exception("Gmail API authentication failed")

logger.info("Gmail API client initialized and authenticated successfully.")

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
    # Use Gmail client facade
    query = f"label:{label}" if label else ""
    messages = gmail_client.list_messages(max_results=max_results, query=query)
    
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
    # Use Gmail client facade
    message = gmail_client.get_message(email_id)
    
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
    # Use Gmail client facade
    messages = gmail_client.list_messages(max_results=max_results, query=query)
    
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
    # Use Gmail client facade
    message_id = gmail_client.send_message(to, subject, body)
    
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
    # Use Gmail client facade
    message_id = gmail_client.reply_to_message(email_id, body)
    
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
    # Use Gmail client facade
    success = gmail_client.delete_message(email_id)
    
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
    # Use Gmail client facade
    results = gmail_client.batch_delete_messages(email_ids)
    
    if results["success"] > 0 and results["failed"] == 0:
        return f"All {results['success']} emails were deleted successfully."
    elif results["success"] > 0 and results["failed"] > 0:
        return f"{results['success']} emails deleted successfully. {results['failed']} emails failed to delete: {', '.join(results['failed_ids'])}"
    else:
        return f"Failed to delete any emails. Please check the logs for details."

# --- Label Management Tools ---

@mcp.tool()
async def list_gmail_labels() -> str:
    """List all available labels in your Gmail account.
    
    Returns:
        A formatted string listing label names and IDs, or an error message.
    """
    labels = gmail_client.list_labels()
    if not labels:
        return "Could not retrieve labels or no labels found."
        
    result = "Available Labels:\n\n"
    for label in labels:
        label_type = label.get('type', 'user') # System labels vs user labels
        result += f"Name: {label['name']}\n"
        result += f"ID: {label['id']}\n"
        result += f"Type: {label_type}\n"
        # Optional: Add visibility info if needed
        # result += f"Label List Visibility: {label.get('labelListVisibility', 'N/A')}\n"
        # result += f"Message List Visibility: {label.get('messageListVisibility', 'N/A')}\n"
        result += "---\n"
        
    return result

@mcp.tool()
async def get_gmail_label(label_id: str) -> str:
    """Get details about a specific Gmail label using its ID.

    Args:
        label_id: The ID of the label (e.g., 'Label_123').

    Returns:
        Formatted string with label details or an error message.
    """
    label = gmail_client.get_label(label_id)
    if not label:
        return f"Could not retrieve label with ID '{label_id}' or it does not exist."

    result = f"Label Details (ID: {label['id']}):\n"
    result += f"  Name: {label['name']}\n"
    result += f"  Type: {label.get('type', 'user')}\n"
    result += f"  Messages Total: {label.get('messagesTotal', 'N/A')}\n"
    result += f"  Messages Unread: {label.get('messagesUnread', 'N/A')}\n"
    result += f"  Threads Total: {label.get('threadsTotal', 'N/A')}\n"
    result += f"  Threads Unread: {label.get('threadsUnread', 'N/A')}\n"
    result += f"  Label List Visibility: {label.get('labelListVisibility', 'N/A')}\n"
    result += f"  Message List Visibility: {label.get('messageListVisibility', 'N/A')}\n"
    # Optional: Add color info if needed
    # color = label.get('color', {})
    # result += f"  Color: Background={color.get('backgroundColor')}, Text={color.get('textColor')}\n"
    
    return result

@mcp.tool()
async def create_gmail_label(name: str) -> str:
    """Create a new Gmail label.

    Args:
        name: The desired name for the new label.

    Returns:
        Confirmation message with the new label ID or an error message.
    """
    # Basic validation for name
    if not name or len(name.strip()) == 0:
        return "Label name cannot be empty."
        
    created_label = gmail_client.create_label(name.strip()) # Use default visibility
    
    if created_label:
        return f"Label '{created_label['name']}' created successfully with ID: {created_label['id']}."
    else:
        return f"Failed to create label '{name}'. It might already exist or an error occurred. Check logs."

@mcp.tool()
async def delete_gmail_label(label_id: str) -> str:
    """Delete an existing Gmail label using its ID.

    Important: Deleting a label does not delete the messages with that label.
    System labels (like INBOX, SPAM, TRASH) cannot be deleted.

    Args:
        label_id: The ID of the label to delete (e.g., 'Label_123').

    Returns:
        Confirmation message or an error message.
    """
    if not label_id:
        return "Label ID cannot be empty."
        
    success = gmail_client.delete_label(label_id)
    
    if success:
        return f"Label with ID '{label_id}' deleted successfully."
    else:
        return f"Failed to delete label with ID '{label_id}'. It might not exist, be a system label, or an error occurred. Check logs."

@mcp.tool()
async def add_labels_to_email(email_id: str, label_ids: List[str]) -> str:
    """Add one or more labels to a specific email using label IDs.

    Args:
        email_id: The ID of the email to modify.
        label_ids: A list of label IDs to add to the email (e.g., ['Label_123', 'Label_456']).

    Returns:
        Confirmation message or an error message.
    """
    if not email_id:
        return "Email ID cannot be empty."
    if not label_ids:
        return "You must provide at least one label ID to add."
        
    updated_message = gmail_client.modify_message_labels(message_id=email_id, add_label_ids=label_ids)
    
    if updated_message:
        # Optional: Could format the updated labels list: list(updated_message.get('labelIds', []))
        return f"Successfully added labels {label_ids} to email {email_id}."
    else:
        return f"Failed to add labels to email {email_id}. Check if the email ID and label IDs are valid. Check logs."

@mcp.tool()
async def remove_labels_from_email(email_id: str, label_ids: List[str]) -> str:
    """Remove one or more labels from a specific email using label IDs.

    Args:
        email_id: The ID of the email to modify.
        label_ids: A list of label IDs to remove from the email (e.g., ['Label_123', 'UNREAD']).

    Returns:
        Confirmation message or an error message.
    """
    if not email_id:
        return "Email ID cannot be empty."
    if not label_ids:
        return "You must provide at least one label ID to remove."
        
    updated_message = gmail_client.modify_message_labels(message_id=email_id, remove_label_ids=label_ids)
    
    if updated_message:
        # Optional: Could format the updated labels list: list(updated_message.get('labelIds', []))
        return f"Successfully removed labels {label_ids} from email {email_id}."
    else:
        return f"Failed to remove labels from email {email_id}. Check if the email ID and label IDs are valid. Check logs."

# --- Draft Management Tools ---

@mcp.tool()
async def list_drafts(max_results: int = 10) -> str:
    """List email drafts.
    
    Args:
        max_results: Maximum number of drafts to return (default: 10).
    
    Returns:
        A formatted string containing draft information, or a message if no drafts are found or an error occurs.
    """
    try:
        draft_list = gmail_client.list_drafts(max_results=max_results)
        
        if not draft_list:
            return "No drafts found."
        
        response = f"Found {len(draft_list)} drafts:\n\n"
        for draft in draft_list:
            draft_id = draft.get('id', 'N/A')
            message_data = draft.get('message', {})
            
            payload = message_data.get('payload', {})
            headers_list = payload.get('headers', [])
            headers = {h['name'].lower(): h['value'] for h in headers_list}
            
            subject = headers.get('subject', 'N/A')
            to_recipients = headers.get('to', 'N/A')
            snippet = message_data.get('snippet', 'N/A')

            response += f"ID: {draft_id}\n"
            response += f"  To: {to_recipients}\n"
            response += f"  Subject: {subject}\n"
            response += f"  Snippet: {snippet}\n"
            response += "---\n"
        return response
    except Exception as e:
        logger.error(f"Error in list_drafts tool: {e}")
        return f"An error occurred while listing drafts: {e}"

@mcp.tool()
async def get_draft(draft_id: str) -> str:
    """Get the full content of a specific email draft.
    
    Args:
        draft_id: The ID of the draft to retrieve.
    
    Returns:
        The full draft content including headers and body, or a message if not found.
    """
    try:
        draft = gmail_client.get_draft(draft_id)
        
        if not draft:
            return f"Draft with ID '{draft_id}' not found."
        
        message_data = draft.get('message', {})
        payload = message_data.get('payload', {})
        headers_list = payload.get('headers', [])
        headers = {h['name'].lower(): h['value'] for h in headers_list}

        response = f"Draft ID: {draft.get('id', 'N/A')}\n"
        response += f"From: {headers.get('from', 'N/A')}\n"
        response += f"To: {headers.get('to', 'N/A')}\n"
        cc_recipients = headers.get('cc')
        if cc_recipients:
            response += f"Cc: {cc_recipients}\n"
        response += f"Subject: {headers.get('subject', 'N/A')}\n"
        
        # Extracting body (simplified, assumes plain text for drafts)
        # Similar to get_email, but drafts might not be as complex
        body_content = "N/A"
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part['body']:
                        body_content = gmail_client.service.users().messages().get( # Hacky, but body isn't directly in draft
                            userId='me', id=message_data['id'], format='raw' 
                        ).execute()['raw'] # This is not ideal as it re-fetches
                        # A better way would be to decode from part['body']['data'] if available
                        # but draft message parts often don't have 'data' directly, they are references
                        # For simplicity, let's try to decode if data is present, else use snippet
                        import base64
                        try:
                            body_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                        except (KeyError, TypeError, binascii.Error): # binascii for potential padding errors
                             pass # Fallback to snippet or N/A if direct body decoding fails
            if body_content == "N/A": # If plain text part not found or failed
                body_content = message_data.get('snippet', 'Body not directly available, snippet shown.')

        elif 'body' in payload and 'data' in payload['body']:
            import base64
            try:
                body_content = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            except (KeyError, TypeError, binascii.Error):
                 body_content = message_data.get('snippet', 'Body not directly available, snippet shown.')
        else:
            body_content = message_data.get('snippet', 'Body not available.')


        response += f"\nBody:\n{body_content}\n"
        
        return response
    except Exception as e:
        logger.error(f"Error in get_draft tool for ID {draft_id}: {e}")
        return f"An error occurred while retrieving draft {draft_id}: {e}"

@mcp.tool()
async def create_draft(to: str, subject: str, body: str) -> str:
    """Create a new email draft.
    
    Args:
        to: Recipient email address.
        subject: Email subject.
        body: Email body content.
    
    Returns:
        Confirmation message with the new draft ID or an error message.
    """
    try:
        if not to or not subject: # Basic validation
            return "Recipient 'to' and 'subject' cannot be empty for creating a draft."

        created_draft = gmail_client.create_draft(to, subject, body)
        
        if created_draft and created_draft.get('id'):
            return f"Draft created successfully. ID: {created_draft['id']}"
        else:
            # Log the actual response from gmail_client if it's unexpected
            logger.warning(f"Failed to create draft. Gmail_client.create_draft returned: {created_draft}")
            return "Failed to create draft. Please check the logs for details."
    except Exception as e:
        logger.error(f"Error in create_draft tool: {e}")
        return f"An error occurred while creating the draft: {e}"

@mcp.tool()
async def update_draft(draft_id: str, to: str, subject: str, body: str) -> str:
    """Update an existing email draft.
    
    Args:
        draft_id: The ID of the draft to update.
        to: New recipient email address.
        subject: New email subject.
        body: New email body content.
    
    Returns:
        Confirmation message or an error message.
    """
    try:
        if not draft_id or not to or not subject: # Basic validation
            return "Draft ID, recipient 'to', and 'subject' cannot be empty for updating a draft."

        updated_draft = gmail_client.update_draft(draft_id, to, subject, body)
        
        if updated_draft and updated_draft.get('id'):
            return f"Draft with ID '{updated_draft['id']}' updated successfully."
        else:
            logger.warning(f"Failed to update draft {draft_id}. Gmail_client.update_draft returned: {updated_draft}")
            return f"Failed to update draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs."
    except Exception as e:
        logger.error(f"Error in update_draft tool for ID {draft_id}: {e}")
        return f"An error occurred while updating draft {draft_id}: {e}"

@mcp.tool()
async def delete_draft(draft_id: str) -> str:
    """Delete an email draft.
    
    Args:
        draft_id: The ID of the draft to delete.
    
    Returns:
        Confirmation message or an error message.
    """
    try:
        if not draft_id:
            return "Draft ID cannot be empty."
            
        success = gmail_client.delete_draft(draft_id)
        
        if success:
            return f"Draft with ID '{draft_id}' deleted successfully."
        else:
            # Log implicitly handled by gmail_client.delete_draft for 404s or other errors
            return f"Failed to delete draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs."
    except Exception as e:
        logger.error(f"Error in delete_draft tool for ID {draft_id}: {e}")
        return f"An error occurred while deleting draft {draft_id}: {e}"

@mcp.tool()
async def send_draft(draft_id: str) -> str:
    """Send an existing email draft.
    
    Args:
        draft_id: The ID of the draft to send.
    
    Returns:
        Confirmation message with the sent message ID or an error message.
    """
    try:
        if not draft_id:
            return "Draft ID cannot be empty."

        sent_message = gmail_client.send_draft(draft_id)
        
        if sent_message and sent_message.get('id'):
            return f"Draft with ID '{draft_id}' sent successfully. Message ID: {sent_message['id']}"
        else:
            # Log implicitly handled by gmail_client.send_draft for 404s or other errors
            return f"Failed to send draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs."
    except Exception as e:
        logger.error(f"Error in send_draft tool for ID {draft_id}: {e}")
        return f"An error occurred while sending draft {draft_id}: {e}"

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
        mcp.run(transport="streamable-http", host=SERVER_HOST, port=port, path=SERVER_PATH, log_level="debug")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        raise
