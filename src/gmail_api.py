"""
Gmail API Integration Module

This module handles authentication and interaction with the Gmail API.
"""

import os
import json
import base64
import logging
from typing import Dict, List, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import google.auth.exceptions
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Set up logging
logger = logging.getLogger(__name__)

# Gmail API scopes
# If modifying these scopes, delete the token.json file
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify'
]

class GmailAPI:
    """Gmail API wrapper class for MCP server integration."""
    
    def __init__(self, credentials_file: str, token_file: str):
        """Initialize the Gmail API client.
        
        Args:
            credentials_file: Path to the credentials.json file
            token_file: Path to the token.json file for storing user credentials
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticated = False
    
    def authenticate(self) -> bool:
        """Authenticate with the Gmail API.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(open(self.token_file).read()), SCOPES)
            except Exception as e:
                logger.error(f"Error loading credentials from token file: {e}")
        
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except google.auth.exceptions.RefreshError as e:
                    logger.error(f"Error refreshing credentials: {e}")
                    creds = None
            
            # If still no valid credentials, need to authenticate
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Error during authentication flow: {e}")
                    return False
            
            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"Error saving credentials to token file: {e}")
        
        try:
            # Build the Gmail API service
            self.service = build('gmail', 'v1', credentials=creds)
            self.authenticated = True
            logger.info("Successfully authenticated with Gmail API")
            return True
        except Exception as e:
            logger.error(f"Error building Gmail service: {e}")
            return False
    
    def list_messages(self, max_results: int = 10, query: str = "") -> List[Dict[str, Any]]:
        """List messages from Gmail.
        
        Args:
            max_results: Maximum number of messages to return
            query: Gmail search query (e.g., "is:unread", "from:example@gmail.com")
        
        Returns:
            List of message dictionaries with id, snippet, etc.
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return []
        
        try:
            # Get list of messages
            results = self.service.users().messages().list(
                userId='me', maxResults=max_results, q=query).execute()
            messages = results.get('messages', [])
            
            # Get details for each message
            detailed_messages = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me', id=message['id']).execute()
                
                # Extract headers
                headers = {}
                for header in msg['payload']['headers']:
                    headers[header['name'].lower()] = header['value']
                
                # Create a simplified message object
                detailed_message = {
                    'id': msg['id'],
                    'threadId': msg['threadId'],
                    'snippet': msg.get('snippet', ''),
                    'from': headers.get('from', ''),
                    'to': headers.get('to', ''),
                    'subject': headers.get('subject', ''),
                    'date': headers.get('date', ''),
                    'labels': msg.get('labelIds', []),
                    'read': 'UNREAD' not in msg.get('labelIds', [])
                }
                
                detailed_messages.append(detailed_message)
            
            return detailed_messages
        
        except Exception as e:
            logger.error(f"Error listing messages: {e}")
            return []
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message with its full content.
        
        Args:
            message_id: The ID of the message to retrieve
        
        Returns:
            Message dictionary with full content or None if not found
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return None
        
        try:
            # Get the message
            msg = self.service.users().messages().get(
                userId='me', id=message_id, format='full').execute()
            
            # Extract headers
            headers = {}
            for header in msg['payload']['headers']:
                headers[header['name'].lower()] = header['value']
            
            # Extract body content
            body = self._get_message_body(msg['payload'])
            
            # Create a detailed message object
            detailed_message = {
                'id': msg['id'],
                'threadId': msg['threadId'],
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'cc': headers.get('cc', ''),
                'subject': headers.get('subject', ''),
                'date': headers.get('date', ''),
                'labels': msg.get('labelIds', []),
                'read': 'UNREAD' not in msg.get('labelIds', []),
                'body': body
            }
            
            return detailed_message
        
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    def _get_message_body(self, payload: Dict[str, Any]) -> str:
        """Extract the message body from the payload.
        
        Args:
            payload: Message payload from Gmail API
        
        Returns:
            Decoded message body as text
        """
        if 'body' in payload and payload['body'].get('data'):
            # Base64 decode the body
            body_data = payload['body']['data']
            body_bytes = base64.urlsafe_b64decode(body_data)
            return body_bytes.decode('utf-8')
        
        # If the message is multipart, recursively get the text parts
        if 'parts' in payload:
            text_parts = []
            for part in payload['parts']:
                # Prefer text/plain parts
                if part['mimeType'] == 'text/plain':
                    text_parts.append(self._get_message_body(part))
                # Fall back to text/html if needed
                elif part['mimeType'] == 'text/html' and not text_parts:
                    text_parts.append(self._get_message_body(part))
                # Handle nested multipart
                elif 'parts' in part:
                    text_parts.append(self._get_message_body(part))
            
            return '\n'.join(text_parts)
        
        return ""
    
    def send_message(self, to: str, subject: str, body: str) -> Optional[str]:
        """Send a new email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return None
        
        try:
            # Create a message
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send the message
            sent_message = self.service.users().messages().send(
                userId='me', body={'raw': raw_message}).execute()
            
            logger.info(f"Message sent successfully with ID: {sent_message['id']}")
            return sent_message['id']
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def reply_to_message(self, message_id: str, body: str) -> Optional[str]:
        """Reply to an existing email.
        
        Args:
            message_id: ID of the email to reply to
            body: Reply content
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return None
        
        try:
            # Get the original message to extract thread ID and subject
            original = self.service.users().messages().get(
                userId='me', id=message_id, format='metadata').execute()
            
            # Extract thread ID
            thread_id = original['threadId']
            
            # Extract headers from original message
            headers = {}
            for header in original['payload']['headers']:
                headers[header['name'].lower()] = header['value']
            
            # Create reply
            message = MIMEMultipart()
            message['to'] = headers.get('from', '')
            
            # Add Re: prefix if not already present
            subject = headers.get('subject', '')
            if not subject.startswith('Re:'):
                subject = f"Re: {subject}"
            message['subject'] = subject
            
            # Set In-Reply-To and References headers for proper threading
            message['In-Reply-To'] = headers.get('message-id', '')
            references = headers.get('references', '')
            if references:
                references += " "
            references += headers.get('message-id', '')
            message['References'] = references
            
            # Add the reply text
            message.attach(MIMEText(body, 'plain'))
            
            # Convert to base64 encoded string
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()).decode('utf-8')
            
            # Send the message via the Gmail API
            sent_message = self.service.users().messages().send(
                userId='me', 
                body={'raw': raw_message, 'threadId': thread_id}
            ).execute()
            
            logger.info(f"Reply sent with message ID: {sent_message['id']}")
            return sent_message['id']
        
        except Exception as e:
            logger.error(f"Error replying to message {message_id}: {e}")
            return None
            
    def delete_message(self, message_id: str) -> bool:
        """Delete a specific email message.
        
        Args:
            message_id: ID of the email to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return False
            
        try:
            # Use the trash method to move the message to trash
            self.service.users().messages().trash(
                userId='me', id=message_id).execute()
            logger.info(f"Successfully deleted message ID: {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
            return False
            
    def batch_delete_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple email messages in a batch operation.
        
        Args:
            message_ids: List of message IDs to delete
            
        Returns:
            Dictionary with counts of successful and failed deletions
        """
        if not self.authenticated:
            logger.error("Not authenticated with Gmail API")
            return {"success": 0, "failed": len(message_ids), "failed_ids": message_ids}
            
        results = {"success": 0, "failed": 0, "failed_ids": []}
        
        for message_id in message_ids:
            try:
                self.service.users().messages().trash(
                    userId='me', id=message_id).execute()
                results["success"] += 1
                logger.info(f"Successfully deleted message ID: {message_id}")
            except Exception as e:
                results["failed"] += 1
                results["failed_ids"].append(message_id)
                logger.error(f"Error deleting message {message_id}: {e}")
                
        return results 