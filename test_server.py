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
            
            # --- Test list_emails ---
            logger.info("Testing list_emails tool...")
            result_list = await session.call_tool("list_emails", {"max_results": 5, "label": "INBOX"})
            if "Found" in result_list.content[0].text:
                logger.info("✅ list_emails test passed")
                logger.info(f"Result: {result_list.content[0].text[:100]}...")
            else:
                logger.error("❌ list_emails test failed")
                logger.error(f"Result: {result_list.content[0].text}")
            
            email_id = None
            lines = result_list.content[0].text.split('\n')
            for line in lines:
                if line.startswith("ID: "):
                    email_id = line[4:].strip()
                    break

            # --- Test get_email ---
            logger.info("Testing get_email tool...")
            if email_id:
                result_get = await session.call_tool("get_email", {"email_id": email_id})
                if "From:" in result_get.content[0].text and "Subject:" in result_get.content[0].text:
                    logger.info("✅ get_email test passed")
                    logger.info(f"Result: {result_get.content[0].text[:100]}...")
                else:
                    logger.error("❌ get_email test failed")
                    logger.error(f"Result: {result_get.content[0].text}")
            else:
                logger.error("❌ get_email test skipped - no email ID available")

            # --- Test search_emails ---
            logger.info("Testing search_emails tool...")
            result_search = await session.call_tool("search_emails", {"query": "is:inbox", "max_results": 3})
            if "Found" in result_search.content[0].text:
                logger.info("✅ search_emails test passed")
                logger.info(f"Result: {result_search.content[0].text[:100]}...")
            else:
                logger.error("❌ search_emails test failed")
                logger.error(f"Result: {result_search.content[0].text}")

            # --- Test send_email ---
            logger.info("Testing send_email tool...")
            result_send = await session.call_tool("send_email", {
                "to": "test@example.com",
                "subject": "Test Email",
                "body": "This is a test email sent from the Gmail MCP Server test script."
            })
            if "Email sent successfully" in result_send.content[0].text:
                logger.info("✅ send_email test passed")
                logger.info(f"Result: {result_send.content[0].text}")
            else:
                logger.error("❌ send_email test failed")
                logger.error(f"Result: {result_send.content[0].text}")

            # --- Test reply_to_email ---
            logger.info("Testing reply_to_email tool...")
            if email_id:
                result_reply = await session.call_tool("reply_to_email", {
                    "email_id": email_id,
                    "body": "This is a test reply sent from the Gmail MCP Server test script."
                })
                if "Reply sent successfully" in result_reply.content[0].text:
                    logger.info("✅ reply_to_email test passed")
                    logger.info(f"Result: {result_reply.content[0].text}")
                else:
                    logger.error("❌ reply_to_email test failed")
                    logger.error(f"Result: {result_reply.content[0].text}")
            else:
                logger.error("❌ reply_to_email test skipped - no email ID available")

            logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_all_tools()) 