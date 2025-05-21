"""
Gmail API Client Facade

This module provides a simplified interface to interact with the Gmail API,
coordinating authentication and delegating actions to specific modules.
"""

import logging
import os # Added for path manipulation
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

    def send_message(self, to: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> Optional[str]:
        """Send a new email, optionally with attachments. Delegates to the messages module.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body content (plain text).
            attachments: Optional. A list of file paths for files to be attached.

        Returns:
            Message ID if successful, None otherwise.
        """
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot send message to {to}.")
            return None
        return messages.send_message(self.service, to, subject, body, attachments=attachments)

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

    def get_attachment(self, message_id: str, attachment_id: str, filename: str, download_path: Optional[str] = None) -> Optional[bytes]:
        """Fetches an attachment's data and optionally saves it to a file.

        Args:
            message_id: The ID of the message containing the attachment.
            attachment_id: The ID of the attachment to retrieve.
            filename: The filename for the attachment (used if saving to disk).
            download_path: Optional. If provided, the directory where the attachment
                           will be saved. The filename from the metadata is used.

        Returns:
            The attachment data as bytes if successful, None otherwise.
            If download_path is specified and saving is successful, it still returns
            the bytes of the attachment.
        """
        if not self.authenticated or not self.service:
            logger.error(f"Not authenticated. Cannot get attachment {attachment_id} from message {message_id}.")
            return None

        logger.info(f"Attempting to fetch attachment {attachment_id} for message {message_id}.")
        attachment_data = messages.get_attachment_data(self.service, message_id, attachment_id)

        if attachment_data is None:
            logger.error(f"Failed to retrieve attachment data for {attachment_id} from message {message_id}.")
            return None

        if download_path:
            if not filename: # Ensure filename is not empty or None
                logger.error(f"Filename is missing for attachment {attachment_id} in message {message_id}. Cannot save.")
                # Still return the data as it was fetched, but log error for saving.
                return attachment_data

            full_save_path = os.path.join(download_path, filename)
            try:
                # Ensure the download directory exists
                if not os.path.exists(download_path):
                    os.makedirs(download_path) # Create directory if it doesn't exist
                    logger.info(f"Created download directory: {download_path}")

                with open(full_save_path, 'wb') as f:
                    f.write(attachment_data)
                logger.info(f"Attachment {attachment_id} (filename: {filename}) saved successfully to {full_save_path}.")
            except IOError as e:
                logger.error(f"IOError saving attachment {filename} to {full_save_path}: {e}")
                # Decide if this should return None or the data.
                # For now, return data as it was successfully fetched, but saving failed.
                return attachment_data
            except Exception as e:
                logger.error(f"Unexpected error saving attachment {filename} to {full_save_path}: {e}")
                return attachment_data # Still return data if fetched

        return attachment_data