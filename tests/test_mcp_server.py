"""Tests for Coroner MCP server with 7 tools."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def run_mcp_session(coro, base_dir=None):
    """Open stdio session to coroner.mcp and run a coroutine.
    
    Args:
        coro: Coroutine to run with the session
        base_dir: Optional base directory for runs/ and build/
    """
    env = os.environ.copy()
    if base_dir:
        env["CORONER_BASE_DIR"] = str(base_dir)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coroner.mcp"],
        cwd=Path(__file__).parent.parent,
        env=env
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


def test_alive_run_workflow(tmp_path):
    """Test ALIVE run workflow: run_differential_check, get_verdict, generate_certificate, verify_certificate."""
    async def workflow(session):
        # Step 1: Run differential check (ALIVE)
        alive_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": "samples/credit-fees/java/CreditFees.java",
            "schema": "samples/credit-fees/schema.json",
            "cases": 30,
            "seed": 42
        })
        assert alive_result.is_error is False
        alive_content = json.loads(alive_result.content[0].text)
        alive_run_id = alive_content["run_id"]
        assert alive_content["status"] == "ALIVE"
        
        # Step 2: Get verdict
        verdict_result = await session.call_tool("get_verdict", arguments={"run_id": alive_run_id})
        assert verdict_result.is_error is False
        verdict_data = json.loads(verdict_result.content[0].text)
        assert verdict_data["status"] == "ALIVE"
        
        # Step 3: Generate certificate (already exists from run)
        cert_result = await session.call_tool("generate_certificate", arguments={"run_id": alive_run_id})
        assert cert_result.is_error is False
        cert_gen_data = json.loads(cert_result.content[0].text)
        assert "path" in cert_gen_data
        
        # Step 4: Verify certificate
        cert_path = f"runs/{alive_run_id}/certificate.json"
        verify_result = await session.call_tool("verify_certificate", arguments={"path": cert_path})
        assert verify_result.is_error is False
        verify_data = json.loads(verify_result.content[0].text)
        assert verify_data["valid"] is True
        assert verify_data["status"] == "ALIVE"
        
        # Step 5: get_failure_report should fail on ALIVE
        failure_result = await session.call_tool("get_failure_report", arguments={"run_id": alive_run_id})
        assert failure_result.is_error is True
        error_text = failure_result.content[0].text if failure_result.content else ""
        assert "No failure report: the run was ALIVE" in error_text
        
        # Step 6: export_junit_test should fail on ALIVE
        junit_result = await session.call_tool("export_junit_test", arguments={"run_id": alive_run_id})
        assert junit_result.is_error is True
        error_text = junit_result.content[0].text if junit_result.content else ""
        assert "No JUnit test: the run was ALIVE" in error_text
    
    asyncio.run(run_mcp_session(workflow, base_dir=tmp_path))


def test_zombie_run_workflow(tmp_path):
    """Test ZOMBIE run workflow: run_differential_check, get_verdict, get_failure_report, export_junit_test."""
    import sys
    
    # The MCP server refuses Java paths outside the repository, so the variant goes into a folder of
    # its own inside build/ (unique name, removed at the end). Never build/variants/: that folder is
    # shared with scripts/init_demo_runs.sh and make zombie.
    repo_root = Path(__file__).parent.parent
    (repo_root / "build").mkdir(exist_ok=True)
    own_dir = Path(tempfile.mkdtemp(prefix="mcp-test-variant-", dir=repo_root / "build"))
    variant_java = own_dir / "CreditFees.java"
    java_arg = f"build/{own_dir.name}/CreditFees.java"
    result = subprocess.run(
        [sys.executable, "-m", "coroner.catalog.legacy_variant", 
         "samples/credit-fees/java/CreditFees.java", str(variant_java)],
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 0, f"Variant generation failed: {result.stderr}"
    assert variant_java.exists(), "Variant file not created"
    
    async def workflow(session):
        # Step 1: Run differential check (ZOMBIE with HALF_EVEN variant)
        zombie_result = await session.call_tool("run_differential_check", arguments={
            "cobol": "samples/credit-fees/CREDIT-FEES.cob",
            "copybooks": "samples/credit-fees/copybooks",
            "java": java_arg,
            "schema": "samples/credit-fees/schema.json",
            "cases": 30,
            "seed": 42
        })
        assert zombie_result.is_error is False
        zombie_content = json.loads(zombie_result.content[0].text)
        zombie_run_id = zombie_content["run_id"]
        assert zombie_content["status"] == "ZOMBIE"
        
        # Step 2: Get verdict
        verdict_result = await session.call_tool("get_verdict", arguments={"run_id": zombie_run_id})
        assert verdict_result.is_error is False
        verdict_data = json.loads(verdict_result.content[0].text)
        assert verdict_data["status"] == "ZOMBIE"
        
        # Step 3: Get failure report
        failure_result = await session.call_tool("get_failure_report", arguments={"run_id": zombie_run_id})
        assert failure_result.is_error is False
        failure_data = json.loads(failure_result.content[0].text)
        assert "case_id" in failure_data
        assert "cobol_output" in failure_data
        assert "java_output" in failure_data
        
        # Step 4: Export JUnit test
        junit_result = await session.call_tool("export_junit_test", arguments={"run_id": zombie_run_id})
        assert junit_result.is_error is False
        junit_data = json.loads(junit_result.content[0].text)
        assert "path" in junit_data
        assert "content" in junit_data
        assert "ZombieRegressionTest" in junit_data["content"]
        
        # Step 5: Verify certificate
        cert_path = f"runs/{zombie_run_id}/certificate.json"
        verify_result = await session.call_tool("verify_certificate", arguments={"path": cert_path})
        assert verify_result.is_error is False
        verify_data = json.loads(verify_result.content[0].text)
        assert verify_data["valid"] is True
        assert verify_data["status"] == "ZOMBIE"
    
    try:
        asyncio.run(run_mcp_session(workflow, base_dir=tmp_path))
    finally:
        shutil.rmtree(own_dir, ignore_errors=True)


def test_get_detection_matrix_not_available(tmp_path):
    """Detection matrix should return error until catalog is built."""
    async def check(session):
        # With an empty tmp base, catalog doesn't exist
        result = await session.call_tool("get_detection_matrix", arguments={})
        assert result.is_error is True
        error_text = result.content[0].text if result.content else ""
        assert "Detection Matrix not available yet" in error_text, f"Expected error message, got: {error_text}"
    
    asyncio.run(run_mcp_session(check, base_dir=tmp_path))


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


def test_verify_certificate_refuses_a_path_that_leaves_the_base_directory(tmp_path):
    """A relative certificate path is looked up in the base directory first; "../" cannot leave it."""
    base = tmp_path / "base"
    base.mkdir()
    (tmp_path / "outside.json").write_text("{}")

    async def check(session):
        for path in ("../outside.json", "runs/../../outside.json", str(tmp_path / "outside.json")):
            result = await session.call_tool("verify_certificate", arguments={"path": path})
            assert result.is_error is True, path
            assert "Path outside repository" in result.content[0].text, path

    asyncio.run(run_mcp_session(check, base_dir=base))


def test_invalid_run_id(tmp_path):
    """Invalid run_id should be rejected."""
    async def check(session):
        result = await session.call_tool("get_verdict", arguments={"run_id": "invalid_id"})
        assert result.is_error is True
        error_text = result.content[0].text if result.content else ""
        assert "Invalid run_id" in error_text, f"Expected invalid run_id error, got: {error_text}"
    
    asyncio.run(run_mcp_session(check, base_dir=tmp_path))


@pytest.mark.slow
def test_get_detection_matrix_with_catalog(tmp_path):
    """Get detection matrix when catalog exists (runs real catalog at 200 cases)."""
    import json
    from coroner.traps import run_catalog, write_catalog_files
    
    # Generate real catalog at 200 cases, seed 42
    catalog_dict = run_catalog(seed=42, cases=200, base_dir=str(tmp_path))
    write_catalog_files(catalog_dict, base_dir=str(tmp_path))
    
    async def check(session):
        # Get full detection matrix
        result = await session.call_tool("get_detection_matrix", arguments={})
        assert result.is_error is False, f"Tool call failed: {result.content if result.is_error else ''}"
        
        matrix_data = json.loads(result.content[0].text)
        assert "traps" in matrix_data, "Matrix should have 'traps' key"
        assert len(matrix_data["traps"]) == 6, f"Expected 6 traps, got {len(matrix_data['traps'])}"
        
        # Verify T1 to T5 have measured numbers
        for trap in matrix_data["traps"][:5]:
            assert trap["status"] == "measured", f"Trap {trap['id']} should be measured"
            assert "cases_generated" in trap, f"Trap {trap['id']} should have cases_generated"
            assert trap["cases_generated"] == 200, f"Trap {trap['id']} should have 200 cases"
            assert "cases_detected" in trap, f"Trap {trap['id']} should have cases_detected"
            assert "detection_rate" in trap, f"Trap {trap['id']} should have detection_rate"
            # Verify detection_rate formula
            expected_rate = trap["cases_detected"] / trap["cases_generated"]
            actual_rate = float(trap["detection_rate"])
            assert abs(actual_rate - expected_rate) < 0.0001, f"Trap {trap['id']} rate mismatch"
        
        # Verify T6 has no numeric fields (placeholder)
        t6 = matrix_data["traps"][5]
        assert t6["id"] == "T6", f"Expected T6, got {t6['id']}"
        assert "cases_generated" not in t6, "T6 should not have cases_generated"
        assert "cases_detected" not in t6, "T6 should not have cases_detected"
        
        # Get single trap T1
        t1_result = await session.call_tool("get_detection_matrix", arguments={"trap_id": "T1"})
        assert t1_result.is_error is False
        
        t1_data = json.loads(t1_result.content[0].text)
        assert t1_data["id"] == "T1", f"Expected T1, got {t1_data.get('id')}"
        assert t1_data["cases_generated"] == 200
        
        # Get unknown trap should fail
        unknown_result = await session.call_tool("get_detection_matrix", arguments={"trap_id": "T99"})
        assert unknown_result.is_error is True
        error_text = unknown_result.content[0].text if unknown_result.content else ""
        assert "not found" in error_text, f"Expected not found error, got: {error_text}"
    
    asyncio.run(run_mcp_session(check, base_dir=tmp_path))


@pytest.mark.slow
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
            "cases": 30,
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
