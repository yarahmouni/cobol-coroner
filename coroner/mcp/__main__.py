"""Entry point for running the COBOL Coroner MCP server as a module."""

from coroner.mcp.server import server


if __name__ == "__main__":
    server.run()
