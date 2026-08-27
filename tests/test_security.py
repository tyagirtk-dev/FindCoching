from app.security.url import safe_next_url


def test_safe_relative_url():
    assert safe_next_url("/student/dashboard") == "/student/dashboard"


def test_reject_absolute_url():
    assert safe_next_url("https://evil.example/") == "/"


def test_reject_protocol_relative_url():
    assert safe_next_url("//evil.example/") == "/"


def test_reject_non_relative_url():
    assert safe_next_url("evil.example/path") == "/"


def test_empty_uses_fallback():
    assert safe_next_url("", "/auth/login") == "/auth/login"


def test_control_character_rejected():
    assert safe_next_url("/foo\nbar") == "/"
