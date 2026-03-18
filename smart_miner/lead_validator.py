"""
Strict Validation Layer - SN71 Schema Enforcement
==================================================

Enforces ALL SN71 schema rules before submission to prevent rejections.

Validation Checks:
1. Required fields (email, business, full_name, first, last, etc.)
2. Email format + pattern validation
3. Location rules (US vs non-US)
4. Industry taxonomy validation
5. Employee count format
6. LinkedIn URL format
7. Role sanity checks
8. Description sanity checks
9. Duplicate detection (email, LinkedIn combo)

Rejects leads BEFORE submission to avoid hitting rejection cap.
"""

import re
import logging
from typing import Dict, Tuple, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Valid employee count ranges
VALID_EMPLOYEE_COUNTS = [
    "0-1", "2-10", "11-50", "51-200", "201-500", "501-1,000",
    "1,001-5,000", "5,001-10,000", "10,001+"
]

# Also accept without commas
VALID_EMPLOYEE_COUNTS_NO_COMMAS = [ec.replace(',', '') for ec in VALID_EMPLOYEE_COUNTS]


def validate_required_fields(lead: Dict) -> Tuple[bool, Optional[str]]:
    """
    Check all required fields are present.
    
    Required fields per SN71:
    - email, business, full_name, first, last
    - website, industry, sub_industry
    - country, city
    - state (for US leads only)
    - role, linkedin, company_linkedin
    - source_url, description, employee_count
    """
    required = [
        'email', 'business', 'full_name', 'first', 'last',
        'website', 'industry', 'sub_industry',
        'country', 'city',
        'role', 'linkedin', 'company_linkedin',
        'source_url', 'description', 'employee_count'
    ]
    
    missing = [field for field in required if not lead.get(field, '').strip()]
    
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    
    return True, None


def validate_email_format(email: str) -> Tuple[bool, Optional[str]]:
    """Validate email format."""
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    return True, None


def validate_location(lead: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate location fields based on US vs non-US rules.
    
    Rules:
    - US leads: require country, state, AND city
    - Non-US leads: require country and city (state optional)
    """
    country = lead.get('country', '').strip()
    state = lead.get('state', '').strip()
    city = lead.get('city', '').strip()
    
    if not country:
        return False, "country is required"
    
    if not city:
        return False, "city is required"
    
    # Check if US
    us_aliases = ['united states', 'usa', 'us', 'u.s.', 'u.s.a.']
    is_us = country.lower() in us_aliases
    
    if is_us:
        if not state:
            return False, "state is required for US leads"
    
    return True, None


def validate_industry_taxonomy(lead: Dict, *, use_gateway_checks: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate industry and sub_industry against taxonomy.
    
    Uses validator_models.industry_taxonomy for validation.
    """
    industry = lead.get('industry', '').strip()
    sub_industry = lead.get('sub_industry', '').strip()
    
    if not industry:
        return False, "industry is required"
    
    if not sub_industry:
        return False, "sub_industry is required"
    
    # Prefer local taxonomy to avoid importing gateway (which may emit unicode/ANSI on Windows).
    try:
        from validator_models.industry_taxonomy import INDUSTRY_TAXONOMY
        if sub_industry not in INDUSTRY_TAXONOMY:
            return False, f"sub_industry '{sub_industry}' not in taxonomy"
        valid_parents = set(INDUSTRY_TAXONOMY[sub_industry].get("industries", []))
        if industry not in valid_parents:
            return False, f"industry '{industry}' invalid for sub_industry '{sub_industry}' (valid: {sorted(valid_parents)})"
    except Exception:
        # Optional: use gateway check if requested.
        if use_gateway_checks:
            try:
                from gateway.api.submit import check_industry_taxonomy
                error_code, error_msg = check_industry_taxonomy(industry, sub_industry)
                if error_code:
                    return False, error_msg
            except Exception:
                pass
        # Fallback: basic check
        if len(industry) < 2:
            return False, "industry too short"
        if len(sub_industry) < 2:
            return False, "sub_industry too short"
    
    return True, None


def validate_employee_count(employee_count: str) -> Tuple[bool, Optional[str]]:
    """Validate employee_count format."""
    if not employee_count:
        return False, "employee_count is required"
    
    employee_count = employee_count.strip()
    
    if employee_count not in VALID_EMPLOYEE_COUNTS and employee_count not in VALID_EMPLOYEE_COUNTS_NO_COMMAS:
        return False, f"Invalid employee_count: '{employee_count}'. Must be one of: {', '.join(VALID_EMPLOYEE_COUNTS)}"
    
    return True, None


def validate_linkedin_urls(lead: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate LinkedIn URL formats.
    
    Rules:
    - linkedin: Personal profile (format: https://linkedin.com/in/username)
    - company_linkedin: Company page (format: https://linkedin.com/company/companyname)
    """
    linkedin = lead.get('linkedin', '').strip()
    company_linkedin = lead.get('company_linkedin', '').strip()
    
    if not linkedin:
        return False, "linkedin is required"
    
    if not company_linkedin:
        return False, "company_linkedin is required"
    
    # Check personal LinkedIn format
    if not re.match(r'^https?://(www\.)?linkedin\.com/in/[^/]+/?$', linkedin, re.IGNORECASE):
        return False, f"Invalid linkedin URL format: {linkedin}"
    
    # Check company LinkedIn format
    if not re.match(r'^https?://(www\.)?linkedin\.com/company/[^/]+/?$', company_linkedin, re.IGNORECASE):
        return False, f"Invalid company_linkedin URL format: {company_linkedin}"
    
    return True, None


def validate_role(lead: Dict, *, use_gateway_checks: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate role format using gateway role sanity checks.
    """
    role = lead.get('role', '').strip()
    
    if not role:
        return False, "role is required"
    
    if use_gateway_checks:
        try:
            from gateway.api.submit import check_role_sanity
            error_code, error_msg = check_role_sanity(
                role,
                full_name=lead.get('full_name', ''),
                company=lead.get('business', ''),
                city=lead.get('city', ''),
                state=lead.get('state', ''),
                country=lead.get('country', ''),
                industry=lead.get('industry', '')
            )
            if error_code:
                return False, f"Role validation failed: {error_msg}"
            return True, None
        except Exception:
            # fall through to basic checks
            pass

    # Basic checks (safe, local-only)
    if len(role) < 3:
        return False, "role too short (minimum 3 characters)"
    if len(role) > 80:
        return False, "role too long (maximum 80 characters)"
    if not any(c.isalpha() for c in role):
        return False, "role must contain letters"
    
    return True, None


def validate_description(lead: Dict, *, use_gateway_checks: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate description format using gateway description sanity checks.
    """
    description = lead.get('description', '').strip()
    
    if not description:
        return False, "description is required"
    
    if use_gateway_checks:
        try:
            from gateway.api.submit import check_description_sanity
            error_code, error_msg = check_description_sanity(description)
            if error_code:
                return False, f"Description validation failed: {error_msg}"
            return True, None
        except Exception:
            # fall through to basic checks
            pass

    # Basic checks (safe, local-only)
    if len(description) < 20:
        return False, "description too short (minimum 20 characters)"
    if len(description) > 2000:
        return False, "description too long (maximum 2000 characters)"
    
    return True, None


def validate_source_url(lead: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate source_url.
    
    Rules:
    - Must be present
    - Cannot be LinkedIn URL
    - Must be valid URL format or "proprietary_database"
    """
    source_url = lead.get('source_url', '').strip()
    source_type = lead.get('source_type', '').strip()
    
    if not source_url:
        return False, "source_url is required"
    
    # LinkedIn not allowed
    if 'linkedin.com' in source_url.lower():
        return False, "LinkedIn URLs not allowed as source_url"
    
    # Check proprietary_database case
    if source_url.lower() == "proprietary_database":
        if source_type and source_type.lower() != "proprietary_database":
            return False, "source_url is 'proprietary_database' but source_type doesn't match"
        return True, None
    
    # Validate URL format
    url_pattern = r'^https?://[^\s]+$'
    if not re.match(url_pattern, source_url):
        # Try adding https://
        if not source_url.startswith(('http://', 'https://')):
            source_url_normalized = f"https://{source_url}"
            if not re.match(url_pattern, source_url_normalized):
                return False, "Invalid source_url format"
        else:
            return False, "Invalid source_url format"
    
    return True, None


def validate_lead(lead: Dict, *, use_gateway_checks: bool = True) -> Tuple[bool, Optional[str], List[str]]:
    """
    Comprehensive lead validation.
    
    Returns:
        (is_valid, error_message, rejection_reasons)
        - is_valid: True if all checks pass
        - error_message: Main error if invalid
        - rejection_reasons: List of all rejection reasons (for logging)
    """
    rejection_reasons = []
    
    # Run all validations
    validators = [
        ("required_fields", validate_required_fields),
        ("email_format", lambda l: validate_email_format(l.get('email', ''))),
        ("location", validate_location),
        ("industry_taxonomy", lambda l: validate_industry_taxonomy(l, use_gateway_checks=use_gateway_checks)),
        ("employee_count", lambda l: validate_employee_count(l.get('employee_count', ''))),
        ("linkedin_urls", validate_linkedin_urls),
        ("role", lambda l: validate_role(l, use_gateway_checks=use_gateway_checks)),
        ("description", lambda l: validate_description(l, use_gateway_checks=use_gateway_checks)),
        ("source_url", validate_source_url),
    ]
    
    for name, validator in validators:
        try:
            is_valid, error_msg = validator(lead)
            if not is_valid:
                rejection_reasons.append(f"{name}: {error_msg}")
        except Exception as e:
            rejection_reasons.append(f"{name}: Validation error - {str(e)}")
    
    if rejection_reasons:
        main_error = rejection_reasons[0]
        return False, main_error, rejection_reasons
    
    return True, None, []


async def check_duplicates(lead: Dict, wallet) -> Tuple[bool, Optional[str]]:
    """
    Check for duplicate email and LinkedIn combo.
    
    Uses cloud_db functions to check against existing submissions.
    """
    email = lead.get('email', '').strip()
    linkedin = lead.get('linkedin', '').strip()
    company_linkedin = lead.get('company_linkedin', '').strip()
    
    if not email:
        return False, "No email to check duplicates"
    
    try:
        from Leadpoet.utils.cloud_db import (
            check_email_duplicate,
            check_linkedin_combo_duplicate
        )
        
        # Check email duplicate
        if check_email_duplicate(email):
            return False, f"Duplicate email: {email}"
        
        # Check LinkedIn combo duplicate
        if linkedin and company_linkedin:
            if check_linkedin_combo_duplicate(linkedin, company_linkedin):
                return False, f"Duplicate LinkedIn combo: {linkedin} + {company_linkedin}"
        
        return True, None
    except ImportError:
        # If cloud_db not available, skip duplicate check
        logger.warning("cloud_db not available - skipping duplicate check")
        return True, None
    except Exception as e:
        logger.warning(f"Duplicate check error: {e}")
        return True, None  # Don't block on duplicate check errors
