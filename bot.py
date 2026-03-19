"""
Smart Miner Assistant Bot
=========================

Acts as your assistant to evaluate leads before real mining.
Shows ALL smart miner criteria with detailed pass/fail logs.

This bot:
- Generates leads (using Lead Sorcerer)
- Scores leads (email, domain, company, source quality)
- Validates leads (SN71 schema rules)
- Shows detailed logs for EVERY criterion
- Does NOT submit to gateway (safe testing)

Usage:
    python bot.py [--num-leads N] [--industry INDUSTRY] [--region REGION] [--threshold SCORE]

Example:
    python bot.py --num-leads 5 --industry "Technology" --threshold 0.7
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Force UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import smart miner components
try:
    from smart_miner.lead_generator import generate_high_quality_leads
    from smart_miner.lead_scorer import (
        score_lead,
        score_email_quality,
        score_domain_quality,
        score_company_quality,
        score_source_quality,
        check_domain_reachability
    )
    from smart_miner.lead_validator import (
        validate_lead,
        validate_required_fields,
        validate_email_format,
        validate_location,
        validate_industry_taxonomy,
        validate_employee_count,
        validate_linkedin_urls,
        validate_role,
        validate_description,
        validate_source_url
    )
    SMART_MINER_AVAILABLE = True
except ImportError as e:
    print(f"❌ Failed to import smart miner components: {e}")
    print("   Make sure you're running from the project root directory")
    SMART_MINER_AVAILABLE = False


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    @staticmethod
    def pass_text(text: str) -> str:
        return f"{Colors.GREEN}✓ {text}{Colors.RESET}"
    
    @staticmethod
    def fail_text(text: str) -> str:
        return f"{Colors.RED}✗ {text}{Colors.RESET}"
    
    @staticmethod
    def warn_text(text: str) -> str:
        return f"{Colors.YELLOW}⚠ {text}{Colors.RESET}"
    
    @staticmethod
    def info_text(text: str) -> str:
        return f"{Colors.CYAN}ℹ {text}{Colors.RESET}"


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{char * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{char * 80}{Colors.RESET}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{Colors.CYAN}{'─' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 80}{Colors.RESET}\n")


def print_criterion(name: str, passed: bool, details: str, score: float = None):
    """Print a criterion check result."""
    status = Colors.pass_text("PASS") if passed else Colors.fail_text("FAIL")
    score_str = f" (score: {score:.2f})" if score is not None else ""
    print(f"  {status} {name}{score_str}")
    if details:
        indent = "    "
        print(f"{indent}{details}")


def print_lead_data(lead: Dict, index: int):
    """Print full generated lead data in a readable format."""
    print_section(f"📋 GENERATED LEAD DATA #{index}")
    
    # Basic Info
    print(f"\n{Colors.BOLD}Basic Information:{Colors.RESET}")
    print(f"  Business:      {lead.get('business', 'N/A')}")
    print(f"  Full Name:     {lead.get('full_name', 'N/A')}")
    print(f"  First Name:    {lead.get('first', 'N/A')}")
    print(f"  Last Name:     {lead.get('last', 'N/A')}")
    print(f"  Email:         {lead.get('email', 'N/A')}")
    print(f"  Role:          {lead.get('role', 'N/A')}")
    
    # Location
    print(f"\n{Colors.BOLD}Location:{Colors.RESET}")
    print(f"  Country:       {lead.get('country', 'N/A')}")
    print(f"  State:         {lead.get('state', 'N/A')}")
    print(f"  City:          {lead.get('city', 'N/A')}")
    
    # Company Details
    print(f"\n{Colors.BOLD}Company Details:{Colors.RESET}")
    print(f"  Website:       {lead.get('website', 'N/A')}")
    print(f"  Industry:      {lead.get('industry', 'N/A')}")
    print(f"  Sub-Industry:  {lead.get('sub_industry', 'N/A')}")
    print(f"  Employee Count: {lead.get('employee_count', 'N/A')}")
    
    # LinkedIn
    print(f"\n{Colors.BOLD}LinkedIn:{Colors.RESET}")
    print(f"  Person LI:     {lead.get('linkedin', 'N/A')}")
    print(f"  Company LI:    {lead.get('company_linkedin', 'N/A')}")
    
    # Source
    print(f"\n{Colors.BOLD}Source:{Colors.RESET}")
    print(f"  Source URL:    {lead.get('source_url', 'N/A')}")
    print(f"  Source Type:   {lead.get('source_type', 'N/A')}")
    
    # Description
    description = lead.get('description', '')
    if description:
        desc_preview = description[:200] + '...' if len(description) > 200 else description
        print(f"\n{Colors.BOLD}Description:{Colors.RESET}")
        print(f"  {desc_preview}")
    
    # Additional Fields
    additional_fields = []
    if lead.get('phone'):
        additional_fields.append(('Phone', lead.get('phone')))
    if lead.get('twitter'):
        additional_fields.append(('Twitter', lead.get('twitter')))
    if lead.get('github'):
        additional_fields.append(('GitHub', lead.get('github')))
    if lead.get('telegram'):
        additional_fields.append(('Telegram', lead.get('telegram')))
    
    if additional_fields:
        print(f"\n{Colors.BOLD}Additional Fields:{Colors.RESET}")
        for field_name, field_value in additional_fields:
            print(f"  {field_name}: {field_value}")
    
    # Show full JSON on request or for debugging
    print(f"\n{Colors.CYAN}Full JSON (for debugging):{Colors.RESET}")
    print(json.dumps(lead, indent=2, ensure_ascii=False))


def print_lead_data(lead: Dict, index: int):
    """Print full generated lead data in a readable format."""
    print(f"\n{Colors.BOLD}{'─' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}📋 GENERATED LEAD #{index}{Colors.RESET}")
    print(f"{Colors.BOLD}{'─' * 80}{Colors.RESET}")
    
    # Basic Info
    print(f"\n{Colors.CYAN}Basic Information:{Colors.RESET}")
    print(f"  Business:      {lead.get('business', 'N/A')}")
    print(f"  Full Name:     {lead.get('full_name', 'N/A')}")
    print(f"  First Name:    {lead.get('first', 'N/A')}")
    print(f"  Last Name:     {lead.get('last', 'N/A')}")
    print(f"  Email:         {lead.get('email', 'N/A')}")
    print(f"  Role:          {lead.get('role', 'N/A')}")
    
    # Location
    print(f"\n{Colors.CYAN}Location:{Colors.RESET}")
    print(f"  Country:       {lead.get('country', 'N/A')}")
    print(f"  State:         {lead.get('state', 'N/A')}")
    print(f"  City:          {lead.get('city', 'N/A')}")
    
    # Company Details
    print(f"\n{Colors.CYAN}Company Details:{Colors.RESET}")
    print(f"  Website:       {lead.get('website', 'N/A')}")
    print(f"  Industry:      {lead.get('industry', 'N/A')}")
    print(f"  Sub-Industry: {lead.get('sub_industry', 'N/A')}")
    print(f"  Employee Count: {lead.get('employee_count', 'N/A')}")
    
    # LinkedIn
    print(f"\n{Colors.CYAN}LinkedIn:{Colors.RESET}")
    print(f"  Person LI:     {lead.get('linkedin', 'N/A')}")
    print(f"  Company LI:    {lead.get('company_linkedin', 'N/A')}")
    
    # Source
    print(f"\n{Colors.CYAN}Source:{Colors.RESET}")
    print(f"  Source URL:    {lead.get('source_url', 'N/A')}")
    print(f"  Source Type:   {lead.get('source_type', 'N/A')}")
    
    # Description
    description = lead.get('description', '')
    if description:
        print(f"\n{Colors.CYAN}Description:{Colors.RESET}")
        # Show first 300 chars, then full in JSON
        desc_preview = description[:300] + '...' if len(description) > 300 else description
        print(f"  {desc_preview}")
    
    # Additional Fields
    additional_fields = []
    if lead.get('phone'):
        additional_fields.append(('Phone', lead.get('phone')))
    if lead.get('twitter'):
        additional_fields.append(('Twitter', lead.get('twitter')))
    if lead.get('github'):
        additional_fields.append(('GitHub', lead.get('github')))
    if lead.get('telegram'):
        additional_fields.append(('Telegram', lead.get('telegram')))
    
    if additional_fields:
        print(f"\n{Colors.CYAN}Additional Fields:{Colors.RESET}")
        for field_name, field_value in additional_fields:
            print(f"  {field_name}: {field_value}")
    
    # Show full JSON for complete data
    print(f"\n{Colors.MAGENTA}Full JSON Data:{Colors.RESET}")
    print(json.dumps(lead, indent=2, ensure_ascii=False))


def print_lead_header(lead: Dict, index: int):
    """Print lead header with basic info."""
    business = lead.get('business', 'Unknown')
    email = lead.get('email', 'No email')
    full_name = lead.get('full_name', 'Unknown')
    
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}LEAD #{index}: {business}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"  Contact: {full_name} ({email})")
    print(f"  Role: {lead.get('role', 'Unknown')}")
    print(f"  Location: {lead.get('city', '')}, {lead.get('state', '')}, {lead.get('country', '')}")


async def analyze_lead_scoring(lead: Dict, threshold: float = 0.7, check_reachability: bool = False) -> Tuple[float, Dict, bool]:
    """Analyze lead scoring with detailed component breakdown."""
    print_section("📊 LEAD SCORING ANALYSIS")
    
    # Score each component individually for detailed logging
    email = lead.get('email', '')
    first = lead.get('first', '')
    last = lead.get('last', '')
    full_name = lead.get('full_name', '')
    website = lead.get('website', '')
    source_url = lead.get('source_url', '')
    source_type = lead.get('source_type', '')
    
    # 1. Email Quality (40% weight)
    print(f"\n{Colors.BOLD}1. Email Quality (40% weight):{Colors.RESET}")
    email_score, email_reason = score_email_quality(email, first, last, full_name)
    print_criterion("Email Quality", email_score >= 0.7, email_reason, email_score)
    
    # Show name-email match details
    if email and (first or last or full_name):
        from smart_miner.lead_scorer import check_name_email_match, extract_name_parts
        first_part, last_part = extract_name_parts(full_name, first, last)
        name_match, match_score = check_name_email_match(email, first_part, last_part, full_name)
        if name_match:
            print(f"    {Colors.GREEN}✓ Name-email match detected (confidence: {match_score:.2f}){Colors.RESET}")
        else:
            print(f"    {Colors.YELLOW}⚠ No name-email pattern match found{Colors.RESET}")
    
    # 2. Domain Quality (30% weight)
    print(f"\n{Colors.BOLD}2. Domain Quality (30% weight):{Colors.RESET}")
    domain_score, domain_reason = score_domain_quality(website, source_url)
    print_criterion("Domain Format", domain_score > 0, domain_reason, domain_score)
    
    # Check reachability (async) - only if requested
    if check_reachability and domain_score > 0 and website:
        print(f"    {Colors.info_text('Checking domain reachability...')}")
        reachable, reachable_reason = await check_domain_reachability(website)
        if reachable:
            print(f"    {Colors.pass_text(f'Domain reachable: {reachable_reason}')}")
        else:
            print(f"    {Colors.fail_text(f'Domain unreachable: {reachable_reason}')}")
            domain_score = 0.0
            domain_reason = f"Domain unreachable: {reachable_reason}"
    elif not check_reachability and domain_score > 0:
        print(f"    {Colors.info_text('Reachability check skipped (use --check-reachability to enable)')}")
    
    # 3. Company Quality (20% weight)
    print(f"\n{Colors.BOLD}3. Company Quality (20% weight):{Colors.RESET}")
    company_score, company_reason = score_company_quality(lead)
    print_criterion("Company Quality", company_score >= 0.7, company_reason, company_score)
    
    # Show company details
    business = lead.get('business', '')
    employee_count = lead.get('employee_count', '')
    industry = lead.get('industry', '')
    sub_industry = lead.get('sub_industry', '')
    
    if business:
        print(f"    Company name: {business}")
    if employee_count:
        print(f"    Employee count: {employee_count}")
    if industry:
        print(f"    Industry: {industry}")
    if sub_industry:
        print(f"    Sub-industry: {sub_industry}")
    
    # 4. Source Quality (10% weight)
    print(f"\n{Colors.BOLD}4. Source Quality (10% weight):{Colors.RESET}")
    source_score, source_reason = score_source_quality(source_url, source_type)
    print_criterion("Source Quality", source_score >= 0.7, source_reason, source_score)
    
    if source_url:
        print(f"    Source URL: {source_url[:70]}{'...' if len(source_url) > 70 else ''}")
    if source_type:
        print(f"    Source Type: {source_type}")
    
    # Calculate total score
    weights = {
        'email': 0.4,
        'domain': 0.3,
        'company': 0.2,
        'source': 0.1
    }
    
    component_scores = {
        'email': (email_score, email_reason),
        'domain': (domain_score, domain_reason),
        'company': (company_score, company_reason),
        'source': (source_score, source_reason)
    }
    
    total_score = sum(
        component_scores[key][0] * weights[key]
        for key in weights
    )
    
    should_submit = total_score >= threshold
    
    print(f"\n{Colors.BOLD}Total Score Calculation:{Colors.RESET}")
    print(f"  Email:   {email_score:.2f} × 0.40 = {email_score * 0.4:.3f}")
    print(f"  Domain:  {domain_score:.2f} × 0.30 = {domain_score * 0.3:.3f}")
    print(f"  Company: {company_score:.2f} × 0.20 = {company_score * 0.2:.3f}")
    print(f"  Source:  {source_score:.2f} × 0.10 = {source_score * 0.1:.3f}")
    print(f"  {Colors.BOLD}─────────────────────────────{Colors.RESET}")
    print(f"  {Colors.BOLD}Total: {total_score:.3f} (threshold: {threshold}){Colors.RESET}")
    
    if should_submit:
        print(f"  {Colors.pass_text(f'✓ ABOVE THRESHOLD - Would submit')}")
    else:
        print(f"  {Colors.fail_text(f'✗ BELOW THRESHOLD - Would reject')}")
    
    return total_score, component_scores, should_submit


def analyze_lead_validation(lead: Dict, use_gateway_checks: bool = False) -> Tuple[bool, List[str]]:
    """Analyze lead validation with detailed check breakdown."""
    print_section("✅ LEAD VALIDATION ANALYSIS")
    
    rejection_reasons = []
    
    # Run all validations with detailed logging
    validators = [
        ("Required Fields", validate_required_fields),
        ("Email Format", lambda l: validate_email_format(l.get('email', ''))),
        ("Location Rules", validate_location),
        ("Industry Taxonomy", lambda l: validate_industry_taxonomy(l, use_gateway_checks=use_gateway_checks)),
        ("Employee Count", lambda l: validate_employee_count(l.get('employee_count', ''))),
        ("LinkedIn URLs", validate_linkedin_urls),
        ("Role", lambda l: validate_role(l, use_gateway_checks=use_gateway_checks)),
        ("Description", lambda l: validate_description(l, use_gateway_checks=use_gateway_checks)),
        ("Source URL", validate_source_url),
    ]
    
    for name, validator in validators:
        try:
            is_valid, error_msg = validator(lead)
            if is_valid:
                print_criterion(name, True, "Validation passed")
            else:
                print_criterion(name, False, error_msg or "Validation failed")
                rejection_reasons.append(f"{name}: {error_msg}")
        except Exception as e:
            print_criterion(name, False, f"Validation error: {str(e)}")
            rejection_reasons.append(f"{name}: Validation error - {str(e)}")
    
    is_valid = len(rejection_reasons) == 0
    
    if is_valid:
        print(f"\n{Colors.pass_text('✓ ALL VALIDATION CHECKS PASSED')}")
    else:
        print(f"\n{Colors.fail_text('✗ VALIDATION FAILED')}")
        print(f"  {Colors.RED}Rejection reasons:{Colors.RESET}")
        for reason in rejection_reasons:
            print(f"    - {reason}")
    
    return is_valid, rejection_reasons


def print_final_decision(lead: Dict, total_score: float, threshold: float, 
                         scored_above: bool, validated: bool, index: int):
    """Print final decision for the lead."""
    print_section("🎯 FINAL DECISION")
    
    business = lead.get('business', 'Unknown')
    
    print(f"\n{Colors.BOLD}Lead #{index}: {business}{Colors.RESET}")
    print(f"  Score: {total_score:.3f} / {threshold:.2f} threshold")
    print(f"  Scoring: {Colors.pass_text('PASS') if scored_above else Colors.fail_text('FAIL')}")
    print(f"  Validation: {Colors.pass_text('PASS') if validated else Colors.fail_text('FAIL')}")
    
    if scored_above and validated:
        print(f"\n  {Colors.BOLD}{Colors.GREEN}✓ WOULD SUBMIT TO GATEWAY{Colors.RESET}")
        print(f"    This lead passed all scoring and validation checks.")
    else:
        print(f"\n  {Colors.BOLD}{Colors.RED}✗ WOULD NOT SUBMIT{Colors.RESET}")
        if not scored_above:
            print(f"    Reason: Score {total_score:.3f} below threshold {threshold:.2f}")
        if not validated:
            print(f"    Reason: Failed validation checks")


def print_summary_statistics(results: List[Dict]):
    """Print summary statistics across all leads."""
    print_header("📊 SUMMARY STATISTICS", "=")
    
    total = len(results)
    scored_above = sum(1 for r in results if r.get('scored_above', False))
    validated = sum(1 for r in results if r.get('validated', False))
    would_submit = sum(1 for r in results if r.get('would_submit', False))
    
    avg_score = sum(r.get('total_score', 0) for r in results) / total if total > 0 else 0
    
    print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
    print(f"  Total leads analyzed: {total}")
    print(f"  Scored above threshold: {scored_above} ({scored_above/total*100:.1f}%)")
    print(f"  Passed validation: {validated} ({validated/total*100:.1f}%)")
    print(f"  Would submit: {would_submit} ({would_submit/total*100:.1f}%)")
    print(f"  Average score: {avg_score:.3f}")
    
    # Component score averages
    if total > 0:
        avg_email = sum(r.get('component_scores', {}).get('email', (0, ''))[0] for r in results) / total
        avg_domain = sum(r.get('component_scores', {}).get('domain', (0, ''))[0] for r in results) / total
        avg_company = sum(r.get('component_scores', {}).get('company', (0, ''))[0] for r in results) / total
        avg_source = sum(r.get('component_scores', {}).get('source', (0, ''))[0] for r in results) / total
        
        print(f"\n{Colors.BOLD}Average Component Scores:{Colors.RESET}")
        print(f"  Email:   {avg_email:.3f}")
        print(f"  Domain:  {avg_domain:.3f}")
        print(f"  Company: {avg_company:.3f}")
        print(f"  Source:  {avg_source:.3f}")
    
    # Recommendations
    print(f"\n{Colors.BOLD}Recommendations:{Colors.RESET}")
    if would_submit == 0:
        print(f"  {Colors.RED}⚠ No leads would be submitted.{Colors.RESET}")
        print(f"    - Check lead generation quality")
        print(f"    - Review scoring thresholds")
        print(f"    - Fix validation issues")
    elif would_submit < total * 0.5:
        print(f"  {Colors.YELLOW}⚠ Low submission rate ({would_submit}/{total}).{Colors.RESET}")
        print(f"    - Consider improving lead quality")
        print(f"    - Review scoring criteria")
    else:
        print(f"  {Colors.GREEN}✓ Good submission rate ({would_submit}/{total}).{Colors.RESET}")
        print(f"    - Ready for real mining")
    
    if avg_score < 0.7:
        print(f"  {Colors.YELLOW}⚠ Average score below threshold.{Colors.RESET}")
        print(f"    - Focus on improving email quality (40% weight)")
        print(f"    - Improve domain quality (30% weight)")


async def main():
    """Main bot function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Smart Miner Assistant Bot - Evaluate leads before real mining"
    )
    parser.add_argument(
        "--num-leads",
        type=int,
        default=3,
        help="Number of leads to analyze (default: 3)"
    )
    parser.add_argument(
        "--industry",
        type=str,
        default=None,
        help="Target industry (e.g., 'Technology', 'Healthcare')"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="Target region (e.g., 'United States', 'Europe')"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Minimum score threshold (default: 0.7)"
    )
    parser.add_argument(
        "--check-reachability",
        action="store_true",
        help="Check domain reachability (slower but more accurate)"
    )
    parser.add_argument(
        "--use-gateway-checks",
        action="store_true",
        help="Use gateway validation checks (requires gateway access)"
    )
    
    args = parser.parse_args()
    
    if not SMART_MINER_AVAILABLE:
        print("❌ Smart miner components not available. Please check your environment setup.")
        return 1
    
    # Check environment variables
    required_env_vars = ["GSE_API_KEY", "GSE_CX", "OPENROUTER_KEY", "FIRECRAWL_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Set these in your .env file or environment before running.")
        return 1
    
    # Print header
    print_header("🤖 SMART MINER ASSISTANT BOT", "=")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Analyzing {args.num_leads} leads")
    print(f"📊 Score threshold: {args.threshold}")
    if args.industry:
        print(f"🏭 Industry: {args.industry}")
    if args.region:
        print(f"🌍 Region: {args.region}")
    print(f"🔍 Check reachability: {args.check_reachability}")
    print(f"🔍 Use gateway checks: {args.use_gateway_checks}")
    print()
    
    # Step 1: Generate leads
    print_section("STEP 1: GENERATING LEADS")
    print("🔄 Starting Lead Sorcerer pipeline...")
    print("   This may take a few minutes (domain discovery → crawling → extraction)...")
    print()
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        leads = await generate_high_quality_leads(
            num_leads=args.num_leads,
            industry=args.industry,
            region=args.region
        )
        
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        if not leads:
            print("⚠️  No leads generated. Possible reasons:")
            print("   - No matching companies found")
            print("   - All leads filtered out (no email/business name or invalid source_url)")
            print("   - API rate limits or errors")
            print("\n💡 Debug: Check if Lead Sorcerer produced leads but they were filtered.")
            print("   Try running: python drytest_scraping.py --num-leads 1")
            print("   to see raw Lead Sorcerer output.")
            return 1
        
        print(f"✅ Generated {len(leads)} leads in {elapsed_time:.2f} seconds")
        print()
        
        # Step 2: Log all generated leads first
        print_section("📋 ALL GENERATED LEADS")
        for i, lead in enumerate(leads, 1):
            print_lead_data(lead, i)
        
        # Step 3: Analyze each lead
        print_header("🔍 ANALYZING LEADS", "=")
        results = []
        
        for i, lead in enumerate(leads, 1):
            print_lead_header(lead, i)
            
            # Scoring analysis
            total_score, component_scores, scored_above = await analyze_lead_scoring(
                lead, 
                threshold=args.threshold,
                check_reachability=args.check_reachability
            )
            
            # Validation analysis
            validated, rejection_reasons = analyze_lead_validation(
                lead,
                use_gateway_checks=args.use_gateway_checks
            )
            
            would_submit = scored_above and validated
            
            # Final decision
            print_final_decision(
                lead, 
                total_score, 
                args.threshold,
                scored_above,
                validated,
                i
            )
            
            # Store results
            results.append({
                'lead': lead,
                'total_score': total_score,
                'component_scores': component_scores,
                'scored_above': scored_above,
                'validated': validated,
                'would_submit': would_submit,
                'rejection_reasons': rejection_reasons
            })
        
        # Step 3: Summary statistics
        print_summary_statistics(results)
        
        # Final recommendation
        print_header("💡 FINAL RECOMMENDATION", "=")
        
        would_submit_count = sum(1 for r in results if r.get('would_submit', False))
        total_count = len(results)
        
        if would_submit_count == 0:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ NOT READY FOR REAL MINING{Colors.RESET}")
            print(f"\n  All {total_count} leads failed scoring or validation.")
            print(f"  {Colors.YELLOW}Action required:{Colors.RESET}")
            print(f"    1. Review lead generation quality")
            print(f"    2. Adjust scoring thresholds if needed")
            print(f"    3. Fix validation issues")
            print(f"    4. Re-run bot to verify improvements")
        elif would_submit_count < total_count * 0.5:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  PROCEED WITH CAUTION{Colors.RESET}")
            print(f"\n  Only {would_submit_count}/{total_count} leads would be submitted.")
            print(f"  {Colors.YELLOW}Recommendations:{Colors.RESET}")
            print(f"    1. Improve lead quality before real mining")
            print(f"    2. Consider lowering threshold (currently {args.threshold})")
            print(f"    3. Review rejection reasons and fix common issues")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ READY FOR REAL MINING{Colors.RESET}")
            print(f"\n  {would_submit_count}/{total_count} leads would be submitted.")
            print(f"  {Colors.GREEN}You can proceed with real mining!{Colors.RESET}")
            print(f"\n  To enable real mining:")
            print(f"    1. Set USE_SMART_MINER=1 in environment")
            print(f"    2. Set SMART_MINER_THRESHOLD={args.threshold}")
            print(f"    3. Run your miner normally")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        print("\n📋 Full traceback:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
