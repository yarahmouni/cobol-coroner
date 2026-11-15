"""MCP server for COBOL Coroner."""

import sys
from mcp.server.mcpserver import MCPServer
from coroner.verdict import Verdict


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
        Verdict with status, divergences count, test cases count, and sub_label
    """
    print(f"[get_verdict] Called with project_id={project_id!r}", file=sys.stderr)
    
    return Verdict(
        status="ALIVE",
        sub_label="PASS: business behavior preserved on 1 case (stub)",
        cases_total=1,
        cases_divergent=0,
        run_return_codes=(0, 0),
        validation_notice="Validated under GnuCOBOL 3.x"
    )
