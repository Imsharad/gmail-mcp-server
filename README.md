# Gmail MCP Server

This MCP server provides access to Gmail functionality through the Model Context Protocol, allowing LLMs like Claude to interact with your email.

## Features

- List emails from your inbox
- Search for specific emails
- Read email content
- Send new emails
- Reply to existing emails
- Delete individual emails
- Batch delete multiple emails at once

## Setup

1. Install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Set up Google API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Gmail API:
     - In the sidebar, navigate to "APIs & Services" > "Library"
     - Search for "Gmail API" and select it
     - Click "Enable"
   - Create OAuth 2.0 credentials:
     - In the sidebar, navigate to "APIs & Services" > "Credentials"
     - Click "Create Credentials" and select "OAuth client ID"
     - Select "Desktop application" as the application type
     - Enter a name for your OAuth client (e.g., "Gmail MCP Server")
     - Click "Create"
     - Download the credentials JSON file and save it as `credentials.json` in the project root

3. Create a `.env` file by copying the example:
   ```
   cp .env.example .env
   ```

4. Run the server:
   - The first time you run the server, it will open a browser window for authentication
   - Follow the prompts to authorize the application to access your Gmail account

## Detailed Gmail API Setup

### Understanding the Credentials Files

1. **credentials.json**:
   - This file contains your OAuth 2.0 client credentials from Google Cloud
   - It's used to identify your application to Google's OAuth servers
   - Format example (values will be different for your application):
     ```json
     {
       "installed": {
         "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
         "project_id": "your-project-id",
         "auth_uri": "https://accounts.google.com/o/oauth2/auth",
         "token_uri": "https://oauth2.googleapis.com/token",
         "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
         "client_secret": "YOUR_CLIENT_SECRET",
         "redirect_uris": ["http://localhost"]
       }
     }
     ```
   - You can use the provided `credentials.json.example` as a reference

2. **token.json**:
   - This file is generated automatically during the first authentication
   - It contains the OAuth tokens needed to access your Gmail account
   - The file is created when you complete the authentication flow in your browser
   - Format example (tokens will be different for your account):
     ```json
     {
       "token": "ya29.a0AfB_byC...",
       "refresh_token": "1//0eXxYz...",
       "token_uri": "https://oauth2.googleapis.com/token",
       "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
       "client_secret": "YOUR_CLIENT_SECRET",
       "scopes": [
         "https://www.googleapis.com/auth/gmail.readonly",
         "https://www.googleapis.com/auth/gmail.send",
         "https://www.googleapis.com/auth/gmail.compose",
         "https://www.googleapis.com/auth/gmail.modify"
       ],
       "expiry": "2025-03-05T14:30:00.000Z"
     }
     ```

### Authentication Flow

1. When you run the server for the first time:
   - The server will check for a `token.json` file
   - If not found, it will start the OAuth 2.0 authentication flow
   - A browser window will open asking you to sign in to your Google account
   - You'll be asked to grant permissions to the application
   - After granting permissions, the browser will show a success message
   - The server will automatically save the tokens to `token.json`

2. For subsequent runs:
   - The server will use the existing `token.json` file
   - If the tokens are expired, they will be automatically refreshed
   - The refreshed tokens will be saved back to `token.json`

### Security Considerations

- Keep your `credentials.json` and `token.json` files secure
- Do not commit these files to version control
- The `.gitignore` file is configured to exclude these files
- If you suspect your credentials have been compromised, revoke them in the Google Cloud Console and generate new ones

## Usage

Run the server:
```
source venv/bin/activate  # On Windows: venv\Scripts\activate
python -m src.server
```

Configure Claude Desktop to use this server by adding it to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/gmail-mcp-server"
    }
  }
}
```

### Available Tool Functions

The Gmail MCP Server provides the following tool functions:

1. **list_emails** - Lists emails from your Gmail inbox
   - Parameters: 
     - `max_results`: Maximum number of emails to return (default: 10)
     - `label`: Gmail label to filter by (default: INBOX)

2. **get_email** - Gets the full content of a specific email
   - Parameters:
     - `email_id`: The ID of the email to retrieve

3. **search_emails** - Searches for emails matching a query
   - Parameters:
     - `query`: Search query to match against email fields
     - `max_results`: Maximum number of results to return (default: 5)

4. **send_email** - Sends a new email
   - Parameters:
     - `to`: Recipient email address
     - `subject`: Email subject
     - `body`: Email body content

5. **reply_to_email** - Replies to an existing email
   - Parameters:
     - `email_id`: ID of the email to reply to
     - `body`: Reply message content

6. **delete_email** - Deletes a single email
   - Parameters:
     - `email_id`: ID of the email to delete

7. **delete_emails** - Deletes multiple emails in a batch operation
   - Parameters:
     - `email_ids`: List of email IDs to delete

## Design Philosophy

This project follows a lean, efficient design philosophy:
1. Minimal code with no bloat
2. Direct integration with Gmail API
3. No mock data or unnecessary abstractions
4. Focus on reliability and performance

## Troubleshooting

### Authentication Issues

If you encounter authentication issues:

1. Check that your `credentials.json` file is correctly placed in the project root
2. Delete the `token.json` file if it exists to force re-authentication
3. Ensure you have the correct scopes enabled for your OAuth client
4. Check the console logs for specific error messages

### Gmail API Rate Limits

The Gmail API has rate limits that may affect usage:

- 1,000,000,000 quota units per day
- Each API method consumes different quota units
- For more information, see the [Gmail API Quotas](https://developers.google.com/gmail/api/reference/quota)
