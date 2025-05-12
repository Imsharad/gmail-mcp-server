"""
Gmail API Client Facade

This module provides a simplified interface to interact with the Gmail API,
coordinating authentication and delegating actions to specific modules.
"""

import logging
from typing import Dict, List, Any, Optional

# Import the specific functions/modules needed
from googleapiclient.discovery import build, Resource
from .auth import authenticate_google_api # Use relative import
from . import messages # Import the whole module
from . import labels   # Import the whole module

# Set up logging
logger = logging.getLogger(__name__)

class GmailClient:
    """Acts as a client facade for interacting with the Gmail API.

    Handles authentication and delegates API calls to specialized modules.
    """

    def __init__(self, credentials_file: str, token_file: str):
        """Initialize the Gmail client and authenticate.

        Args:
            credentials_file: Path to the credentials.json file.
            token_file: Path to the token.json file for storing/retrieving user credentials.
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service: Optional[Resource] = None # Type hint for the service object
        self.authenticated = False
        self._authenticate()

    def _authenticate(self): # Changed from public authenticate to internal _authenticate
        """Authenticate with the Gmail API using the auth module."""
        creds = authenticate_google_api(self.credentials_file, self.token_file)

        if creds and creds.valid:
            try:
                # Build the Gmail API service using the obtained credentials
                self.service = build('gmail', 'v1', credentials=creds)
                self.authenticated = True
                logger.info("GmailClient: Successfully authenticated and built Gmail service.")
            except Exception as e:
                logger.error(f"GmailClient: Error building Gmail service after authentication: {e}")
                self.service = None
                self.authenticated = False
        else:
            logger.error("GmailClient: Authentication failed. Check auth logs for details.")
            self.service = None
            self.authenticated = False

    # --- Message Methods (Delegation) ---

    def list_messages(self, max_results: int = 10, query: str = "") -> List[Dict[str, Any]]:
        """List messages. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error("Not authenticated. Cannot list messages.")
            return []
        return messages.list_messages(self.service, max_results, query)

    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot get message {message_id}.")
            return None
        return messages.get_message(self.service, message_id)

    def send_message(self, to: str, subject: str, body: str) -> Optional[str]:
        """Send a new email. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot send message to {to}.")
            return None
        return messages.send_message(self.service, to, subject, body)

    def reply_to_message(self, message_id: str, body: str) -> Optional[str]:
        """Reply to an existing email. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot reply to message {message_id}.")
            return None
        return messages.reply_to_message(self.service, message_id, body)

    def delete_message(self, message_id: str) -> bool:
        """Delete a specific email message. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot delete message {message_id}.")
            return False
        return messages.delete_message(self.service, message_id)

    def batch_delete_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple email messages. Delegates to the messages module."""
        if not self.authenticated or not self.service:
            logger.error("Not authenticated. Cannot batch delete messages.")
            # Return structure consistent with the messages module on auth failure
            return {"success": 0, "failed": len(message_ids), "failed_ids": message_ids}
        return messages.batch_delete_messages(self.service, message_ids)

    def modify_message_labels(self, message_id: str,
                              add_label_ids: Optional[List[str]] = None,
                              remove_label_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Add or remove labels from a message. Delegates to the messages module."""
        if not self.authenticated or not self.service:
             logger.error(f"Not authenticated. Cannot modify labels for message {message_id}.")
             return None
        return messages.modify_message_labels(self.service, message_id, add_label_ids, remove_label_ids)

    # --- Label Methods (Delegation) ---

    def list_labels(self) -> List[Dict[str, Any]]:
        """List all labels. Delegates to the labels module."""
        if not self.authenticated or not self.service:
            logger.error("Not authenticated. Cannot list labels.")
            return []
        return labels.list_labels(self.service)

    def get_label(self, label_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific label. Delegates to the labels module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot get label {label_id}.")
            return None
        return labels.get_label(self.service, label_id)

    def create_label(self, name: str,
                       label_list_visibility: str = 'labelShow',
                       message_list_visibility: str = 'show') -> Optional[Dict[str, Any]]:
        """Create a new label. Delegates to the labels module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot create label '{name}'.")
            return None
        # Pass along optional visibility params
        return labels.create_label(self.service, name, label_list_visibility, message_list_visibility)

    def delete_label(self, label_id: str) -> bool:
        """Delete an existing label. Delegates to the labels module."""
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot delete label {label_id}.")
            return False
        return labels.delete_label(self.service, label_id) 