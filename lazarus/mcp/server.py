"""MCP server for COBOL Lazarus."""

import sys
from dataclasses import dataclass
from typing import Literal
from mcp.server.mcpserver import MCPServer


@dataclass
class Verdict:
    verdict: Literal["VIVANT", "ZOMBIE"]
    divergences: int
    test_cases: int
    message: str


server = MCPServer(
    name="lazarus",
    title="COBOL Lazarus",
    description="The zombie detector for COBOL to Java migrations",
    version="0.1.0"
)


@server.tool()
def get_verdict(project_id: str) -> Verdict:
    """Get the verification verdict for a COBOL to Java migration project.
    
    Args:
        project_id: Identifier for the verification project
        
    Returns:
        Verdict with status, divergences count, test cases count, and message
    """
    print(f"[get_verdict] Called with project_id={project_id!r}", file=sys.stderr)
    
    return Verdict(
        verdict="VIVANT",
        divergences=0,
        test_cases=1,
        message="0 divergence found on 1 case (stub)"
    )
