"""
Gmail Message Management Module
"""

import base64
import logging
from typing import Dict, List, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.discovery import Resource # For type hinting the service object
import googleapiclient.errors

logger = logging.getLogger(__name__)

def _get_message_body(payload: Dict[str, Any]) -> str:
    """Extract the message body from the payload (helper function).

    Args:
        payload: Message payload from Gmail API

    Returns:
        Decoded message body as text
    """
    # Handle base64 encoded body data
    if 'body' in payload and payload['body'].get('data'):
        body_data = payload['body']['data']
        # Pad the base64 string if necessary
        missing_padding = len(body_data) % 4
        if missing_padding:
            body_data += '=' * (4 - missing_padding)
        try:
            body_bytes = base64.urlsafe_b64decode(body_data)
            # Try decoding with utf-8 first, fallback to common encodings if needed
            try:
                return body_bytes.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning("Failed to decode body with utf-8, trying latin-1")
                try:
                    return body_bytes.decode('latin-1')
                except UnicodeDecodeError:
                     logger.warning("Failed to decode body with latin-1, trying iso-8859-1")
                     return body_bytes.decode('iso-8859-1', errors='replace') # Replace errors as last resort
        except Exception as decode_error:
             logger.error(f"Error decoding base64 body data: {decode_error}")
             return "[Decoding Error]" # Return placeholder on error

    # Handle multipart messages
    if 'parts' in payload:
        text_parts = []
        html_parts = []
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            if mime_type == 'text/plain':
                part_body = _get_message_body(part)
                if part_body: text_parts.append(part_body)
            elif mime_type == 'text/html':
                 part_body = _get_message_body(part)
                 if part_body: html_parts.append(part_body)
            # Handle nested multipart (e.g., multipart/alternative)
            elif mime_type.startswith('multipart/'):
                nested_body = _get_message_body(part) # Recursive call
                if nested_body: text_parts.append(nested_body) # Add whatever is found inside

        # Prefer plain text, fallback to HTML, then join whatever was found
        if text_parts:
            return '\n---\n'.join(text_parts)
        elif html_parts:
             # TODO: Consider adding HTML parsing/stripping library like BeautifulSoup
             logger.debug("Returning HTML body as plain text was not available.")
             return '\n---\n'.join(html_parts)

    return "" # No readable body found

def list_messages(service: Resource, max_results: int = 10, query: str = "") -> List[Dict[str, Any]]:
    """List messages from Gmail.

    Args:
        service: Authorized Google API service instance.
        max_results: Maximum number of messages to return
        query: Gmail search query (e.g., "is:unread", "from:example@gmail.com")

    Returns:
        List of message dictionaries with id, snippet, headers, etc. or empty list on error.
    """
    try:
        # Get list of message IDs matching the query
        results = service.users().messages().list(
            userId='me', maxResults=max_results, q=query).execute()
        messages_summary = results.get('messages', [])

        if not messages_summary:
            logger.info(f"No messages found for query: '{query}'")
            return []

        detailed_messages = []
        # Fetch details for each message ID found
        # Consider using batch requests for larger max_results if performance becomes an issue
        for message_summary in messages_summary:
            try:
                msg = service.users().messages().get(
                    userId='me', id=message_summary['id'], format='metadata' # Fetch metadata only for listing
                ).execute()

                # Extract headers
                headers = {}
                if 'payload' in msg and 'headers' in msg['payload']:
                    for header in msg['payload']['headers']:
                        headers[header['name'].lower()] = header['value']

                # Create a simplified message object for the list
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

            except googleapiclient.errors.HttpError as e:
                 logger.error(f"Error fetching details for message {message_summary['id']}: {e}")
                 # Skip this message and continue with others
            except Exception as e:
                 logger.error(f"Unexpected error fetching details for message {message_summary['id']}: {e}")
                 # Skip this message

        logger.info(f"Successfully listed {len(detailed_messages)} messages for query: '{query}'")
        return detailed_messages

    except Exception as e:
        logger.error(f"Error listing messages: {e}")
        return []

def get_message(service: Resource, message_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific message with its full content.

    Args:
        service: Authorized Google API service instance.
        message_id: The ID of the message to retrieve

    Returns:
        Message dictionary with full content or None if not found or on error.
    """
    try:
        # Get the full message content
        msg = service.users().messages().get(
            userId='me', id=message_id, format='full').execute() # format='full' gets payload with body

        # Extract headers
        headers = {}
        if 'payload' in msg and 'headers' in msg['payload']:
             for header in msg['payload']['headers']:
                 headers[header['name'].lower()] = header['value']

        # Extract body content using the helper function
        body = _get_message_body(msg['payload'])

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
            'body': body,
            'snippet': msg.get('snippet', ''), # Include snippet too
            'historyId': msg.get('historyId', ''),
            'internalDate': msg.get('internalDate', '') # Unix timestamp ms
        }
        logger.info(f"Successfully retrieved full message {message_id}")
        return detailed_message

    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"Message with ID {message_id} not found.")
        else:
            logger.error(f"Error getting message {message_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting message {message_id}: {e}")
        return None

def send_message(service: Resource, to: str, subject: str, body: str) -> Optional[str]:
    """Send a new email.

    Args:
        service: Authorized Google API service instance.
        to: Recipient email address
        subject: Email subject
        body: Email body content (plain text)

    Returns:
        Message ID if successful, None otherwise
    """
    try:
        # Create a MIME message object
        message = MIMEMultipart() # Use multipart in case of future attachment needs
        message['to'] = to
        message['subject'] = subject

        # Attach the body as plain text
        message.attach(MIMEText(body, 'plain'))

        # Encode the message for the API
        raw_message_bytes = message.as_bytes()
        raw_message = base64.urlsafe_b64encode(raw_message_bytes).decode('utf-8')

        # Prepare the request body
        message_body = {'raw': raw_message}

        # Send the message
        sent_message = service.users().messages().send(
            userId='me', body=message_body).execute()

        logger.info(f"Message sent successfully to {to} with ID: {sent_message['id']}")
        return sent_message['id']

    except googleapiclient.errors.HttpError as e:
        logger.error(f"HTTP error sending message to {to}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error sending message to {to}: {e}")
        return None

def reply_to_message(service: Resource, message_id: str, body: str) -> Optional[str]:
    """Reply to an existing email.

    Args:
        service: Authorized Google API service instance.
        message_id: ID of the email to reply to
        body: Reply content (plain text)

    Returns:
        Message ID of the reply if successful, None otherwise
    """
    try:
        # Get the original message metadata to extract necessary headers and thread ID
        original = service.users().messages().get(
            userId='me', id=message_id, format='metadata' # Only need headers and threadId
        ).execute()

        thread_id = original['threadId']

        # Extract essential headers from the original message
        headers = {}
        if 'payload' in original and 'headers' in original['payload']:
            for header in original['payload']['headers']:
                 # Normalize header names to lowercase for reliable access
                 headers[header['name'].lower()] = header['value']

        original_subject = headers.get('subject', '')
        original_from = headers.get('from', '')
        original_to = headers.get('to', '')
        original_cc = headers.get('cc')
        original_message_id_header = headers.get('message-id') # Usually includes < >
        original_references_header = headers.get('references')

        # Determine recipient(s) for the reply
        reply_to = headers.get('reply-to', original_from) # Prefer Reply-To if present

        # Create the reply MIME message
        message = MIMEMultipart()
        message['to'] = reply_to
        # Optionally add original recipients (To, CC) to CC if desired (common practice)
        # For simplicity, just replying to the sender/Reply-To address here.

        # Construct the subject with "Re:" prefix if not already present
        if original_subject.lower().startswith('re:'):
            subject = original_subject
        else:
            subject = f"Re: {original_subject}"
        message['subject'] = subject

        # Set In-Reply-To and References headers for proper email threading
        if original_message_id_header:
            message['In-Reply-To'] = original_message_id_header
            references = original_references_header if original_references_header else ''
            if original_message_id_header not in references: # Avoid duplication
                 if references:
                     references += " " # Add space separator
                 references += original_message_id_header
            message['References'] = references
        else:
             logger.warning(f"Original message {message_id} missing 'Message-ID' header. Threading may be affected.")


        # Attach the reply body
        message.attach(MIMEText(body, 'plain'))

        # Encode the message
        raw_message_bytes = message.as_bytes()
        raw_message = base64.urlsafe_b64encode(raw_message_bytes).decode('utf-8')

        # Send the reply, ensuring it's part of the original thread
        reply_body = {'raw': raw_message, 'threadId': thread_id}
        sent_message = service.users().messages().send(
            userId='me', body=reply_body).execute()

        logger.info(f"Reply sent for message ID {message_id}. New message ID: {sent_message['id']}")
        return sent_message['id']

    except googleapiclient.errors.HttpError as e:
        logger.error(f"HTTP error replying to message {message_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error replying to message {message_id}: {e}")
        return None

def delete_message(service: Resource, message_id: str) -> bool:
    """Delete a specific email message (moves to trash).

    Args:
        service: Authorized Google API service instance.
        message_id: ID of the email to delete

    Returns:
        True if deletion (trashing) was successful, False otherwise
    """
    try:
        # Use the trash method to move the message to trash
        service.users().messages().trash(
            userId='me', id=message_id).execute()
        logger.info(f"Successfully moved message ID {message_id} to trash.")
        return True
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"Message ID {message_id} not found for deletion.")
        else:
            logger.error(f"Error deleting message {message_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting message {message_id}: {e}")
        return False

def batch_delete_messages(service: Resource, message_ids: List[str]) -> Dict[str, Any]:
    """Delete multiple email messages in a batch operation (moves to trash).

    Note: Gmail API's batch trash endpoint simplifies this.

    Args:
        service: Authorized Google API service instance.
        message_ids: List of message IDs to delete

    Returns:
        Dictionary with counts of successful and failed deletions, and list of failed IDs.
        Returns {"success": 0, "failed": len(message_ids), "failed_ids": message_ids} on initial API error.
    """
    if not message_ids:
        return {"success": 0, "failed": 0, "failed_ids": []}

    try:
        # Use the batchTrash method
        request_body = {'ids': message_ids}
        service.users().messages().batchTrash(userId='me', body=request_body).execute()
        # If batchTrash succeeds, the API doesn't return per-message status, it's all or nothing for the call itself.
        # Assume all succeeded if the call didn't raise an exception.
        logger.info(f"Successfully executed batch trash for {len(message_ids)} messages.")
        return {"success": len(message_ids), "failed": 0, "failed_ids": []}
    except googleapiclient.errors.HttpError as e:
         # Batch operations might return partial success/failure details in the error response,
         # but parsing that can be complex. For simplicity, treat API error as full failure.
         logger.error(f"Error during batch delete operation: {e}. Treating all as failed.")
         return {"success": 0, "failed": len(message_ids), "failed_ids": message_ids}
    except Exception as e:
         logger.error(f"Unexpected error during batch delete: {e}")
         return {"success": 0, "failed": len(message_ids), "failed_ids": message_ids}


def modify_message_labels(service: Resource, message_id: str,
                          add_label_ids: Optional[List[str]] = None,
                          remove_label_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Add or remove labels from a specific message.

    Args:
        service: Authorized Google API service instance.
        message_id: The ID of the message to modify.
        add_label_ids: List of label IDs to add.
        remove_label_ids: List of label IDs to remove.

    Returns:
        The updated message resource dictionary or None on error.
    """
    if not add_label_ids and not remove_label_ids:
         logger.warning("No labels provided to add or remove.")
         # To be consistent, perhaps fetch and return the current message state?
         # Or just return None as no modification was requested/performed.
         return None # Return None as no action taken

    modify_request = {
        # Ensure lists are provided even if None was passed
        'addLabelIds': add_label_ids if add_label_ids else [],
        'removeLabelIds': remove_label_ids if remove_label_ids else []
    }

    try:
        updated_message = service.users().messages().modify(
            userId='me', id=message_id, body=modify_request).execute()

        log_parts = []
        if add_label_ids:
            log_parts.append(f"added labels {add_label_ids}")
        if remove_label_ids:
            log_parts.append(f"removed labels {remove_label_ids}")
        logger.info(f"Successfully modified message {message_id}: {' and '.join(log_parts)}.")

        return updated_message
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
             logger.error(f"Message with ID {message_id} not found for label modification.")
        elif e.resp.status == 400: # Often indicates invalid label ID format
             logger.error(f"Bad request modifying labels for message {message_id} (check label IDs?): {e}")
        else:
             logger.error(f"Error modifying labels for message {message_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error modifying labels for message {message_id}: {e}")
        return None 