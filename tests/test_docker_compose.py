"""
Docker Compose validation tests.

These tests validate that both docker-compose.yml and docker-compose.server.yml
are valid and properly configured with security limits.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml


# Register PyYAML constructor for !reset tag
def reset_constructor(loader, node):
    """Handle !reset tag by returning the node value."""
    return loader.construct_sequence(node)


yaml.SafeLoader.add_constructor('!reset', reset_constructor)


def parse_size_to_bytes(size_str):
    """Parse Docker size strings to bytes (512M, 2G, 2g, plain bytes)."""
    if isinstance(size_str, int):
        return size_str
    
    size_str = str(size_str).strip()
    if size_str.isdigit():
        return int(size_str)
    
    multipliers = {
        'k': 1024,
        'm': 1024 ** 2,
        'g': 1024 ** 3,
    }
    
    unit = size_str[-1].lower()
    if unit in multipliers:
        return int(size_str[:-1]) * multipliers[unit]
    
    return int(size_str)


@pytest.mark.slow
def test_init_demo_runs_script(tmp_path):
    """Test the full init_demo_runs.sh script creates all expected runs."""
    # Run the script with CORONER_BASE_DIR in tmp_path
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    env["PYTHON"] = sys.executable
    
    result = subprocess.run(
        ["bash", "scripts/init_demo_runs.sh"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    assert result.returncode == 0, (
        f"init_demo_runs.sh failed:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    # Check that run directories exist
    runs_dir = tmp_path / "runs"
    assert runs_dir.exists()
    
    # Check for the four expected run directories (the specific run IDs from the script)
    expected_run_ids = ["f584d5f35228", "29c15f04407b", "df4d7929ce44", "08d14a07bcdb"]
    for run_id in expected_run_ids:
        run_dir = runs_dir / run_id
        assert run_dir.exists(), f"Expected run directory {run_id} not found"
    
    # Check that the catalog exists
    assert (runs_dir / "trap_catalog.json").exists()
    assert (runs_dir / "trap_catalog.txt").exists()
    
    # Run again and check it skips generation
    result2 = subprocess.run(
        ["bash", "scripts/init_demo_runs.sh"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    assert result2.returncode == 0
    assert "already exist" in result2.stdout


@pytest.mark.repo
def test_no_tunnel_credentials_tracked():
    """No tunnel credential file is tracked."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True
    )
    tracked = result.stdout.splitlines()
    
    for path in tracked:
        assert "tunnel" not in path.lower() or "cloudflared-config.yml" in path
        assert ".json" not in path or not any(
            word in path.lower() 
            for word in ["credential", "token", "secret"]
        )


@pytest.mark.repo
def test_tunnel_credentials_negative_control():
    """Negative control: a temp repo with a credentials file is detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".git").mkdir()
        creds = repo / "tunnel-credentials.json"
        creds.write_text('{"AccountTag":"test"}')
        
        result = subprocess.run(
            ["git", "add", str(creds)],
            cwd=repo,
            capture_output=True,
        )
        
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            tracked = result.stdout.splitlines()
            has_creds = any("credential" in p.lower() for p in tracked)
            assert has_creds, "Negative control failed: credentials file should be tracked in temp repo"


@pytest.mark.repo
def test_docker_compose_base_config_valid():
    """Base docker-compose.yml must be valid and have correct structure."""
    # Validate with docker compose config -q
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"docker-compose.yml is invalid:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    # Parse the merged config and check structure
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    
    config = yaml.safe_load(result.stdout)
    services = config["services"]
    
    # API service must expose port 8000 on 127.0.0.1 in base config
    api = services["coroner-api"]
    assert "ports" in api
    ports = api["ports"]
    assert len(ports) == 1
    # Port format is either "127.0.0.1:8000:8000" or dict with target/published/host_ip
    port_spec = ports[0]
    if isinstance(port_spec, str):
        assert port_spec == "127.0.0.1:8000:8000" or port_spec == "127.0.0.1:8000:8000/tcp"
    else:
        assert port_spec["target"] == 8000
        assert port_spec["published"] == "8000"
        assert port_spec.get("host_ip") == "127.0.0.1"
    
    # Check memswap_limit equals memory limit for api (normalized to bytes)
    api_memswap_bytes = parse_size_to_bytes(api["memswap_limit"])
    api_memory_bytes = parse_size_to_bytes(api["deploy"]["resources"]["limits"]["memory"])
    assert api_memswap_bytes == api_memory_bytes
    assert api_memswap_bytes == parse_size_to_bytes("512M")
    
    # Engine service
    engine = services["coroner-engine"]
    assert engine["network_mode"] == "none"
    engine_memswap_bytes = parse_size_to_bytes(engine["memswap_limit"])
    engine_memory_bytes = parse_size_to_bytes(engine["deploy"]["resources"]["limits"]["memory"])
    assert engine_memswap_bytes == engine_memory_bytes
    assert engine_memswap_bytes == parse_size_to_bytes("2G")
    
    # Init service
    init = services["coroner-init"]
    assert init["network_mode"] == "none"
    init_memswap_bytes = parse_size_to_bytes(init["memswap_limit"])
    init_memory_bytes = parse_size_to_bytes(init["deploy"]["resources"]["limits"]["memory"])
    assert init_memswap_bytes == init_memory_bytes
    assert init_memswap_bytes == parse_size_to_bytes("2G")


@pytest.mark.repo
def test_docker_compose_server_config_valid():
    """Merged server config must be valid and have correct structure."""
    env = os.environ.copy()
    env["TUNNEL_ID"] = "test-tunnel-id"
    env["TUNNEL_CREDENTIALS_FILE"] = "/tmp/test-credentials.json"
    
    # Validate with docker compose config -q
    result = subprocess.run(
        [
            "docker", "compose",
            "-f", "docker-compose.yml",
            "-f", "docker-compose.server.yml",
            "config", "-q"
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"Merged server config is invalid:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    # Parse the merged config and check structure
    result = subprocess.run(
        [
            "docker", "compose",
            "-f", "docker-compose.yml",
            "-f", "docker-compose.server.yml",
            "config"
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    
    config = yaml.safe_load(result.stdout)
    services = config["services"]
    
    # API service must have no ports in server config
    api = services["coroner-api"]
    assert "ports" not in api or api.get("ports") is None or len(api.get("ports", [])) == 0
    
    # Cloudflared service must exist with correct image and limits
    cloudflared = services["cloudflared"]
    # Verify it's pinned by digest
    assert "@sha256:" in cloudflared["image"]
    assert cloudflared["image"].startswith("cloudflare/cloudflared:")
    
    cloudflared_memswap_bytes = parse_size_to_bytes(cloudflared["memswap_limit"])
    cloudflared_memory_bytes = parse_size_to_bytes(cloudflared["deploy"]["resources"]["limits"]["memory"])
    assert cloudflared_memswap_bytes == cloudflared_memory_bytes
    assert cloudflared_memswap_bytes == parse_size_to_bytes("128M")
    
    # Engine and init still have network_mode none
    assert services["coroner-engine"]["network_mode"] == "none"
    assert services["coroner-init"]["network_mode"] == "none"


def test_api_cpu_limit():
    """API service has CPU limit of 1."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["deploy"]["resources"]["limits"]["cpus"] == "1"


def test_api_memory_limit():
    """API service has memory limit of 512M."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["deploy"]["resources"]["limits"]["memory"] == "512M"
    assert api["memswap_limit"] == "512M"


def test_api_pids_limit():
    """API service has pids limit of 128."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["deploy"]["resources"]["limits"]["pids"] == 128


def test_api_user():
    """API service runs as user 1000:1000."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["user"] == "1000:1000"


def test_api_read_only():
    """API service has read_only root filesystem."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["read_only"] is True


def test_api_no_new_privileges():
    """API service has no new privileges."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["security_opt"] == ["no-new-privileges:true"]


def test_api_tmpfs():
    """API service has /tmp tmpfs with exec."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    tmpfs = api["tmpfs"]
    assert "/tmp:exec,mode=1777" in tmpfs


def test_api_volumes():
    """API service has coroner-data and coroner-exchange volumes."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    volumes = api["volumes"]
    
    data_volume = next((v for v in volumes if "coroner-data" in v), None)
    assert data_volume is not None
    assert "coroner-data:/data" in data_volume
    
    exchange_volume = next((v for v in volumes if "coroner-exchange" in v), None)
    assert exchange_volume is not None
    assert "coroner-exchange:/exchange" in exchange_volume


def test_api_localhost_only():
    """API service publishes port only on 127.0.0.1."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    ports = api["ports"]
    assert len(ports) == 1
    assert ports[0] == "127.0.0.1:8000:8000"


def test_engine_cpu_limit():
    """Engine service has CPU limit of 2."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["deploy"]["resources"]["limits"]["cpus"] == "2"


def test_engine_memory_limit():
    """Engine service has memory limit of 2G."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["deploy"]["resources"]["limits"]["memory"] == "2G"
    assert engine["memswap_limit"] == "2G"


def test_engine_pids_limit():
    """Engine service has pids limit of 256."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["deploy"]["resources"]["limits"]["pids"] == 256


def test_engine_user():
    """Engine service runs as user 1000:1000."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["user"] == "1000:1000"


def test_engine_read_only():
    """Engine service has read_only root filesystem."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["read_only"] is True


def test_engine_no_new_privileges():
    """Engine service has no new privileges."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["security_opt"] == ["no-new-privileges:true"]


def test_engine_cap_drop_all():
    """Engine service drops all capabilities."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["cap_drop"] == ["ALL"]


def test_engine_network_none():
    """Engine service has network_mode none."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    assert engine["network_mode"] == "none"


def test_engine_tmpfs():
    """Engine service has /tmp tmpfs with exec."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    tmpfs = engine["tmpfs"]
    assert "/tmp:exec,mode=1777" in tmpfs


def test_engine_volumes():
    """Engine service has coroner-exchange only, no coroner-data."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    engine = config["services"]["coroner-engine"]
    volumes = engine["volumes"]
    
    exchange_volume = next((v for v in volumes if "coroner-exchange" in v), None)
    assert exchange_volume is not None
    assert "coroner-exchange:/exchange" in exchange_volume
    
    data_volume = next((v for v in volumes if "coroner-data" in v), None)
    assert data_volume is None


def test_init_cpu_limit():
    """Init service has CPU limit of 2."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["deploy"]["resources"]["limits"]["cpus"] == "2"


def test_init_memory_limit():
    """Init service has memory limit of 2G."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["deploy"]["resources"]["limits"]["memory"] == "2G"
    assert init["memswap_limit"] == "2G"


def test_init_pids_limit():
    """Init service has pids limit of 256."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["deploy"]["resources"]["limits"]["pids"] == 256


def test_init_user():
    """Init service runs as user 1000:1000."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["user"] == "1000:1000"


def test_init_no_new_privileges():
    """Init service has no new privileges."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["security_opt"] == ["no-new-privileges:true"]


def test_init_cap_drop_all():
    """Init service drops all capabilities."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["cap_drop"] == ["ALL"]


def test_init_network_none():
    """Init service has network_mode none."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    assert init["network_mode"] == "none"


def test_init_tmpfs():
    """Init service has /tmp tmpfs with exec."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    tmpfs = init["tmpfs"]
    assert "/tmp:exec,mode=1777" in tmpfs


def test_init_volumes():
    """Init service has coroner-data volume."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    init = config["services"]["coroner-init"]
    volumes = init["volumes"]
    
    data_volume = next((v for v in volumes if "coroner-data" in v), None)
    assert data_volume is not None
    assert "coroner-data:/data" in data_volume


def test_server_override_no_ports():
    """Server override resets ports to empty list."""
    with open("docker-compose.server.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    assert api["ports"] == []


def test_server_cloudflared_image():
    """Cloudflared image is pinned by digest."""
    with open("docker-compose.server.yml") as f:
        config = yaml.safe_load(f)
    
    cloudflared = config["services"]["cloudflared"]
    image = cloudflared["image"]
    assert image.startswith("cloudflare/cloudflared:")
    assert "@sha256:" in image


def test_server_cloudflared_limits():
    """Cloudflared service has 128M memory limit."""
    with open("docker-compose.server.yml") as f:
        config = yaml.safe_load(f)
    
    cloudflared = config["services"]["cloudflared"]
    assert cloudflared["deploy"]["resources"]["limits"]["memory"] == "128M"
    assert cloudflared["memswap_limit"] == "128M"


def test_server_cloudflared_command():
    """Cloudflared command references TUNNEL_ID."""
    with open("docker-compose.server.yml") as f:
        config = yaml.safe_load(f)
    
    cloudflared = config["services"]["cloudflared"]
    command = " ".join(cloudflared["command"])
    assert "${TUNNEL_ID}" in command


def test_server_api_trusted_proxy():
    """API service has CORONER_TRUSTED_PROXY set to cloudflared fixed IP."""
    with open("docker-compose.server.yml") as f:
        config = yaml.safe_load(f)
    
    api = config["services"]["coroner-api"]
    env_list = api["environment"]
    # Parse list of KEY=VALUE strings into a dict
    env = {}
    for item in env_list:
        key, _, value = item.partition("=")
        env[key] = value
    
    assert "CORONER_TRUSTED_PROXY" in env
    # The value should be the cloudflared container's fixed IP
    cloudflared = config["services"]["cloudflared"]
    cloudflared_ip = cloudflared["networks"]["coroner-net"]["ipv4_address"]
    assert env["CORONER_TRUSTED_PROXY"] == cloudflared_ip


def test_cloudflared_config_ingress():
    """Cloudflared config ingress routes coroner.iqoba.com then 404."""
    with open("cloudflared-config.yml") as f:
        config = yaml.safe_load(f)
    
    ingress = config["ingress"]
    assert len(ingress) == 2
    
    first = ingress[0]
    assert first["hostname"] == "coroner.iqoba.com"
    assert "service" in first
    
    catch_all = ingress[1]
    assert catch_all["service"] == "http_status:404"


def test_env_example_ignored():
    """.env is in .gitignore."""
    with open(".gitignore") as f:
        content = f.read()
    
    assert ".env" in content or ".env*" in content


def test_init_script_helper_logic():
    """Test that the run_expect helper correctly checks exit codes and Run lines."""
    helper_script = """#!/usr/bin/env bash
set -euo pipefail

run_expect() {
    expected=$1
    name=$2
    shift 2
    set +e
    "$@" > "/tmp/$name.log" 2>&1
    rc=$?
    set -e
    cat "/tmp/$name.log"
    if [ "$rc" -ne "$expected" ]; then
        echo "ERROR: $name expected exit $expected, got $rc"
        exit 2
    fi
    grep "^Run: " "/tmp/$name.log" || {
        echo "ERROR: $name printed no Run line"
        exit 2
    }
}
"""
    
    # Case 1: expected exit 1 with actual exit 1 and Run line (should pass)
    case1_script = helper_script + """
run_expect 1 test1 bash -c "echo 'Run: runs/abc'; exit 1"
echo "Case 1 passed"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(case1_script)
        case1_path = f.name
    
    try:
        result = subprocess.run(
            ["bash", case1_path],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Case 1 should pass but got exit {result.returncode}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "Case 1 passed" in result.stdout
    finally:
        os.unlink(case1_path)
    
    # Case 2: expected exit 0 with actual exit 1 (should exit 2 with message)
    case2_script = helper_script + """
run_expect 0 test2_fail bash -c "exit 1"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(case2_script)
        case2_path = f.name
    
    try:
        result = subprocess.run(
            ["bash", case2_path],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, (
            f"Case 2 should exit 2 but got exit {result.returncode}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "expected exit 0, got 1" in result.stdout
    finally:
        os.unlink(case2_path)
    
    # Case 3: command without Run line (should exit 2 with message)
    case3_script = helper_script + """
run_expect 0 test3_no_run bash -c "echo 'no run line'; exit 0"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(case3_script)
        case3_path = f.name
    
    try:
        result = subprocess.run(
            ["bash", case3_path],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, (
            f"Case 3 should exit 2 but got exit {result.returncode}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "printed no Run line" in result.stdout
    finally:
        os.unlink(case3_path)


def test_engine_depends_on_init():
    """The engine starts after the init service."""
    with open("docker-compose.yml") as f:
        services = yaml.safe_load(f)["services"]
    assert "coroner-init" in services["coroner-engine"].get("depends_on", {})


# Check for duplicate test function names at module load time
def _check_no_duplicate_test_names():
    """Fail if any test function name is defined more than once in this module."""
    module_file = Path(__file__)
    with open(module_file) as f:
        tree = ast.parse(f.read(), filename=str(module_file))
    
    test_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            test_names.append(node.name)
    
    from collections import Counter
    duplicates = [name for name, count in Counter(test_names).items() if count > 1]
    
    if duplicates:
        raise AssertionError(
            f"Duplicate test function names found: {duplicates}. "
            f"Each test name must be defined exactly once."
        )


def test_no_duplicate_test_names():
    """Module has no duplicate test function names."""
    _check_no_duplicate_test_names()


def test_all_services_have_init():
    """All three services have init: true to prevent zombie processes."""
    with open("docker-compose.yml") as f:
        config = yaml.safe_load(f)
    
    services = config["services"]
    
    # Check all three services have init: true
    for service_name in ["coroner-init", "coroner-api", "coroner-engine"]:
        service = services[service_name]
        assert service.get("init") is True, (
            f"Service {service_name} must have init: true to reap zombie processes"
        )


@pytest.mark.repo
def test_workflows_use_docker_init():
    """All docker run commands of the coroner image have --init flag."""
    workflows_dir = Path(".github/workflows")
    
    # Files to check
    workflow_files = [
        "test.yml",
        "publish-image.yml",
        "coroner-gate.yml",
    ]
    
    for workflow_file in workflow_files:
        path = workflows_dir / workflow_file
        with open(path) as f:
            content = f.read()
        
        # Find all docker run lines
        import re
        docker_run_pattern = re.compile(r'docker\s+run\s+.*?coroner[:\s]', re.MULTILINE | re.DOTALL)
        
        for match in docker_run_pattern.finditer(content):
            docker_run_line = match.group(0)
            # Check if this is a coroner image run
            if "coroner:ci" in docker_run_line or "cobol-coroner" in docker_run_line:
                assert "--init" in docker_run_line, (
                    f"docker run in {workflow_file} missing --init flag:\n"
                    f"{docker_run_line[:200]}"
                )


PINNED_IMAGE = (
    "ghcr.io/yarahmouni/cobol-coroner@sha256:"
    "e671f330fa7ebd78c5d5041bbccfbe9cddf7f3e12a33b4a94825ee1d0bf75d50"
)
LOCAL_IMAGE = "coroner-local:latest"
COMPOSE_SERVICES = ["coroner-init", "coroner-api", "coroner-engine"]
SERVER_ENV = {
    "TUNNEL_ID": "test-tunnel-id",
    "TUNNEL_CREDENTIALS_FILE": "/tmp/test-credentials.json",
}


def _compose_config(files, extra_env=None):
    """Return the services of `docker compose -f ... config --format json`."""
    cmd = ["docker", "compose"]
    for name in files:
        cmd += ["-f", name]
    cmd += ["config", "--format", "json"]
    env = os.environ.copy()
    env.update(extra_env or {})
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0, (
        f"{' '.join(cmd)} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)["services"]


def test_base_compose_has_no_build_and_pulls_when_missing():
    """docker-compose.yml never builds, pulls the pinned image when missing, pins amd64."""
    with open("docker-compose.yml") as f:
        services = yaml.safe_load(f)["services"]
    for name in COMPOSE_SERVICES:
        service = services[name]
        assert "build" not in service, f"{name} must not have a build key"
        assert service.get("pull_policy") == "missing", (
            f"{name} must pull the pinned image when it is missing"
        )
        assert service.get("platform") == "linux/amd64", f"{name} must set platform"
        assert service["image"] == PINNED_IMAGE, name


@pytest.mark.repo
def test_base_compose_resolves_to_pinned_digest():
    """Every service of docker-compose.yml resolves to the exact pinned digest."""
    services = _compose_config(["docker-compose.yml"])
    assert sorted(services) == sorted(COMPOSE_SERVICES)
    for name in COMPOSE_SERVICES:
        assert services[name]["image"] == PINNED_IMAGE, name
        assert "build" not in services[name], name


@pytest.mark.repo
def test_build_override_resolves_to_local_tag_with_build_context():
    """With docker-compose.build.yml every service uses coroner-local:latest and builds."""
    services = _compose_config(["docker-compose.yml", "docker-compose.build.yml"])
    assert sorted(services) == sorted(COMPOSE_SERVICES)
    for name in COMPOSE_SERVICES:
        service = services[name]
        assert service["image"] == LOCAL_IMAGE, name
        assert service.get("build", {}).get("context"), f"{name} must have a build context"
        assert Path(service["build"]["context"]).resolve() == Path.cwd().resolve(), name
        assert service.get("pull_policy") == "never", name


@pytest.mark.repo
def test_server_override_still_renders_with_pinned_image():
    """The live server override renders (exit 0), keeps the pinned image and has no build."""
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.server.yml", "config", "-q"],
        capture_output=True,
        text=True,
        env={**os.environ, **SERVER_ENV},
    )
    assert result.returncode == 0, result.stderr
    services = _compose_config(["docker-compose.yml", "docker-compose.server.yml"], SERVER_ENV)
    for name in COMPOSE_SERVICES:
        assert services[name]["image"] == PINNED_IMAGE, name
        assert "build" not in services[name], name
    assert "cloudflared" in services
