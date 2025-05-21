import unittest
from unittest.mock import MagicMock, patch, ANY
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText

# Assuming src.drafts is importable, adjust path if necessary
# This might need adjustment based on how Python path is configured in the test environment.
# For example, if 'src' is a top-level directory and tests are run from the project root.
from src import drafts

class TestCreateMimeMessage(unittest.TestCase):
    def test_create_mime_message_structure(self):
        to = "test@example.com"
        subject = "Test Subject"
        body = "This is the body of the email."
        
        result_b64 = drafts._create_mime_message(to, subject, body)
        
        # Decode the base64url string
        decoded_bytes = base64.urlsafe_b64decode(result_b64)
        decoded_string = decoded_bytes.decode('utf-8')
        
        self.assertIn(f"To: {to}", decoded_string)
        self.assertIn(f"Subject: {subject}", decoded_string)
        self.assertIn(f"\n\n{body}", decoded_string) # MIMEText adds extra newlines
        self.assertTrue(decoded_string.startswith("Content-Type: text/plain; charset=\"utf-8\""))

class TestListDrafts(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    def test_list_drafts_success_multiple_drafts(self):
        max_results = 5
        draft_summaries = [{'id': 'draft1'}, {'id': 'draft2'}]
        draft_details = [
            {'id': 'draft1', 'message': {'snippet': 'Snippet 1'}},
            {'id': 'draft2', 'message': {'snippet': 'Snippet 2'}}
        ]
        
        self.mock_service.users().drafts().list().execute.return_value = {'drafts': draft_summaries, 'resultSizeEstimate': 2}
        # Mock the subsequent get calls for each draft
        self.mock_service.users().drafts().get().execute.side_effect = draft_details
        
        result = drafts.list_drafts(self.mock_service, max_results=max_results)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 'draft1')
        self.assertEqual(result[1]['id'], 'draft2')
        self.mock_service.users().drafts().list.assert_called_once_with(userId='me', maxResults=max_results)
        self.mock_service.users().drafts().get.assert_any_call(userId='me', id='draft1', format='full')
        self.mock_service.users().drafts().get.assert_any_call(userId='me', id='draft2', format='full')
        self.mock_logger.info.assert_called_with("Successfully retrieved 2 drafts.")

    def test_list_drafts_no_drafts_found(self):
        self.mock_service.users().drafts().list().execute.return_value = {} # No 'drafts' key
        
        result = drafts.list_drafts(self.mock_service)
        
        self.assertEqual(result, [])
        self.mock_logger.info.assert_called_with("No drafts found.")

    def test_list_drafts_api_error_on_list(self):
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        self.mock_service.users().drafts().list().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'API error'
        )
        
        result = drafts.list_drafts(self.mock_service)
        
        self.assertEqual(result, [])
        self.mock_logger.error.assert_called_with(f"An API error occurred while listing drafts: {ANY}")

    def test_list_drafts_api_error_on_get_individual_draft(self):
        draft_summaries = [{'id': 'draft1'}, {'id': 'draft2_error'}]
        draft1_details = {'id': 'draft1', 'message': {'snippet': 'Snippet 1'}}
        
        self.mock_service.users().drafts().list().execute.return_value = {'drafts': draft_summaries}
        
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        
        # First get succeeds, second get fails
        self.mock_service.users().drafts().get().execute.side_effect = [
            draft1_details,
            HttpError(resp=mock_http_error_response, content=b'API error on get')
        ]
        
        result = drafts.list_drafts(self.mock_service)
        
        self.assertEqual(len(result), 1) # Only the first draft should be returned
        self.assertEqual(result[0]['id'], 'draft1')
        self.mock_logger.error.assert_called_with(f"An API error occurred while fetching draft draft2_error: {ANY}")
        self.mock_logger.info.assert_called_with("Successfully retrieved 1 drafts.")


class TestGetDraft(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    def test_get_draft_success(self):
        draft_id = "draft123"
        expected_draft_data = {'id': draft_id, 'message': {'snippet': 'Test snippet'}}
        self.mock_service.users().drafts().get().execute.return_value = expected_draft_data
        
        result = drafts.get_draft(self.mock_service, draft_id)
        
        self.assertEqual(result, expected_draft_data)
        self.mock_service.users().drafts().get.assert_called_once_with(userId='me', id=draft_id, format='full')
        self.mock_logger.info.assert_called_with(f"Successfully retrieved draft with ID: {draft_id}")

    def test_get_draft_not_found(self):
        draft_id = "draft_not_found"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 404
        self.mock_service.users().drafts().get().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Draft not found'
        )
        
        result = drafts.get_draft(self.mock_service, draft_id)
        
        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_with(f"Draft with ID: {draft_id} not found.")

    def test_get_draft_other_api_error(self):
        draft_id = "draft_other_error"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500 # Internal server error
        self.mock_service.users().drafts().get().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Server error'
        )
        
        result = drafts.get_draft(self.mock_service, draft_id)
        
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_with(f"An API error occurred while retrieving draft {draft_id}: {ANY}")

class TestCreateDraft(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    @patch('src.drafts._create_mime_message')
    def test_create_draft_success(self, mock_create_mime_message):
        to, subject, body = "recipient@example.com", "Hello", "Draft body"
        mock_raw_message = "base64url_encoded_message_string"
        mock_create_mime_message.return_value = mock_raw_message
        
        expected_draft_response = {'id': 'new_draft_id', 'message': {'raw': mock_raw_message}}
        self.mock_service.users().drafts().create().execute.return_value = expected_draft_response
        
        result = drafts.create_draft(self.mock_service, to, subject, body)
        
        self.assertEqual(result, expected_draft_response)
        mock_create_mime_message.assert_called_once_with(to, subject, body)
        self.mock_service.users().drafts().create.assert_called_once_with(
            userId='me', body={'message': {'raw': mock_raw_message}}
        )
        self.mock_logger.info.assert_called_with(f"Successfully created draft with ID: new_draft_id")

    @patch('src.drafts._create_mime_message')
    def test_create_draft_api_error(self, mock_create_mime_message):
        to, subject, body = "recipient@example.com", "Hello", "Draft body"
        mock_raw_message = "base64url_encoded_message_string"
        mock_create_mime_message.return_value = mock_raw_message

        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        self.mock_service.users().drafts().create().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'API error'
        )
        
        result = drafts.create_draft(self.mock_service, to, subject, body)
        
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_with(f"An API error occurred while creating draft: {ANY}")

class TestUpdateDraft(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    @patch('src.drafts._create_mime_message')
    def test_update_draft_success(self, mock_create_mime_message):
        draft_id, to, subject, body = "existing_draft_id", "new_recipient@example.com", "Updated Subject", "Updated body"
        mock_raw_message = "base64url_encoded_updated_message"
        mock_create_mime_message.return_value = mock_raw_message
        
        expected_draft_response = {'id': draft_id, 'message': {'raw': mock_raw_message}}
        self.mock_service.users().drafts().update().execute.return_value = expected_draft_response
        
        result = drafts.update_draft(self.mock_service, draft_id, to, subject, body)
        
        self.assertEqual(result, expected_draft_response)
        mock_create_mime_message.assert_called_once_with(to, subject, body)
        self.mock_service.users().drafts().update.assert_called_once_with(
            userId='me', id=draft_id, body={'message': {'raw': mock_raw_message}}
        )
        self.mock_logger.info.assert_called_with(f"Successfully updated draft with ID: {draft_id}")

    @patch('src.drafts._create_mime_message')
    def test_update_draft_not_found(self, mock_create_mime_message):
        draft_id, to, subject, body = "draft_not_found_id", "new_recipient@example.com", "Updated Subject", "Updated body"
        mock_raw_message = "base64url_encoded_updated_message"
        mock_create_mime_message.return_value = mock_raw_message

        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 404
        self.mock_service.users().drafts().update().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Draft not found'
        )
        
        result = drafts.update_draft(self.mock_service, draft_id, to, subject, body)
        
        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_with(f"Draft with ID: {draft_id} not found for update.")

    @patch('src.drafts._create_mime_message')
    def test_update_draft_other_api_error(self, mock_create_mime_message):
        draft_id, to, subject, body = "draft_error_id", "new_recipient@example.com", "Updated Subject", "Updated body"
        mock_raw_message = "base64url_encoded_updated_message"
        mock_create_mime_message.return_value = mock_raw_message
        
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        self.mock_service.users().drafts().update().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Server error'
        )
        
        result = drafts.update_draft(self.mock_service, draft_id, to, subject, body)
        
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_with(f"An API error occurred while updating draft {draft_id}: {ANY}")

class TestDeleteDraft(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    def test_delete_draft_success(self):
        draft_id = "draft_to_delete"
        # delete().execute() returns None on success for Gmail API
        self.mock_service.users().drafts().delete().execute.return_value = None 
        
        result = drafts.delete_draft(self.mock_service, draft_id)
        
        self.assertTrue(result)
        self.mock_service.users().drafts().delete.assert_called_once_with(userId='me', id=draft_id)
        self.mock_logger.info.assert_called_with(f"Successfully deleted draft with ID: {draft_id}")

    def test_delete_draft_not_found(self):
        draft_id = "draft_not_found_for_delete"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 404
        self.mock_service.users().drafts().delete().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Draft not found'
        )
        
        result = drafts.delete_draft(self.mock_service, draft_id)
        
        self.assertFalse(result)
        self.mock_logger.warning.assert_called_with(f"Draft with ID: {draft_id} not found for deletion.")

    def test_delete_draft_other_api_error(self):
        draft_id = "draft_delete_error_id"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        self.mock_service.users().drafts().delete().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Server error'
        )
        
        result = drafts.delete_draft(self.mock_service, draft_id)
        
        self.assertFalse(result)
        self.mock_logger.error.assert_called_with(f"An API error occurred while deleting draft {draft_id}: {ANY}")

class TestSendDraft(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.logger_patch = patch('src.drafts.logger')
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.logger_patch.stop()

    def test_send_draft_success(self):
        draft_id = "draft_to_send"
        expected_sent_message = {'id': 'sent_message_id', 'labelIds': ['SENT']}
        self.mock_service.users().drafts().send().execute.return_value = expected_sent_message
        
        result = drafts.send_draft(self.mock_service, draft_id)
        
        self.assertEqual(result, expected_sent_message)
        self.mock_service.users().drafts().send.assert_called_once_with(
            userId='me', body={'id': draft_id}
        )
        self.mock_logger.info.assert_called_with(f"Successfully sent draft with ID: {draft_id}. New message ID: sent_message_id")

    def test_send_draft_not_found(self):
        draft_id = "draft_not_found_for_send"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 404
        self.mock_service.users().drafts().send().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Draft not found'
        )
        
        result = drafts.send_draft(self.mock_service, draft_id)
        
        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_with(f"Draft with ID: {draft_id} not found for sending.")

    def test_send_draft_other_api_error(self):
        draft_id = "draft_send_error_id"
        mock_http_error_response = MagicMock()
        mock_http_error_response.status = 500
        self.mock_service.users().drafts().send().execute.side_effect = HttpError(
            resp=mock_http_error_response, content=b'Server error'
        )
        
        result = drafts.send_draft(self.mock_service, draft_id)
        
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_with(f"An API error occurred while sending draft {draft_id}: {ANY}")

if __name__ == '__main__':
    unittest.main()
