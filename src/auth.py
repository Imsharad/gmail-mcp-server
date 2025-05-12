"""
Authentication Module for Gmail API
"""

import os
import json
import logging
import google.auth.exceptions
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from typing import Optional

logger = logging.getLogger(__name__)

# Gmail API scopes - Keep consistent with other modules if needed elsewhere
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels' # Added for label management
]

def authenticate_google_api(credentials_file: str, token_file: str) -> Optional[Credentials]:
    """Handles the OAuth2 flow and returns valid credentials.

    Args:
        credentials_file: Path to the credentials.json file.
        token_file: Path to the token.json file for storing/retrieving user credentials.

    Returns:
        Valid Google OAuth2 Credentials object or None if authentication fails.
    """
    creds = None

    # Check if token file exists and load credentials
    if os.path.exists(token_file):
        try:
            # Ensure SCOPES matches the ones used to generate the token
            creds = Credentials.from_authorized_user_info(
                json.loads(open(token_file).read()), SCOPES)
            logger.debug("Loaded credentials from token file.")
        except ValueError as e:
             logger.warning(f"Error loading token file (likely scope mismatch or invalid format): {e}. Will attempt re-authentication.")
             creds = None # Force re-authentication
        except Exception as e:
            logger.error(f"Unexpected error loading credentials from token file: {e}")
            creds = None # Safer to force re-auth

    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Credentials expired, attempting refresh.")
            try:
                creds.refresh(Request())
                logger.info("Credentials refreshed successfully.")
                # Save the refreshed credentials
                try:
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.debug("Saved refreshed credentials to token file.")
                except Exception as e:
                    logger.error(f"Error saving refreshed credentials to token file: {e}")
            except google.auth.exceptions.RefreshError as e:
                logger.error(f"Error refreshing credentials: {e}. Need to re-authenticate.")
                # If refresh fails, potentially delete the token file or prompt user
                try:
                    os.remove(token_file)
                    logger.info(f"Removed invalid token file: {token_file}")
                except OSError as rm_err:
                     logger.error(f"Error removing invalid token file {token_file}: {rm_err}")
                creds = None # Force re-authentication flow
            except Exception as e:
                 logger.error(f"Unexpected error during credential refresh: {e}")
                 creds = None # Force re-authentication flow

        # If still no valid credentials, need to run the authentication flow
        if not creds or not creds.valid:
            logger.info("No valid credentials found, starting authentication flow.")
            if not os.path.exists(credentials_file):
                logger.error(f"Credentials file '{credentials_file}' not found. Cannot authenticate.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES)
                # TODO: Consider how to handle the run_local_server part in a non-interactive server environment if needed.
                # For now, assumes local execution context where browser can be opened.
                creds = flow.run_local_server(port=0)
                logger.info("Authentication flow completed successfully.")
                # Save the new credentials for the next run
                try:
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info(f"Saved new credentials to token file: {token_file}")
                except Exception as e:
                    logger.error(f"Error saving new credentials to token file: {e}")
            except FileNotFoundError:
                 logger.error(f"Credentials secrets file not found at {credentials_file}")
                 return None
            except Exception as e:
                logger.error(f"Error during authentication flow: {e}")
                return None # Authentication failed

    # At this point, creds should be valid
    if creds and creds.valid:
         logger.info("Successfully obtained valid Google API credentials.")
         return creds
    else:
         logger.error("Failed to obtain valid Google API credentials after all attempts.")
         return None 