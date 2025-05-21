import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio # Required for running async functions

# The server module needs to be imported to be tested.
# This assumes 'src' is in Python's path or discoverable.
from src import server 

# Helper to run async test methods
def async_test(f):
    def wrapper(*args, **kwargs):
        asyncio.run(f(*args, **kwargs))
    return wrapper

class TestServerDraftTools(unittest.TestCase):

    def setUp(self):
        # Patch the gmail_client used by the server's tool functions
        self.gmail_client_patch = patch('src.server.gmail_client', new_callable=MagicMock)
        self.mock_gmail_client = self.gmail_client_patch.start()

        # Patch the logger used by the server's tool functions
        self.logger_patch = patch('src.server.logger', new_callable=MagicMock)
        self.mock_logger = self.logger_patch.start()

    def tearDown(self):
        self.gmail_client_patch.stop()
        self.logger_patch.stop()

    @async_test
    async def test_list_drafts_mcp_success(self):
        mock_draft_list = [
            {'id': 'draft1', 'message': {'payload': {'headers': [{'name': 'To', 'value': 'test1@example.com'}, {'name': 'Subject', 'value': 'Sub1'}]}, 'snippet': 'Snip1'}},
            {'id': 'draft2', 'message': {'payload': {'headers': [{'name': 'To', 'value': 'test2@example.com'}, {'name': 'Subject', 'value': 'Sub2'}]}, 'snippet': 'Snip2'}}
        ]
        self.mock_gmail_client.list_drafts.return_value = mock_draft_list
        
        result = await server.list_drafts(max_results=5)
        
        self.assertIn("Found 2 drafts:", result)
        self.assertIn("ID: draft1", result)
        self.assertIn("To: test1@example.com", result)
        self.assertIn("Subject: Sub1", result)
        self.assertIn("Snippet: Snip1", result)
        self.assertIn("ID: draft2", result)
        self.mock_gmail_client.list_drafts.assert_called_once_with(max_results=5)

    @async_test
    async def test_list_drafts_mcp_no_drafts(self):
        self.mock_gmail_client.list_drafts.return_value = []
        result = await server.list_drafts()
        self.assertEqual(result, "No drafts found.")

    @async_test
    async def test_list_drafts_mcp_exception(self):
        self.mock_gmail_client.list_drafts.side_effect = Exception("Gmail API Error")
        result = await server.list_drafts()
        self.assertIn("An error occurred while listing drafts: Gmail API Error", result)
        self.mock_logger.error.assert_called_with("Error in list_drafts tool: Gmail API Error")

    @async_test
    async def test_get_draft_mcp_success(self):
        draft_id = "d123"
        mock_draft_data = {
            'id': draft_id,
            'message': {
                'payload': {
                    'headers': [
                        {'name': 'From', 'value': 'me@example.com'},
                        {'name': 'To', 'value': 'you@example.com'},
                        {'name': 'Subject', 'value': 'Test Subject'}
                    ],
                    'parts': [{'mimeType': 'text/plain', 'body': {'data': 'SGVsbG8gV29ybGQ='}}], # "Hello World" b64
                },
                'snippet': 'Test snippet'
            }
        }
        self.mock_gmail_client.get_draft.return_value = mock_draft_data
        
        # Mock the service object on the client for body decoding (if that path is taken)
        # This part of get_draft in server.py was a bit complex, ensure it's handled
        # The current server.py get_draft tries to decode directly from parts
        
        result = await server.get_draft(draft_id)
        
        self.assertIn(f"Draft ID: {draft_id}", result)
        self.assertIn("From: me@example.com", result)
        self.assertIn("To: you@example.com", result)
        self.assertIn("Subject: Test Subject", result)
        self.assertIn("Body:\nHello World", result) # Check for decoded body
        self.mock_gmail_client.get_draft.assert_called_once_with(draft_id)

    @async_test
    async def test_get_draft_mcp_not_found(self):
        draft_id = "d_not_found"
        self.mock_gmail_client.get_draft.return_value = None
        result = await server.get_draft(draft_id)
        self.assertEqual(result, f"Draft with ID '{draft_id}' not found.")

    @async_test
    async def test_get_draft_mcp_exception(self):
        draft_id = "d_error"
        self.mock_gmail_client.get_draft.side_effect = Exception("Fetch Error")
        result = await server.get_draft(draft_id)
        self.assertIn(f"An error occurred while retrieving draft {draft_id}: Fetch Error", result)
        self.mock_logger.error.assert_called_with(f"Error in get_draft tool for ID {draft_id}: Fetch Error")


    @async_test
    async def test_create_draft_mcp_success(self):
        to, subject, body = "test@example.com", "My Subject", "My Body"
        self.mock_gmail_client.create_draft.return_value = {'id': 'newDraftId123'}
        
        result = await server.create_draft(to, subject, body)
        
        self.assertEqual(result, "Draft created successfully. ID: newDraftId123")
        self.mock_gmail_client.create_draft.assert_called_once_with(to, subject, body)

    @async_test
    async def test_create_draft_mcp_failure(self):
        to, subject, body = "test@example.com", "My Subject", "My Body"
        self.mock_gmail_client.create_draft.return_value = None # Simulate failure
        
        result = await server.create_draft(to, subject, body)
        
        self.assertEqual(result, "Failed to create draft. Please check the logs for details.")
        self.mock_logger.warning.assert_called_with(f"Failed to create draft. Gmail_client.create_draft returned: None")

    @async_test
    async def test_create_draft_mcp_validation_error_to(self):
        result = await server.create_draft(to="", subject="Subject", body="Body")
        self.assertEqual(result, "Recipient 'to' and 'subject' cannot be empty for creating a draft.")

    @async_test
    async def test_create_draft_mcp_validation_error_subject(self):
        result = await server.create_draft(to="test@example.com", subject="", body="Body")
        self.assertEqual(result, "Recipient 'to' and 'subject' cannot be empty for creating a draft.")

    @async_test
    async def test_create_draft_mcp_exception(self):
        to, subject, body = "test@example.com", "My Subject", "My Body"
        self.mock_gmail_client.create_draft.side_effect = Exception("Creation Error")
        result = await server.create_draft(to, subject, body)
        self.assertIn("An error occurred while creating the draft: Creation Error", result)
        self.mock_logger.error.assert_called_with("Error in create_draft tool: Creation Error")


    @async_test
    async def test_update_draft_mcp_success(self):
        draft_id, to, subject, body = "d1", "t@e.com", "S", "B"
        self.mock_gmail_client.update_draft.return_value = {'id': draft_id}
        result = await server.update_draft(draft_id, to, subject, body)
        self.assertEqual(result, f"Draft with ID '{draft_id}' updated successfully.")
        self.mock_gmail_client.update_draft.assert_called_once_with(draft_id, to, subject, body)

    @async_test
    async def test_update_draft_mcp_not_found_or_fail(self):
        draft_id, to, subject, body = "d1", "t@e.com", "S", "B"
        self.mock_gmail_client.update_draft.return_value = None
        result = await server.update_draft(draft_id, to, subject, body)
        self.assertEqual(result, f"Failed to update draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs.")
        self.mock_logger.warning.assert_called_with(f"Failed to update draft {draft_id}. Gmail_client.update_draft returned: None")

    @async_test
    async def test_update_draft_mcp_validation_error(self):
        result = await server.update_draft(draft_id="", to="t@e.com", subject="S", body="B")
        self.assertEqual(result, "Draft ID, recipient 'to', and 'subject' cannot be empty for updating a draft.")


    @async_test
    async def test_delete_draft_mcp_success(self):
        draft_id = "d1_to_delete"
        self.mock_gmail_client.delete_draft.return_value = True
        result = await server.delete_draft(draft_id)
        self.assertEqual(result, f"Draft with ID '{draft_id}' deleted successfully.")
        self.mock_gmail_client.delete_draft.assert_called_once_with(draft_id)

    @async_test
    async def test_delete_draft_mcp_failure_or_not_found(self):
        draft_id = "d1_fail_delete"
        self.mock_gmail_client.delete_draft.return_value = False
        result = await server.delete_draft(draft_id)
        self.assertEqual(result, f"Failed to delete draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs.")

    @async_test
    async def test_delete_draft_mcp_validation_error(self):
        result = await server.delete_draft(draft_id="")
        self.assertEqual(result, "Draft ID cannot be empty.")


    @async_test
    async def test_send_draft_mcp_success(self):
        draft_id = "d1_to_send"
        self.mock_gmail_client.send_draft.return_value = {'id': 'sentMsgId1'}
        result = await server.send_draft(draft_id)
        self.assertEqual(result, f"Draft with ID '{draft_id}' sent successfully. Message ID: sentMsgId1")
        self.mock_gmail_client.send_draft.assert_called_once_with(draft_id)

    @async_test
    async def test_send_draft_mcp_failure_or_not_found(self):
        draft_id = "d1_fail_send"
        self.mock_gmail_client.send_draft.return_value = None
        result = await server.send_draft(draft_id)
        self.assertEqual(result, f"Failed to send draft with ID '{draft_id}'. It might not exist or an error occurred. Check logs.")
    
    @async_test
    async def test_send_draft_mcp_validation_error(self):
        result = await server.send_draft(draft_id="")
        self.assertEqual(result, "Draft ID cannot be empty.")


if __name__ == '__main__':
    unittest.main()
