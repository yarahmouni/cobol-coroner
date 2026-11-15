"""MCP server for COBOL Coroner."""

import sys
from dataclasses import dataclass
from typing import Literal
from mcp.server.mcpserver import MCPServer


@dataclass
class Verdict:
    verdict: Literal["ALIVE", "ZOMBIE"]
    divergences: int
    test_cases: int
    message: str


server = MCPServer(
    name="coroner",
    title="COBOL Coroner",
    description="The independent regression auditor for COBOL-to-Java migrations",
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
        verdict="ALIVE",
        divergences=0,
        test_cases=1,
        message="PASS: business behavior preserved on 1 case (stub)"
    )
