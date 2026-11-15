"""Tests for Coroner MCP server with 7 tools."""
import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def run_mcp_session(coro):
    """Open stdio session to coroner.mcp and run a coroutine."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coroner.mcp"],
        cwd=Path(__file__).parent.parent
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await coro(session)


def test_list_tools():
    """List tools and verify all 7 are present."""
    async def check(session):
        result = await session.list_tools()
        tool_names = [tool.name for tool in result.tools]
        
        expected_tools = [
            "run_differential_check",
            "get_verdict",
            "get_failure_report",
            "get_detection_matrix",
            "export_junit_test",
            "generate_certificate",
            "verify_certificate"
        ]
        
        assert len(tool_names) == 7, f"Expected 7 tools, got {len(tool_names)}: {tool_names}"
        for expected in expected_tools:
            assert expected in tool_names, f"Tool {expected} not found"
    
    asyncio.run(run_mcp_session(check))


def test_run_differential_check_alive():
    """Run differential check on demo sample, expect ALIVE."""
    async def check(session):
        result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        assert result.is_error is False, f"Tool call failed: {result.content if result.is_error else ''}"
        
        import json
        content = json.loads(result.content[0].text)
        
        assert content["status"] == "ALIVE", f"Expected ALIVE, got {content['status']}"
        assert content["cases_divergent"] == 0, f"Expected 0 divergences, got {content['cases_divergent']}"
        assert len(content["run_id"]) == 12, f"run_id should be 12 characters, got {len(content['run_id'])}"
        
        return content["run_id"]
    
    asyncio.run(run_mcp_session(check))


def test_get_verdict():
    """Get verdict for a run."""
    async def check(session):
        # First run the check
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        run_id = run_content["run_id"]
        
        # Then get the verdict
        verdict_result = await session.call_tool("get_verdict", arguments={"run_id": run_id})
        assert verdict_result.is_error is False
        
        verdict_data = json.loads(verdict_result.content[0].text)
        assert verdict_data["status"] == "ALIVE"
    
    asyncio.run(run_mcp_session(check))


def test_verify_certificate():
    """Verify a certificate."""
    async def check(session):
        # First run the check
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        cert_path = run_content["certificate_path"]
        
        # Verify the certificate
        cert_result = await session.call_tool("verify_certificate", arguments={"path": cert_path})
        assert cert_result.is_error is False
        
        cert_data = json.loads(cert_result.content[0].text)
        assert cert_data["valid"] is True, "Certificate should be valid"
        assert cert_data["status"] == "ALIVE"
    
    asyncio.run(run_mcp_session(check))


def test_get_detection_matrix_not_available():
    """Detection matrix should return error until catalog is built."""
    async def check(session):
        result = await session.call_tool("get_detection_matrix", arguments={})
        assert result.is_error is True
        # Check error message is present
        error_text = result.content[0].text if result.content else ""
        assert "Detection Matrix not available yet" in error_text, f"Expected error message, got: {error_text}"
    
    asyncio.run(run_mcp_session(check))


def test_run_differential_check_zombie():
    """Run differential check on legacy variant, expect ZOMBIE."""
    async def check(session):
        result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "build/variants/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        assert result.is_error is False
        
        import json
        content = json.loads(result.content[0].text)
        
        assert content["status"] == "ZOMBIE", f"Expected ZOMBIE, got {content['status']}"
        assert content["cases_divergent"] > 0, "Expected divergences"
        
        return content["run_id"]
    
    asyncio.run(run_mcp_session(check))


def test_get_failure_report():
    """Get failure report for a ZOMBIE run."""
    async def check(session):
        # First run the check
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "build/variants/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        run_id = run_content["run_id"]
        
        # Get failure report
        failure_result = await session.call_tool("get_failure_report", arguments={"run_id": run_id})
        assert failure_result.is_error is False
        
        failure_data = json.loads(failure_result.content[0].text)
        assert "case_id" in failure_data
        assert "cobol_output" in failure_data
        assert "java_output" in failure_data
    
    asyncio.run(run_mcp_session(check))


def test_export_junit_test():
    """Export JUnit test for a ZOMBIE run."""
    async def check(session):
        # First run the check
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "build/variants/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        run_id = run_content["run_id"]
        
        # Export JUnit test
        junit_result = await session.call_tool("export_junit_test", arguments={"run_id": run_id})
        assert junit_result.is_error is False
        
        junit_data = json.loads(junit_result.content[0].text)
        assert "path" in junit_data
        assert "content" in junit_data
        assert "ZombieRegressionTest" in junit_data["content"]
    
    asyncio.run(run_mcp_session(check))


def test_path_validation():
    """Path validation should reject paths outside the repository."""
    async def check(session):
        result = await session.call_tool("run_differential_check", arguments={
            "cobol": "../etc/passwd",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json"
        })
        
        assert result.is_error is True
        error_text = result.content[0].text if result.content else ""
        assert "Path outside repository" in error_text, f"Expected path error message, got: {error_text}"
    
    asyncio.run(run_mcp_session(check))


def test_invalid_run_id():
    """Invalid run_id should be rejected."""
    async def check(session):
        result = await session.call_tool("get_verdict", arguments={"run_id": "invalid_id"})
        assert result.is_error is True
        error_text = result.content[0].text if result.content else ""
        assert "Invalid run_id" in error_text, f"Expected invalid run_id error, got: {error_text}"
    
    asyncio.run(run_mcp_session(check))


def test_get_failure_report_alive():
    """Get failure report should fail on ALIVE run."""
    async def check(session):
        # First run the check to get an ALIVE run
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        run_id = run_content["run_id"]
        
        # Try to get failure report
        failure_result = await session.call_tool("get_failure_report", arguments={"run_id": run_id})
        assert failure_result.is_error is True
        error_text = failure_result.content[0].text if failure_result.content else ""
        assert "No failure report: the run was ALIVE" in error_text, f"Expected ALIVE error, got: {error_text}"
    
    asyncio.run(run_mcp_session(check))


def test_export_junit_test_alive():
    """Export JUnit test should fail on ALIVE run."""
    async def check(session):
        # First run the check to get an ALIVE run
        run_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        import json
        run_content = json.loads(run_result.content[0].text)
        run_id = run_content["run_id"]
        
        # Try to export JUnit test
        junit_result = await session.call_tool("export_junit_test", arguments={"run_id": run_id})
        assert junit_result.is_error is True
        error_text = junit_result.content[0].text if junit_result.content else ""
        assert "No JUnit test: the run was ALIVE" in error_text, f"Expected ALIVE error, got: {error_text}"
    
    asyncio.run(run_mcp_session(check))



def test_server_from_temp_directory():
    """
    Server started from /tmp should write runs/ inside the repository.
    
    This test verifies the fix for the bug where the MCP server wrote
    runs/ relative to its cwd instead of the repository root.
    """
    import tempfile
    import os
    
    async def check(session):
        # Get the repository root
        repo_root = Path(__file__).parent.parent
        
        # Run differential check (should write to repo_root/runs/, not /tmp/runs/)
        result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 200,
            "seed": 42
        })
        
        assert result.is_error is False
        
        import json
        content = json.loads(result.content[0].text)
        run_id = content["run_id"]
        cert_path = content["certificate_path"]
        
        # Verify run directory is inside the repository
        run_dir = repo_root / "runs" / run_id
        assert run_dir.exists(), f"Run directory not found at {run_dir}"
        assert (run_dir / "verdict.json").exists(), "verdict.json not found"
        assert (run_dir / "certificate.json").exists(), "certificate.json not found"
        
        # Verify certificate path is inside repository
        full_cert_path = repo_root / cert_path
        assert full_cert_path.exists(), f"Certificate not found at {full_cert_path}"
        
        # Verify certificate can be replayed
        cert_result = await session.call_tool("verify_certificate", arguments={"path": cert_path})
        assert cert_result.is_error is False
        
        cert_data = json.loads(cert_result.content[0].text)
        assert cert_data["valid"] is True, "Certificate should be valid"
        assert cert_data["status"] == "ALIVE"
        
        return run_id
    
    # Start server with cwd set to a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(__file__).parent.parent
        
        async def run_from_tmp():
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "coroner.mcp"],
                cwd=tmpdir  # Start from /tmp, not from repo root
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await check(session)
        
        run_id = asyncio.run(run_from_tmp())
        
        # Verify no runs/ directory was created in /tmp
        tmp_runs = Path(tmpdir) / "runs"
        assert not tmp_runs.exists(), f"Server should not write to {tmp_runs}"
        
        # Clean up the run directory
        run_dir = repo_root / "runs" / run_id
        if run_dir.exists():
            import shutil
            shutil.rmtree(run_dir)
