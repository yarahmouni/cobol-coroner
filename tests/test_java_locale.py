"""Tests for Java locale determinism."""
import pytest
import subprocess
import tempfile
import json
from pathlib import Path

from coroner.run import JAVA_LOCALE, JAVA_LOCALE_PROPERTIES, JAVAC_ENCODING, run_java, compile_java
from coroner.cli import run_verify
from coroner.certificate import generate_certificate, replay_certificate


def test_java_locale_constant_matches_properties():
    """
    Test that JAVA_LOCALE constant matches the properties built from it.
    """
    assert JAVA_LOCALE == "en_US"
    
    # Check that properties are derived from JAVA_LOCALE
    assert "-Duser.language=en" in JAVA_LOCALE_PROPERTIES
    assert "-Duser.country=US" in JAVA_LOCALE_PROPERTIES
    assert "-Duser.variant=" in JAVA_LOCALE_PROPERTIES
    assert "-Dfile.encoding=UTF-8" in JAVA_LOCALE_PROPERTIES


def test_kiro_fresh_port_alive_with_locale_fix(tmp_path):
    """
    Test that the kiro-fresh port (which uses String.format with locale-sensitive
    formatting) gives ALIVE on this machine with the locale fix.
    
    Before the fix, on macOS with French locale (user.language=fr), this port
    produced decimal commas ("+009723,98") and was ZOMBIE on 2000 of 2000.
    With the fix (explicit en_US locale), it should be ALIVE.
    
    Audits samples/independence/ports/kiro-fresh/MatchMerge.java against
    samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob at 200 cases, seed 42.
    """
    verdict, run_dir = run_verify(
        cobol_path="samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
        java_path="samples/independence/ports/kiro-fresh/MatchMerge.java",
        schema_path="samples/traps/T1-ebcdic-match-merge/schema.json",
        copybooks_dir="samples/traps/T1-ebcdic-match-merge/copybooks",
        num_cases=200,
        seed=42,
        timings=False,
        base_dir=str(tmp_path)
    )
    
    # With the locale fix, the kiro-fresh port should be ALIVE
    # (before the fix, on French locale Mac: ZOMBIE 200 of 200)
    assert verdict.status == "ALIVE", (
        f"Expected ALIVE but got {verdict.status}. "
        f"The kiro-fresh port uses String.format which is locale-sensitive. "
        f"With explicit en_US locale, it should produce period decimals and be ALIVE."
    )
    assert verdict.cases_divergent == 0


def test_java_command_contains_locale_properties():
    """
    Test that the Java command line built by the engine contains
    the four locale properties by running a program that reads them.
    """
    # Create a minimal Java program that writes properties to output CSV
    with tempfile.TemporaryDirectory() as temp_dir:
        java_source = Path(temp_dir) / "LocaleTest.java"
        java_source.write_text("""
import java.io.*;

public class LocaleTest {
    public static void main(String[] args) throws IOException {
        String outputFile = System.getenv("OUTPUT_FILE");
        if (outputFile == null) {
            System.err.println("OUTPUT_FILE not set");
            System.exit(1);
        }
        try (PrintWriter out = new PrintWriter(new FileWriter(outputFile))) {
            out.println("PROPERTY,VALUE");
            out.println("user.language," + System.getProperty("user.language"));
            out.println("user.country," + System.getProperty("user.country"));
            out.println("user.variant," + System.getProperty("user.variant"));
            out.println("file.encoding," + System.getProperty("file.encoding"));
        }
    }
}
""")
        
        # Compile
        compile_java(str(java_source), temp_dir, temp_dir)
        
        # Create dummy input
        input_csv = Path(temp_dir) / "input.csv"
        input_csv.write_text("CASE-ID\n")
        output_csv = Path(temp_dir) / "output.csv"
        
        # Run
        result = run_java("LocaleTest", temp_dir, str(input_csv), str(output_csv), timeout=10.0)
        
        # Read the output CSV
        output_text = output_csv.read_text()
        
        # Verify the locale properties are set correctly
        assert "user.language,en" in output_text, f"Expected user.language=en in output, got: {output_text}"
        assert "user.country,US" in output_text, f"Expected user.country=US in output, got: {output_text}"
        # user.variant is empty string
        assert "user.variant," in output_text
        assert "file.encoding,UTF-8" in output_text, f"Expected file.encoding=UTF-8 in output, got: {output_text}"


def test_certificate_contains_java_locale(tmp_path):
    """
    Test that a newly generated certificate contains the java_locale field
    and that it matches JAVA_LOCALE constant.
    
    run_verify generates the certificate automatically, so we just need to
    check that the certificate file contains the field.
    """
    # Run a small T1 audit
    verdict, run_dir = run_verify(
        cobol_path="samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
        java_path="samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java",
        schema_path="samples/traps/T1-ebcdic-match-merge/schema.json",
        copybooks_dir="samples/traps/T1-ebcdic-match-merge/copybooks",
        num_cases=50,
        seed=42,
        timings=False,
        base_dir=str(tmp_path)
    )
    
    # Read certificate (run_verify already generated it)
    cert_path = run_dir / "certificate.json"
    with open(cert_path) as f:
        cert = json.load(f)
    
    assert "java_locale" in cert, "Certificate should contain java_locale field"
    assert cert["java_locale"] == JAVA_LOCALE, f"Expected java_locale={JAVA_LOCALE}, got {cert['java_locale']}"
    
    # Replay should be VALID
    replay_result = replay_certificate(str(cert_path), base_dir=str(tmp_path))
    assert replay_result.valid, f"Certificate replay should be VALID, got: {replay_result.reason}"


@pytest.mark.slow
def test_t1_correct_run_id_unchanged_with_locale(tmp_path):
    """
    Test that the run id of T1 correct audit at 2000 cases, seed 42
    is still 29c15f04407b (the bundled run id).
    
    The java_locale field is not part of the run id computation, so adding
    it to the certificate should not change run ids.
    """
    verdict, run_dir = run_verify(
        cobol_path="samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
        java_path="samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java",
        schema_path="samples/traps/T1-ebcdic-match-merge/schema.json",
        copybooks_dir="samples/traps/T1-ebcdic-match-merge/copybooks",
        num_cases=2000,
        seed=42,
        timings=False,
        base_dir=str(tmp_path)
    )
    
    # Extract run_id from run_dir path
    run_id = run_dir.name
    
    # The run id should be the bundled one
    assert run_id == "29c15f04407b", (
        f"Expected run id 29c15f04407b (bundled T1 correct run), got {run_id}. "
        "The locale field should not affect run id computation."
    )
