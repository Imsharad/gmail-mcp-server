#!/usr/bin/env python3
"""
Test script for Gmail MCP Server
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_list_emails(session: ClientSession) -> None:
    """Test the list_emails tool"""
    logger.info("Testing list_emails tool...")
    
    # Call the tool
    result = await session.call_tool("list_emails", {"max_results": 5, "label": "INBOX"})
    
    # Check the result
    if "Found" in result.content[0].text:
        logger.info("✅ list_emails test passed")
        logger.info(f"Result: {result.content[0].text[:100]}...")
    else:
        logger.error("❌ list_emails test failed")
        logger.error(f"Result: {result.content[0].text}")
    
    # Return the first email ID for further tests
    lines = result.content[0].text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith("ID: "):
            return line[4:].strip()
    
    return None

async def test_get_email(session: ClientSession, email_id: str) -> None:
    """Test the get_email tool"""
    logger.info("Testing get_email tool...")
    
    if not email_id:
        logger.error("❌ get_email test skipped - no email ID available")
        return
    
    # Call the tool
    result = await session.call_tool("get_email", {"email_id": email_id})
    
    # Check the result
    if "From:" in result.content[0].text and "Subject:" in result.content[0].text:
        logger.info("✅ get_email test passed")
        logger.info(f"Result: {result.content[0].text[:100]}...")
    else:
        logger.error("❌ get_email test failed")
        logger.error(f"Result: {result.content[0].text}")

async def test_search_emails(session: ClientSession) -> None:
    """Test the search_emails tool"""
    logger.info("Testing search_emails tool...")
    
    # Call the tool with a generic search term likely to find results
    result = await session.call_tool("search_emails", {"query": "is:inbox", "max_results": 3})
    
    # Check the result
    if "Found" in result.content[0].text:
        logger.info("✅ search_emails test passed")
        logger.info(f"Result: {result.content[0].text[:100]}...")
    else:
        logger.error("❌ search_emails test failed")
        logger.error(f"Result: {result.content[0].text}")

async def test_send_email(session: ClientSession) -> None:
    """Test the send_email tool"""
    logger.info("Testing send_email tool...")
    
    # Call the tool
    result = await session.call_tool("send_email", {
        "to": "test@example.com",
        "subject": "Test Email",
        "body": "This is a test email sent from the Gmail MCP Server test script."
    })
    
    # Check the result
    if "Email sent successfully" in result.content[0].text:
        logger.info("✅ send_email test passed")
        logger.info(f"Result: {result.content[0].text}")
    else:
        logger.error("❌ send_email test failed")
        logger.error(f"Result: {result.content[0].text}")

async def test_reply_to_email(session: ClientSession, email_id: str) -> None:
    """Test the reply_to_email tool"""
    logger.info("Testing reply_to_email tool...")
    
    if not email_id:
        logger.error("❌ reply_to_email test skipped - no email ID available")
        return
    
    # Call the tool
    result = await session.call_tool("reply_to_email", {
        "email_id": email_id,
        "body": "This is a test reply sent from the Gmail MCP Server test script."
    })
    
    # Check the result
    if "Reply sent successfully" in result.content[0].text:
        logger.info("✅ reply_to_email test passed")
        logger.info(f"Result: {result.content[0].text}")
    else:
        logger.error("❌ reply_to_email test failed")
        logger.error(f"Result: {result.content[0].text}")

async def test_all_tools() -> None:
    """Test all tools in the Gmail MCP Server"""
    logger.info("Starting Gmail MCP Server tests...")
    
    # Set up server parameters
    params = StdioServerParameters(
        command="python",
        args=["-m", "src.server"],
    )
    
    # Connect to the server
    async with stdio_client(params) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            tools_result = await session.list_tools()
            logger.info(f"Available tools: {[tool.name for tool in tools_result.tools]}")
            
            # Test each tool
            email_id = await test_list_emails(session)
            await test_get_email(session, email_id)
            await test_search_emails(session)
            await test_send_email(session)
            await test_reply_to_email(session, email_id)
            
            logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_all_tools()) 