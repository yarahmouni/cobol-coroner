"""Entry point for running the Lazarus MCP server as a module."""

from lazarus.mcp.server import server


if __name__ == "__main__":
    server.run()
