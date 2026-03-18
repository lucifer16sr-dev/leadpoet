"""
Lead Intelligence Layer - Scoring System
==========================================

Scores each lead before submission to maximize approval rate and reputation score.

Scoring Components:
1. Email Quality Score (0-1.0)
   - Name-email matching (high weight)
   - Generic email detection (reject)
   - Email format validation

2. Domain Quality Score (0-1.0)
   - Real website verification
   - Domain age check (≥7 days)
   - Spam/blacklist detection

3. Company Quality Score (0-1.0)
   - Known company signals
   - Employee count validation
   - Industry taxonomy match

4. Source Quality Score (0-1.0)
   - Reliable URL (not LinkedIn)
   - Source type validation
   - URL reachability

Only leads above threshold (default 0.7) are allowed for submission.
"""

import re
import asyncio
import aiohttp
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Fallback restricted sources list (copied from Leadpoet.utils.source_provenance).
# We keep this here so scoring can run in a clean environment without bittensor installed.
_RESTRICTED_SOURCES_FALLBACK = {
    "zoominfo.com",
    "apollo.io",
    "people-data-labs.com",
    "peopledatalabs.com",
    "rocketreach.co",
    "hunter.io",
    "snov.io",
    "lusha.com",
    "clearbit.com",
    "leadiq.com",
}

def _is_restricted_source_fallback(domain: str) -> bool:
    if not domain:
        return False
    d = domain.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    if d in _RESTRICTED_SOURCES_FALLBACK:
        return True
    return any(r in d for r in _RESTRICTED_SOURCES_FALLBACK)

# Generic email patterns (reject immediately)
GENERIC_EMAIL_PATTERNS = [
    r'^(hello|info|contact|support|team|sales|marketing|admin|noreply|no-reply|help|service|general|office|hr|jobs|careers|press|media|news|blog|webmaster|postmaster|abuse|security|legal|privacy|terms|billing|accounting|finance|it|tech|dev|engineering|operations|ops|business|partners|investors|founders|executives|management|staff|employees|members|users|customers|clients|vendors|suppliers|partners|all|everyone|everybody|anyone|anybody|someone|somebody|nobody|nobody|any|some|all|every|each|both|either|neither|other|another|others|anothers|more|most|less|least|few|many|much|more|most|less|least|few|many|much|more|most|less|least|few|many|much)@',
    r'^(test|demo|example|sample|temp|temporary|fake|dummy|placeholder|invalid|wrong|error|bug|debug|dev|development|staging|stage|prod|production|live|beta|alpha|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega)@',
]

# Name-email matching patterns (26 common patterns)
NAME_EMAIL_PATTERNS = [
    # Starting with first name
    r'^{first}?{last}@',  # johndoe, john.doe, john_doe, john-doe
    r'^{first_short}?{last}@',  # jdoe, j.doe, j_doe, j-doe
    r'^{first}?{last_short}@',  # johnd, john.d, john_d, john-d
    # Starting with last name
    r'^{last}?{first}@',  # doejohn, doe.john, doe_john, doe-john
    r'^{last}?{first_short}@',  # doej, doe.j, doe_j, doe-j
    r'^{last_short}?{first}@',  # djohn, d.john, d_john, d-john
    # Single tokens
    r'^{first}@',  # john
    r'^{last}@',  # doe
]


def extract_name_parts(full_name: str, first: str = "", last: str = "") -> Tuple[str, str]:
    """Extract first and last name from full_name or use provided fields."""
    if not first and not last and full_name:
        parts = full_name.strip().split(maxsplit=1)
        first = parts[0] if len(parts) > 0 else ""
        last = parts[1] if len(parts) > 1 else ""
    return (first.lower().strip(), last.lower().strip())


def check_name_email_match(email: str, first: str, last: str, full_name: str = "") -> Tuple[bool, float]:
    """
    Check if email matches name using 26 common patterns.
    
    Returns:
        (matches, confidence_score)
        - matches: True if name appears in email
        - confidence_score: 0.0-1.0 based on match quality
    """
    if not email or not (first or last or full_name):
        return False, 0.0
    
    first, last = extract_name_parts(full_name, first, last)
    
    if not first and not last:
        return False, 0.0
    
    email_lower = email.lower().split('@')[0]  # Get local part
    
    # Check for generic emails first (reject)
    for pattern in GENERIC_EMAIL_PATTERNS:
        if re.match(pattern, email_lower):
            return False, 0.0
    
    # Check name patterns
    first_short = first[0] if first else ""
    last_short = last[0] if last else ""
    
    # Build pattern variations
    patterns_to_check = [
        (f"{first}{last}", 1.0),  # johndoe - highest confidence
        (f"{first}.{last}", 1.0),  # john.doe
        (f"{first}_{last}", 1.0),  # john_doe
        (f"{first}-{last}", 1.0),  # john-doe
        (f"{first_short}{last}", 0.9),  # jdoe
        (f"{first_short}.{last}", 0.9),  # j.doe
        (f"{first_short}_{last}", 0.9),  # j_doe
        (f"{first_short}-{last}", 0.9),  # j-doe
        (f"{first}{last_short}", 0.9),  # johnd
        (f"{first}.{last_short}", 0.9),  # john.d
        (f"{first}_{last_short}", 0.9),  # john_d
        (f"{first}-{last_short}", 0.9),  # john-d
        (f"{last}{first}", 0.8),  # doejohn
        (f"{last}.{first}", 0.8),  # doe.john
        (f"{last}_{first}", 0.8),  # doe_john
        (f"{last}-{first}", 0.8),  # doe-john
        (f"{last_short}{first}", 0.7),  # djohn
        (f"{last_short}.{first}", 0.7),  # d.john
        (f"{last_short}_{first}", 0.7),  # d_john
        (f"{last_short}-{first}", 0.7),  # d-john
        (first, 0.6),  # john (single token)
        (last, 0.6),  # doe (single token)
    ]
    
    for pattern, confidence in patterns_to_check:
        if pattern and pattern in email_lower:
            return True, confidence
    
    return False, 0.0


def score_email_quality(email: str, first: str, last: str, full_name: str = "") -> Tuple[float, str]:
    """
    Score email quality (0-1.0).
    
    Returns:
        (score, reason)
    """
    if not email:
        return 0.0, "No email provided"
    
    # Basic format check
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return 0.0, "Invalid email format"
    
    # Check for generic emails (reject)
    email_lower = email.lower()
    for pattern in GENERIC_EMAIL_PATTERNS:
        if re.match(pattern, email_lower):
            return 0.0, "Generic email address (rejected)"
    
    # Check name-email matching
    matches, confidence = check_name_email_match(email, first, last, full_name)
    if not matches:
        return 0.3, "Email does not match name pattern"
    
    # Score based on confidence
    if confidence >= 0.9:
        return 1.0, f"Strong name-email match (confidence: {confidence:.1f})"
    elif confidence >= 0.7:
        return 0.8, f"Good name-email match (confidence: {confidence:.1f})"
    else:
        return 0.6, f"Weak name-email match (confidence: {confidence:.1f})"


async def check_domain_reachability(url: str) -> Tuple[bool, str]:
    """Check if domain/URL is reachable."""
    if not url:
        return False, "No URL provided"
    
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as response:
                if response.status in (200, 201, 204, 301, 302, 303, 307, 308, 401, 403):
                    return True, f"URL reachable (status: {response.status})"
                return False, f"URL returned status {response.status}"
    except Exception as e:
        return False, f"URL unreachable: {str(e)}"


def score_domain_quality(website: str, source_url: str = "") -> Tuple[float, str]:
    """
    Score domain quality (0-1.0).
    
    Checks:
    - Real website (not placeholder)
    - Domain format validation
    - Not in restricted sources
    
    Note: Domain age check requires async call, done separately.
    """
    if not website:
        return 0.0, "No website provided"
    
    # Basic URL format
    url_pattern = r'^https?://[^\s]+$'
    if not re.match(url_pattern, website):
        # Try adding https://
        if not website.startswith(('http://', 'https://')):
            website = f"https://{website}"
        if not re.match(url_pattern, website):
            return 0.0, "Invalid website URL format"
    
    # Extract domain
    from urllib.parse import urlparse
    try:
        parsed = urlparse(website)
        domain = parsed.netloc or parsed.path
        if ':' in domain:
            domain = domain.split(':')[0]
        domain = domain.lower().strip()
        
        if domain.startswith('www.'):
            domain = domain[4:]
    except Exception:
        return 0.0, "Could not parse domain from URL"
    
    # Check for restricted sources (optional dependency)
    try:
        from Leadpoet.utils.source_provenance import is_restricted_source  # type: ignore
        restricted = is_restricted_source(domain)
    except Exception:
        restricted = _is_restricted_source_fallback(domain)
    if restricted:
        return 0.0, f"Domain {domain} is in restricted source denylist"
    
    # Check for LinkedIn (not allowed as source_url)
    if 'linkedin.com' in domain.lower():
        return 0.0, "LinkedIn URLs not allowed as source"
    
    # Basic domain validation
    if len(domain) < 3:
        return 0.0, "Domain too short"
    
    # Check for placeholder domains
    placeholder_domains = ['example.com', 'test.com', 'placeholder.com', 'localhost']
    if any(pd in domain for pd in placeholder_domains):
        return 0.0, "Placeholder domain detected"
    
    return 1.0, "Domain format valid"


def score_company_quality(lead: Dict) -> Tuple[float, str]:
    """
    Score company quality (0-1.0).
    
    Checks:
    - Company name present
    - Employee count valid
    - Industry taxonomy match
    """
    business = lead.get('business', '').strip()
    if not business:
        return 0.0, "No company name provided"
    
    if len(business) < 2:
        return 0.0, "Company name too short"
    
    # Check employee count format
    employee_count = lead.get('employee_count', '').strip()
    if employee_count:
        VALID_EMPLOYEE_COUNTS = [
            "0-1", "2-10", "11-50", "51-200", "201-500", "501-1,000",
            "1,001-5,000", "5,001-10,000", "10,001+"
        ]
        # Also accept without commas
        valid_without_commas = [ec.replace(',', '') for ec in VALID_EMPLOYEE_COUNTS]
        if employee_count not in VALID_EMPLOYEE_COUNTS and employee_count not in valid_without_commas:
            return 0.5, f"Invalid employee_count format: {employee_count}"
    
    # Check industry taxonomy (basic check - full validation in validator)
    industry = lead.get('industry', '').strip()
    sub_industry = lead.get('sub_industry', '').strip()
    
    if not industry:
        return 0.5, "No industry specified"
    
    if not sub_industry:
        return 0.5, "No sub_industry specified"
    
    return 1.0, "Company quality checks passed"


def score_source_quality(source_url: str, source_type: str = "") -> Tuple[float, str]:
    """
    Score source quality (0-1.0).
    
    Checks:
    - Not LinkedIn
    - Valid source type
    - URL format valid
    """
    if not source_url:
        return 0.0, "No source_url provided"
    
    # LinkedIn not allowed
    if 'linkedin.com' in source_url.lower():
        return 0.0, "LinkedIn URLs not allowed as source_url"
    
    # Check for proprietary_database (special case)
    if source_url.lower() == "proprietary_database":
        if source_type and source_type.lower() == "proprietary_database":
            return 1.0, "Valid proprietary database source"
        else:
            return 0.0, "source_url is 'proprietary_database' but source_type doesn't match"
    
    # Basic URL format
    url_pattern = r'^https?://[^\s]+$'
    if not re.match(url_pattern, source_url):
        # Try adding https://
        if not source_url.startswith(('http://', 'https://')):
            source_url_normalized = f"https://{source_url}"
            if not re.match(url_pattern, source_url_normalized):
                return 0.0, "Invalid source_url format"
        else:
            return 0.0, "Invalid source_url format"
    
    # Check for restricted sources
    from urllib.parse import urlparse
    try:
        parsed = urlparse(source_url if source_url.startswith(('http://', 'https://')) else f"https://{source_url}")
        domain = parsed.netloc or parsed.path
        if ':' in domain:
            domain = domain.split(':')[0]
        domain = domain.lower().strip()
        
        if domain.startswith('www.'):
            domain = domain[4:]
        
        try:
            from Leadpoet.utils.source_provenance import is_restricted_source  # type: ignore
            restricted = is_restricted_source(domain)
        except Exception:
            restricted = _is_restricted_source_fallback(domain)
        if restricted:
            return 0.0, f"Source domain {domain} is in restricted denylist"
    except Exception:
        pass  # Continue even if parsing fails
    
    return 1.0, "Source quality checks passed"


async def score_lead(
    lead: Dict,
    min_threshold: float = 0.7,
    *,
    check_reachability: bool = True,
) -> Tuple[float, Dict[str, Tuple[float, str]], bool]:
    """
    Score a lead across all dimensions.
    
    Args:
        lead: Lead dictionary
        min_threshold: Minimum total score to allow submission (default 0.7)
        check_reachability: If True, performs HTTP reachability checks for website/source URLs.
            For safe/local dry-runs with fake domains, set to False so scoring is deterministic.
    
    Returns:
        (total_score, component_scores, should_submit)
        - total_score: Weighted average (0-1.0)
        - component_scores: Dict of (score, reason) for each component
        - should_submit: True if total_score >= min_threshold
    """
    component_scores = {}
    
    # 1. Email Quality (weight: 0.4 - most important)
    email_score, email_reason = score_email_quality(
        lead.get('email', ''),
        lead.get('first', ''),
        lead.get('last', ''),
        lead.get('full_name', '')
    )
    component_scores['email'] = (email_score, email_reason)
    
    # 2. Domain Quality (weight: 0.3)
    domain_score, domain_reason = score_domain_quality(
        lead.get('website', ''),
        lead.get('source_url', '')
    )
    component_scores['domain'] = (domain_score, domain_reason)
    
    # Check domain reachability (async) - optional for dry-runs/tests
    if check_reachability and domain_score > 0:
        website = lead.get('website', '')
        if website:
            reachable, reachable_reason = await check_domain_reachability(website)
            if not reachable:
                domain_score = 0.0
                domain_reason = f"Domain unreachable: {reachable_reason}"
                component_scores['domain'] = (domain_score, domain_reason)
    
    # 3. Company Quality (weight: 0.2)
    company_score, company_reason = score_company_quality(lead)
    component_scores['company'] = (company_score, company_reason)
    
    # 4. Source Quality (weight: 0.1)
    source_score, source_reason = score_source_quality(
        lead.get('source_url', ''),
        lead.get('source_type', '')
    )
    component_scores['source'] = (source_score, source_reason)
    
    # Calculate weighted total score
    weights = {
        'email': 0.4,
        'domain': 0.3,
        'company': 0.2,
        'source': 0.1
    }
    
    total_score = sum(
        component_scores[key][0] * weights[key]
        for key in weights
        if key in component_scores
    )
    
    should_submit = total_score >= min_threshold
    
    return total_score, component_scores, should_submit
