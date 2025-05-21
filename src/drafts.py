import base64
import logging
from typing import Optional, Dict, List, Any
from email.mime.text import MIMEText

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

def _create_mime_message(to: str, subject: str, body: str) -> str:
    """Creates a MIME message.

    Args:
        to: Email address of the recipient.
        subject: The subject of the email.
        body: The plain text body of the email.

    Returns:
        A base64url encoded email message.
    """
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    return base64.urlsafe_b64encode(message.as_bytes()).decode()

def list_drafts(service: Resource, max_results: int = 10) -> List[Dict[str, Any]]:
    """Lists draft emails.

    Args:
        service: The authenticated Gmail API service instance.
        max_results: Maximum number of drafts to return.

    Returns:
        A list of draft dictionaries.
    """
    drafts_list = []
    try:
        results = service.users().drafts().list(userId='me', maxResults=max_results).execute()
        draft_summaries = results.get('drafts', [])
        if not draft_summaries:
            logger.info("No drafts found.")
            return []

        for draft_summary in draft_summaries:
            try:
                draft = service.users().drafts().get(userId='me', id=draft_summary['id'], format='full').execute()
                drafts_list.append(draft)
            except HttpError as error:
                logger.error(f"An API error occurred while fetching draft {draft_summary['id']}: {error}")
                # Continue to fetch other drafts
        logger.info(f"Successfully retrieved {len(drafts_list)} drafts.")
        return drafts_list
    except HttpError as error:
        logger.error(f"An API error occurred while listing drafts: {error}")
        return []

def get_draft(service: Resource, draft_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific draft by its ID.

    Args:
        service: The authenticated Gmail API service instance.
        draft_id: The ID of the draft to retrieve.

    Returns:
        A dictionary containing the draft details or None if not found or on error.
    """
    try:
        draft = service.users().drafts().get(userId='me', id=draft_id, format='full').execute()
        logger.info(f"Successfully retrieved draft with ID: {draft_id}")
        return draft
    except HttpError as error:
        if error.resp.status == 404:
            logger.warning(f"Draft with ID: {draft_id} not found.")
        else:
            logger.error(f"An API error occurred while retrieving draft {draft_id}: {error}")
        return None

def create_draft(service: Resource, to: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
    """Creates a new draft email.

    Args:
        service: The authenticated Gmail API service instance.
        to: Email address of the recipient.
        subject: The subject of the email.
        body: The plain text body of the email.

    Returns:
        A dictionary representing the created draft or None on error.
    """
    try:
        raw_message = _create_mime_message(to, subject, body)
        message_body = {'message': {'raw': raw_message}}
        draft = service.users().drafts().create(userId='me', body=message_body).execute()
        logger.info(f"Successfully created draft with ID: {draft.get('id')}")
        return draft
    except HttpError as error:
        logger.error(f"An API error occurred while creating draft: {error}")
        return None

def update_draft(service: Resource, draft_id: str, to: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
    """Updates an existing draft.

    Args:
        service: The authenticated Gmail API service instance.
        draft_id: The ID of the draft to update.
        to: Email address of the recipient.
        subject: The subject of the email.
        body: The plain text body of the email.

    Returns:
        A dictionary representing the updated draft or None on error.
    """
    try:
        raw_message = _create_mime_message(to, subject, body)
        message_body = {'message': {'raw': raw_message}}
        # Note: The API for update requires the draft_id in the URL, not in the body.
        # The body for update is just the message.
        draft = service.users().drafts().update(userId='me', id=draft_id, body=message_body).execute()
        logger.info(f"Successfully updated draft with ID: {draft_id}")
        return draft
    except HttpError as error:
        if error.resp.status == 404:
            logger.warning(f"Draft with ID: {draft_id} not found for update.")
        else:
            logger.error(f"An API error occurred while updating draft {draft_id}: {error}")
        return None

def delete_draft(service: Resource, draft_id: str) -> bool:
    """Deletes a draft.

    Args:
        service: The authenticated Gmail API service instance.
        draft_id: The ID of the draft to delete.

    Returns:
        True on success, False on failure.
    """
    try:
        service.users().drafts().delete(userId='me', id=draft_id).execute()
        logger.info(f"Successfully deleted draft with ID: {draft_id}")
        return True
    except HttpError as error:
        if error.resp.status == 404:
            logger.warning(f"Draft with ID: {draft_id} not found for deletion.")
        else:
            logger.error(f"An API error occurred while deleting draft {draft_id}: {error}")
        return False

def send_draft(service: Resource, draft_id: str) -> Optional[Dict[str, Any]]:
    """Sends an existing draft.

    Args:
        service: The authenticated Gmail API service instance.
        draft_id: The ID of the draft to send.

    Returns:
        A dictionary representing the sent message or None on error.
    """
    try:
        # The body for send is {'id': draft_id}
        sent_message = service.users().drafts().send(userId='me', body={'id': draft_id}).execute()
        logger.info(f"Successfully sent draft with ID: {draft_id}. New message ID: {sent_message.get('id')}")
        return sent_message
    except HttpError as error:
        if error.resp.status == 404:
            logger.warning(f"Draft with ID: {draft_id} not found for sending.")
        else:
            logger.error(f"An API error occurred while sending draft {draft_id}: {error}")
        return None
