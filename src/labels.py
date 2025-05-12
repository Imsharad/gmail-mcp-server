"""
Gmail Label Management Module
"""

import logging
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import Resource # For type hinting the service object
import googleapiclient.errors

logger = logging.getLogger(__name__)

def list_labels(service: Resource) -> List[Dict[str, Any]]:
    """List all labels in the user\'s account.

    Args:
        service: Authorized Google API service instance.

    Returns:
        List of label dictionaries or empty list on error.
    """
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        logger.info(f"Retrieved {len(labels)} labels.")
        return labels
    except Exception as e:
        logger.error(f"Error listing labels: {e}")
        return []

def get_label(service: Resource, label_id: str) -> Optional[Dict[str, Any]]:
    """Get details for a specific label.

    Args:
        service: Authorized Google API service instance.
        label_id: The ID of the label to retrieve (e.g., \'Label_123\').

    Returns:
        Label dictionary or None if not found or on error.
    """
    try:
        label = service.users().labels().get(userId='me', id=label_id).execute()
        logger.info(f"Retrieved details for label ID: {label_id}")
        return label
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"Label with ID {label_id} not found.")
        else:
            logger.error(f"Error getting label {label_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting label {label_id}: {e}")
        return None

def create_label(service: Resource, name: str,
                   label_list_visibility: str = 'labelShow',
                   message_list_visibility: str = 'show') -> Optional[Dict[str, Any]]:
    """Create a new label.

    Args:
        service: Authorized Google API service instance.
        name: The display name of the new label.
        label_list_visibility: Visibility in the label list ('labelShow', 'labelShowIfUnread', 'labelHide'). Default is 'labelShow'.
        message_list_visibility: Visibility in message list ('show', 'hide'). Default is 'show'.

    Returns:
        The created label dictionary or None on error.
    """
    label_body = {
        'name': name,
        'labelListVisibility': label_list_visibility,
        'messageListVisibility': message_list_visibility
    }

    try:
        created_label = service.users().labels().create(userId='me', body=label_body).execute()
        logger.info(f"Successfully created label \'{name}\' with ID: {created_label['id']}")
        return created_label
    except googleapiclient.errors.HttpError as e:
         # Handle potential conflict (label name already exists)
        if e.resp.status == 409:
             logger.warning(f"Label with name \'{name}\' might already exist.")
             # Optionally, try to find the existing label by name here if needed
             # For now, just return None as the creation itself failed.
        else:
            logger.error(f"Error creating label \'{name}\': {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating label \'{name}\': {e}")
        return None

def delete_label(service: Resource, label_id: str) -> bool:
    """Delete an existing label.

    Args:
        service: Authorized Google API service instance.
        label_id: The ID of the label to delete (e.g., \'Label_123\').

    Returns:
        True if deletion was successful, False otherwise.
    """
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        logger.info(f"Successfully deleted label ID: {label_id}")
        return True
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"Label with ID {label_id} not found for deletion.")
        else:
             logger.error(f"Error deleting label {label_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting label {label_id}: {e}")
        return False

# Note: modify_message_labels logically belongs more with messages,
# as it modifies a message based on labels. It will be moved to messages.py 