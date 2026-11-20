"""Tests for deploy_check.py verification logic."""
import pytest


def test_verify_check_exact_marker():
    """Test that check_verify looks for exact 'Certificate: VALID' marker."""
    from scripts.deploy_check import check_verify
    import httpx
    
    # Mock client and base_url
    class MockResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.headers = {}
    
    class MockClient:
        def __init__(self, response):
            self.response = response
        
        def post(self, url, **kwargs):
            return self.response
    
    # Test 1: Valid certificate (contains "Certificate: VALID")
    valid_html = '<div>Certificate: VALID</div><div>Status: ALIVE</div>'
    client = MockClient(MockResponse(200, valid_html))
    result = check_verify(client, "http://test", "abc123")
    assert result is True
    
    # Test 2: Invalid certificate (contains "Certificate: INVALID")
    # The bug was that "INVALID" contains "VALID" as substring
    invalid_html = '<div>Certificate: INVALID</div><div>replay mismatch</div>'
    client = MockClient(MockResponse(200, invalid_html))
    result = check_verify(client, "http://test", "abc123")
    assert result is False  # Should fail because it's INVALID


def test_tamper_check_exact_marker():
    """Test that check_tamper looks for exact markers."""
    from scripts.deploy_check import check_tamper
    import httpx
    
    class MockResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.headers = {}
    
    class MockClient:
        def __init__(self, responses):
            self.responses = responses
            self.call_count = 0
        
        def get(self, url, **kwargs):
            return self.responses[0]
        
        def post(self, url, **kwargs):
            result = self.responses[1]
            self.call_count += 1
            return result
    
    # Test: Tamper should find "Certificate: INVALID" and "replay mismatch"
    form_response = MockResponse(200, '<form></form>')
    tamper_response = MockResponse(200, '<div>Certificate: INVALID</div><div>replay mismatch (status: expected ALIVE, got ZOMBIE)</div>')
    
    client = MockClient([form_response, tamper_response])
    result = check_tamper(client, "http://test", "abc123")
    assert result is True
    
    # Test: Should fail if only "INVALID" without "Certificate:" prefix
    tamper_response_bad = MockResponse(200, '<div>INVALID</div>')
    client = MockClient([form_response, tamper_response_bad])
    result = check_tamper(client, "http://test", "abc123")
    assert result is False
