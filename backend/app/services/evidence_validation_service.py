"""
Evidence validation service - deterministic content checks.

This is NOT AI logic. Pure Python rules to detect:
- CAPTCHA/bot blocks
- Login/auth pages
- Invalid content (wrong document type)
- Valid evidence
"""


def validate_evidence(content: str, evidence_type: str, url: str) -> tuple[str, str | None]:
    """
    Validate fetched evidence content.

    Args:
        content: Fetched HTML/text content
        evidence_type: Expected type (API_DOCS, ROBOTS_TXT, etc.)
        url: URL that was fetched

    Returns:
        Tuple of (status, reason)
        Status: VALID, BLOCKED, AUTH_REQUIRED, INVALID_CONTENT
    """
    content_lower = content.lower()

    # 1. Detect CAPTCHA / bot blocking
    captcha_indicators = [
        "recaptcha",
        "captcha",
        "challengepage",
        "verify you are human",
        "unusual traffic",
        "access denied",
        "cloudflare",
        "are you a robot",
        "security check",
    ]

    for indicator in captcha_indicators:
        if indicator in content_lower:
            return ("BLOCKED", f"CAPTCHA/bot protection detected: '{indicator}'")

    # 2. Detect sign-in/login pages
    auth_indicators = [
        "sign in",
        "log in",
        "login required",
        "authenticate",
        "please login",
        "create account",
        "forgot password",
    ]

    for indicator in auth_indicators:
        if indicator in content_lower:
            return ("AUTH_REQUIRED", f"Authentication required: '{indicator}' found")

    # 3. Type-specific validation
    if evidence_type == "ROBOTS_TXT":
        return _validate_robots_txt(content)

    elif evidence_type == "API_DOCS":
        return _validate_api_docs(content)

    # Default: assume valid if no blocking detected
    return ("VALID", None)


def _validate_robots_txt(content: str) -> tuple[str, str | None]:
    """Validate robots.txt content."""
    required_keywords = ["user-agent:", "disallow:", "allow:", "sitemap:", "crawl-delay:"]

    content_lower = content.lower()

    # Check if it looks like robots.txt
    has_robots_syntax = any(keyword in content_lower for keyword in required_keywords)

    if not has_robots_syntax:
        # Check if it's HTML instead
        if "<html" in content_lower or "<!doctype" in content_lower:
            return ("INVALID_CONTENT", "Expected robots.txt but got HTML page")
        return ("INVALID_CONTENT", "Content doesn't match robots.txt format")

    return ("VALID", None)


def _validate_api_docs(content: str) -> tuple[str, str | None]:
    """Validate API documentation content."""
    content_lower = content.lower()

    # Look for API documentation indicators
    api_indicators = [
        "api",
        "rest",
        "endpoint",
        "authentication",
        "rate limit",
        "openapi",
        "sdk",
        "api reference",
        "api documentation",
        "developer",
        "getting started",
    ]

    matches = sum(1 for indicator in api_indicators if indicator in content_lower)

    if matches >= 3:
        # Likely real API docs
        return ("VALID", None)

    # Check if it's too short (less than 200 chars is suspicious)
    if len(content) < 200:
        return ("INVALID_CONTENT", "Content too short to be API documentation")

    # Check if it's mostly JavaScript/JSON (not rendered HTML)
    if content.strip().startswith("{") or content.strip().startswith("["):
        return ("INVALID_CONTENT", "Received JSON/API response instead of documentation")

    # Uncertain, but allow with low confidence
    return ("VALID", f"API indicators found: {matches}/11")
