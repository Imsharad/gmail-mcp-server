import unittest
from unittest.mock import patch, mock_open, MagicMock, ANY
import base64
import os
import mimetypes
from email import message_from_bytes

# Modules to test
from src import messages
from src.gmail_api import GmailClient
from googleapiclient.errors import HttpError


class TestAttachmentHandling(unittest.TestCase):
    @patch('src.gmail_api.GmailClient.__init__', return_value=None) # Patch __init__ here
    def setUp(self, mock_gmail_client_init):
        """Set up basic mocks or configurations for each test."""
        # The GmailClient.__init__ is now patched, so we don't need
        # dummy file paths here. We can create an instance and set service/authenticated state manually.
        self.mock_client = GmailClient(credentials_file="", token_file="") # Pass dummy paths, won't be used due to patch
        self.mock_client.service = MagicMock() # Set the mocked service directly
        self.mock_client.authenticated = True # Assume authenticated for client tests

        self.mock_service = self.mock_client.service # Keep this for tests that directly use service mock

        # Create mocks for nested calls where needed
        self.mock_users = MagicMock()
        self.mock_messages = MagicMock()
        self.mock_attachments = MagicMock()
        self.mock_get_execute = MagicMock()

        self.mock_service.users.return_value = self.mock_users
        self.mock_users.messages.return_value = self.mock_messages
        self.mock_messages.attachments.return_value = self.mock_attachments
        self.mock_attachments.get.return_value = self.mock_get_execute

        self.logger_patch = patch('src.messages.logger')
        self.mock_logger = self.logger_patch.start()

        # Patch os.path.exists for tests that call get_attachment (in GmailClient)
        self.patch_os_path_exists = patch('src.gmail_api.os.path.exists')
        self.mock_os_path_exists = self.patch_os_path_exists.start()

        self.patch_os_makedirs = patch('src.gmail_api.os.makedirs')
        self.mock_os_makedirs = self.patch_os_makedirs.start()

        self.patch_builtin_open = patch('builtins.open', new_callable=mock_open)
        self.mock_builtin_open = self.patch_builtin_open.start()

    # --- Tests for src.messages._extract_attachment_info ---
    def test_extract_attachment_info_direct_filename(self):
        part = {
            'partId': '1',
            'mimeType': 'image/jpeg',
            'filename': 'test.jpg',
            'body': {'attachmentId': 'attach-id-1', 'size': 1024}
        }
        expected_info = {
            'filename': 'test.jpg',
            'mimeType': 'image/jpeg',
            'size': 1024,
            'attachmentId': 'attach-id-1',
            'partId': '1'
        }
        self.assertEqual(messages._extract_attachment_info(part), expected_info)

    def test_extract_attachment_info_content_disposition(self):
        part = {
            'partId': '2',
            'mimeType': 'application/pdf',
            'headers': [{'name': 'Content-Disposition', 'value': 'attachment; filename="document.pdf"'}],
            'body': {'attachmentId': 'attach-id-2', 'size': 2048}
        }
        expected_info = {
            'filename': 'document.pdf',
            'mimeType': 'application/pdf',
            'size': 2048,
            'attachmentId': 'attach-id-2',
            'partId': '2'
        }
        self.assertEqual(messages._extract_attachment_info(part), expected_info)

    def test_extract_attachment_info_no_filename(self):
        part = {
            'partId': '3',
            'mimeType': 'text/plain', # Not typically an attachment without a filename
            'body': {'size': 300}
        }
        self.assertIsNone(messages._extract_attachment_info(part))

    def test_extract_attachment_info_inline_with_filename(self):
        # Inline disposition but with a filename should still be extracted
        part = {
            'partId': '4',
            'mimeType': 'image/png',
            'filename': 'logo.png',
            'headers': [{'name': 'Content-Disposition', 'value': 'inline; filename="logo.png"'}],
            'body': {'attachmentId': 'attach-id-3', 'size': 500}
        }
        expected_info = {
            'filename': 'logo.png',
            'mimeType': 'image/png',
            'size': 500,
            'attachmentId': 'attach-id-3',
            'partId': '4'
        }
        self.assertEqual(messages._extract_attachment_info(part), expected_info)

    # --- Tests for src.messages.get_message (Attachment Extraction) ---
    def test_get_message_no_attachments(self):
        mock_msg_payload = {
            'id': 'msg-1',
            'threadId': 'thread-1',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'Test Email'}],
                'parts': [{'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Hello').decode()}}]
            }
        }
        self.mock_service.users().messages().get().execute.return_value = mock_msg_payload
        
        result = messages.get_message(self.mock_service, 'msg-1')
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'msg-1')
        self.assertIn('attachments', result)
        self.assertEqual(len(result['attachments']), 0)

    def test_get_message_one_simple_attachment(self):
        mock_msg_payload = {
            'id': 'msg-2', 'threadId': 'thread-2',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'With Attachment'}],
                'parts': [
                    {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Email body').decode()}},
                    {
                        'partId': 'att-part-1', 'filename': 'file1.txt', 'mimeType': 'text/plain',
                        'body': {'attachmentId': 'attach-id-file1', 'size': 123}
                    }
                ]
            }
        }
        self.mock_service.users().messages().get().execute.return_value = mock_msg_payload
        result = messages.get_message(self.mock_service, 'msg-2')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['attachments']), 1)
        self.assertEqual(result['attachments'][0]['filename'], 'file1.txt')
        self.assertEqual(result['attachments'][0]['attachmentId'], 'attach-id-file1')

    def test_get_message_multiple_attachments(self):
        mock_msg_payload = {
            'id': 'msg-3', 'threadId': 'thread-3',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'Multiple Attachments'}],
                'parts': [
                    {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Body here').decode()}},
                    {
                        'partId': 'att-part-a', 'filename': 'image.jpg', 'mimeType': 'image/jpeg',
                        'body': {'attachmentId': 'attach-id-jpg', 'size': 2000}
                    },
                    {
                        'partId': 'att-part-b', 'filename': 'doc.pdf', 'mimeType': 'application/pdf',
                        'headers': [{'name': 'Content-Disposition', 'value': 'attachment; filename="doc.pdf"'}],
                        'body': {'attachmentId': 'attach-id-pdf', 'size': 3000}
                    }
                ]
            }
        }
        self.mock_service.users().messages().get().execute.return_value = mock_msg_payload
        result = messages.get_message(self.mock_service, 'msg-3')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['attachments']), 2)
        self.assertEqual(result['attachments'][0]['filename'], 'image.jpg')
        self.assertEqual(result['attachments'][1]['filename'], 'doc.pdf')


    def test_get_message_nested_attachments(self):
        mock_msg_payload = {
            'id': 'msg-4', 'threadId': 'thread-4',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'Nested Attachments'}],
                'parts': [ # multipart/alternative
                    {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Plain text body').decode()}},
                    { # multipart/mixed
                        'mimeType': 'multipart/mixed',
                        'parts': [
                            {'mimeType': 'text/html', 'body': {'data': base64.urlsafe_b64encode(b'<p>HTML body</p>').decode()}},
                            {
                                'partId': 'nested-att-1', 'filename': 'report.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                'body': {'attachmentId': 'attach-id-docx', 'size': 5000}
                            }
                        ]
                    },
                    { # Another top-level attachment for good measure
                        'partId': 'top-att-1', 'filename': 'archive.zip', 'mimeType': 'application/zip',
                        'body': {'attachmentId': 'attach-id-zip', 'size': 10000}
                    }
                ]
            }
        }
        self.mock_service.users().messages().get().execute.return_value = mock_msg_payload
        result = messages.get_message(self.mock_service, 'msg-4')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['attachments']), 2) # Should find report.docx and archive.zip
        filenames = [att['filename'] for att in result['attachments']]
        self.assertIn('report.docx', filenames)
        self.assertIn('archive.zip', filenames)

    def test_get_message_attachment_with_partid_only_for_id(self):
        # This tests if an item with a filename but no attachmentId is still picked up.
        # The current _extract_attachment_info uses partId in the output dict,
        # but relies on filename for identification as an attachment.
        mock_msg_payload = {
            'id': 'msg-5', 'threadId': 'thread-5',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'PartID Test'}],
                'parts': [
                    {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Body').decode()}},
                    { # Regular attachment with attachmentId
                        'partId': 'att-part-real-id', 'filename': 'real_attach.dat', 'mimeType': 'application/octet-stream',
                        'body': {'attachmentId': 'attach-id-real', 'size': 600}
                    },
                    { # Attachment-like part with filename, but no 'attachmentId', only 'partId'
                      # This might be an inline image where 'data' is in 'body' but not 'attachmentId'
                        'partId': 'att-part-no-id', 'filename': 'inline_image.png', 'mimeType': 'image/png',
                        'body': {'size': 700} # No attachmentId
                    }
                ]
            }
        }
        self.mock_service.users().messages().get().execute.return_value = mock_msg_payload
        result = messages.get_message(self.mock_service, 'msg-5')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['attachments']), 2)
        
        # Check details of the first attachment (with attachmentId)
        self.assertEqual(result['attachments'][0]['filename'], 'real_attach.dat')
        self.assertEqual(result['attachments'][0]['attachmentId'], 'attach-id-real')
        self.assertEqual(result['attachments'][0]['partId'], 'att-part-real-id')

        # Check details of the second attachment (filename, no attachmentId)
        self.assertEqual(result['attachments'][1]['filename'], 'inline_image.png')
        self.assertIsNone(result['attachments'][1]['attachmentId']) # Expecting None as it wasn't in the payload
        self.assertEqual(result['attachments'][1]['partId'], 'att-part-no-id')

    # --- Tests for src.messages.get_attachment_data ---
    def test_get_attachment_data_success(self):
        sample_data_bytes = b"This is attachment data."
        encoded_data = base64.urlsafe_b64encode(sample_data_bytes).decode()
        mock_response = {'data': encoded_data, 'size': len(sample_data_bytes)}
        
        self.mock_get_execute.execute.return_value = mock_response
        
        result = messages.get_attachment_data(self.mock_service, 'msg-id', 'attach-id')
        self.assertEqual(result, sample_data_bytes)
        self.mock_attachments.get.assert_called_once_with(
            userId='me', messageId='msg-id', id='attach-id'
        )

    def test_get_attachment_data_api_error_404(self):
        # Simulate HttpError with status 404
        http_error = HttpError(resp=MagicMock(status=404), content=b"Not Found")
        self.mock_get_execute.execute.side_effect = http_error
        
        result = messages.get_attachment_data(self.mock_service, 'msg-id', 'attach-id-invalid')
        self.assertIsNone(result)
        self.mock_logger.warning.assert_called_once_with(
            "Attachment with ID attach-id-invalid not found in message msg-id."
        )

    def test_get_attachment_data_api_other_error(self):
        # Simulate HttpError with a different status
        http_error = HttpError(resp=MagicMock(status=500), content=b"Server Error")
        self.mock_get_execute.execute.side_effect = http_error

        result = messages.get_attachment_data(self.mock_service, 'msg-id', 'attach-id-err')
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_once_with(
            f"API error getting attachment attach-id-err for message msg-id: {http_error}"
        )

    def test_get_attachment_data_missing_data_field(self):
        # Simulate a response missing the 'data' field
        mock_response = {'size': 100} # Missing 'data'
        self.mock_get_execute.execute.return_value = mock_response

        result = messages.get_attachment_data(self.mock_service, 'msg-id', 'attach-id-missing-data')

        self.assertIsNone(result)
        self.mock_logger.error.assert_called_once_with("No data found in attachment attach-id-missing-data for message msg-id.")

    def test_get_attachment_data_decoding_error(self):
        # Provide data that will cause a base64 decoding error
        mock_response = {'data': 'this-is-not-valid-base64!', 'size': 100}
        self.mock_get_execute.execute.return_value = mock_response

        result = messages.get_attachment_data(self.mock_service, 'msg-id', 'attach-id-decode-err')

        self.assertIsNone(result) # Expecting None based on src/messages.py logic
        self.mock_logger.error.assert_called_once_with(ANY) # Check that error was logged
        mock_base64_decode.assert_called_once_with('invalid-base64-data') # Verify patch was called

    # --- Tests for src.messages.send_message (Attachment Handling) ---
    @patch('src.messages.mimetypes.guess_type')
    @patch('builtins.open', new_callable=mock_open, read_data=b"File content of attachment1.txt")
    def test_send_message_with_one_attachment(self, mock_file_open, mock_guess_type):
        self.mock_service.users().messages().send().execute.return_value = {'id': 'sent-msg-1'}
        mock_guess_type.return_value = ('text/plain', None) # Mock guess_type

        attachment_path = "dummy/attachment1.txt"
        
        msg_id = messages.send_message(
            self.mock_service, 
            to="recipient@example.com", 
            subject="Test with Attachment", 
            body="Please find attached.",
            attachments=[attachment_path]
        )
        self.assertEqual(msg_id, 'sent-msg-1')
        
        # Check that open was called correctly
        mock_file_open.assert_called_once_with(attachment_path, 'rb')

        # Check the raw message structure
        sent_body_arg = self.mock_service.users().messages().send.call_args[1]['body']
        self.assertIn('raw', sent_body_arg)
        
        raw_email_bytes = base64.urlsafe_b64decode(sent_body_arg['raw'])
        email_message = message_from_bytes(raw_email_bytes)
        
        self.assertTrue(email_message.is_multipart())
        self.assertEqual(len(email_message.get_payload()), 2) # Body + 1 attachment

        attachment_part = email_message.get_payload()[1]
        self.assertEqual(attachment_part.get_content_type(), 'text/plain')
        self.assertIn('attachment; filename="attachment1.txt"', attachment_part['Content-Disposition'])
        self.assertEqual(base64.b64decode(attachment_part.get_payload()), b"File content of attachment1.txt")

    @patch('src.messages.mimetypes.guess_type')
    @patch('builtins.open', new_callable=mock_open) # More complex mocking for multiple files
    def test_send_message_with_multiple_attachments(self, mock_file_open, mock_guess_type):
        self.mock_service.users().messages().send().execute.return_value = {'id': 'sent-msg-2'}

        # Configure side effects for open and guess_type for multiple files
        mock_guess_type.side_effect = [
            ('text/plain', None),         # For file1.txt
            ('image/jpeg', None)          # For image.jpg
        ]
        mock_file_open.side_effect = [
            mock_open(read_data=b"Text file content").return_value,
            mock_open(read_data=b"JPEG image data").return_value
        ]

        attachments_paths = ["path/to/file1.txt", "another/path/image.jpg"]
        
        msg_id = messages.send_message(
            self.mock_service,
            to="user@example.com", subject="Multiple Attachments", body="See attached files.",
            attachments=attachments_paths
        )
        self.assertEqual(msg_id, 'sent-msg-2')
        
        # Check raw message
        sent_body_arg = self.mock_service.users().messages().send.call_args[1]['body']
        raw_email_bytes = base64.urlsafe_b64decode(sent_body_arg['raw'])
        email_message = message_from_bytes(raw_email_bytes)

        self.assertTrue(email_message.is_multipart())
        self.assertEqual(len(email_message.get_payload()), 3) # Body + 2 attachments

        # Check first attachment
        att1 = email_message.get_payload()[1]
        self.assertEqual(att1.get_content_type(), 'text/plain')
        self.assertIn('filename="file1.txt"', att1['Content-Disposition'])
        self.assertEqual(base64.b64decode(att1.get_payload()), b"Text file content")

        # Check second attachment
        att2 = email_message.get_payload()[2]
        self.assertEqual(att2.get_content_type(), 'image/jpeg')
        self.assertIn('filename="image.jpg"', att2['Content-Disposition'])
        self.assertEqual(base64.b64decode(att2.get_payload()), b"JPEG image data")

    @patch('src.messages.logger')
    @patch('src.messages.mimetypes.guess_type')
    @patch('builtins.open', new_callable=mock_open)
    def test_send_message_attachment_not_found(self, mock_file_open, mock_guess_type, mock_logger):
        self.mock_service.users().messages().send().execute.return_value = {'id': 'sent-msg-3'}
        
        # Setup for two files, one will be found, one will raise FileNotFoundError
        mock_guess_type.side_effect = [('text/plain', None), ('application/pdf', None)] # For found_file.txt and missing_file.pdf
        
        # First call to open (found_file.txt) is successful
        # Second call to open (missing_file.pdf) raises FileNotFoundError
        mock_file_open.side_effect = [
            mock_open(read_data=b"Content of found file").return_value,
            FileNotFoundError("File missing_file.pdf not found")
        ]

        attachments_paths = ["path/found_file.txt", "path/missing_file.pdf"]
        
        msg_id = messages.send_message(
            self.mock_service,
            to="test@example.com", subject="File Not Found Test", body="One file should be attached.",
            attachments=attachments_paths
        )
        self.assertEqual(msg_id, 'sent-msg-3')
        
        mock_logger.error.assert_called_with("Attachment file not found: path/missing_file.pdf. Skipping this attachment.")
        
        # Verify that the message was sent with only the first attachment
        sent_body_arg = self.mock_service.users().messages().send.call_args[1]['body']
        raw_email_bytes = base64.urlsafe_b64decode(sent_body_arg['raw'])
        email_message = message_from_bytes(raw_email_bytes)
        
        self.assertTrue(email_message.is_multipart())
        self.assertEqual(len(email_message.get_payload()), 2) # Body + 1 (found) attachment
        self.assertIn('filename="found_file.txt"', email_message.get_payload()[1]['Content-Disposition'])

    def test_send_message_no_attachments(self): # Ensure it works without the attachments param
        self.mock_service.users().messages().send().execute.return_value = {'id': 'sent-msg-no-attach'}
        
        msg_id = messages.send_message(
            self.mock_service, 
            to="noattach@example.com", 
            subject="No Attachments Email", 
            body="This is a plain email."
            # attachments parameter is omitted
        )
        self.assertEqual(msg_id, 'sent-msg-no-attach')
        sent_body_arg = self.mock_service.users().messages().send.call_args[1]['body']
        raw_email_bytes = base64.urlsafe_b64decode(sent_body_arg['raw'])
        email_message = message_from_bytes(raw_email_bytes)

        self.assertTrue(email_message.is_multipart()) # MIMEMultipart is used by default
        # Even if no explicit attachments, MIMEMultipart might create a structure
        # The key is that the body part is there, and no *file* attachments are.
        # A simple text message in MIMEMultipart often has one part (the text body).
        payload = email_message.get_payload()
        self.assertEqual(len(payload), 1) # Only the text body part
        self.assertEqual(payload[0].get_content_type(), 'text/plain')

    # --- Tests for src.gmail_api.GmailClient (Attachment Methods) ---
    @patch('src.gmail_api.messages.get_attachment_data')
    def test_gmail_client_get_attachment_returns_bytes(self, mock_get_data):
        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client

        sample_bytes = b"attachment content"
        mock_get_data.return_value = sample_bytes
        
        result = mock_client.get_attachment("msg1", "att1", "file.txt")
        
        self.assertEqual(result, sample_bytes)
        mock_get_data.assert_called_once_with(mock_client.service, "msg1", "att1")

    @patch('src.gmail_api.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.gmail_api.messages.get_attachment_data') # Patch the function called by GmailClient.get_attachment
    def test_gmail_client_get_attachment_saves_file(self, mock_get_data, mock_file_open, mock_makedirs):
        # These mocks are now set up in setUp and/or within this test's decorators
        mock_path_exists = self.mock_os_path_exists # From setUp

        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client

        sample_bytes = b"data to save"
        mock_path_exists.return_value = False # Simulate directory does not exist
        mock_get_data.return_value = sample_bytes # Ensure get_attachment_data returns bytes

        download_dir = "test_downloads"
        filename = "output.dat"
        full_path = os.path.join(download_dir, filename)
        
        result = mock_client.get_attachment("msg2", "att2", filename, download_path=download_dir)
        
        self.assertEqual(result, sample_bytes) # Should return the bytes that were saved
        mock_get_data.assert_called_once_with(mock_client.service, "msg2", "att2")
        mock_path_exists.assert_called_once_with(download_dir)
        mock_makedirs.assert_called_once_with(download_dir)
        mock_file_open.assert_called_once_with(full_path, 'wb')
        mock_file_open().write.assert_called_once_with(sample_bytes)

    @patch('src.gmail_api.messages.get_attachment_data')
    def test_gmail_client_get_attachment_data_is_none(self, mock_get_data):
        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client

        mock_get_data.return_value = None # Simulate get_attachment_data returning None
        
        result = mock_client.get_attachment("msg3", "att3", "file.txt", download_path="some/path")
        self.assertIsNone(result)
        mock_get_data.assert_called_once_with(mock_client.service, "msg3", "att3")

    @patch('src.gmail_api.logger')
    def test_gmail_client_get_attachment_not_authenticated(self, mock_logger):
        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client
        mock_client.authenticated = False # Explicitly set to not authenticated for this test
        mock_client.service = None # Service should also be None if not authenticated
        
        result = mock_client.get_attachment("msg4", "att4", "file.txt")
        
        self.assertIsNone(result)
        mock_logger.error.assert_called_with("Not authenticated. Cannot get attachment att4 from message msg4.")

    @patch('src.gmail_api.messages.send_message') # Patch the function called by GmailClient.send_message
    def test_gmail_client_send_message_with_attachments(self, mock_messages_send):
        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client

        mock_messages_send.return_value = "sent-msg-client-1"
        
        to, subject, body = "to@example.com", "Client Subject", "Client Body"
        attachments = ["file1.pdf", "file2.jpg"]
        
        result = mock_client.send_message(to, subject, body, attachments=attachments)
        
        self.assertEqual(result, "sent-msg-client-1")
        mock_messages_send.assert_called_once_with(
            mock_client.service, to, subject, body, attachments=attachments
        )

    @patch('src.gmail_api.logger')
    @patch('src.gmail_api.messages.send_message') # Patch the function called by GmailClient.send_message
    def test_gmail_client_send_message_not_authenticated(self, mock_messages_send, mock_logger):
        # GmailClient.__init__ is patched in setUp
        mock_client = self.mock_client
        mock_client.authenticated = False # Explicitly set to not authenticated for this test
        mock_client.service = None # Service should also be None if not authenticated
        
        result = mock_client.send_message("to@example.com", "Subj", "Body", attachments=["file.txt"])
        
        self.assertIsNone(result)
        mock_logger.error.assert_called_with("Not authenticated. Cannot send message to to@example.com.")
        mock_messages_send.assert_not_called() # Ensure send_message was not called


if __name__ == '__main__':
    unittest.main()
