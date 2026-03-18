"""
Test script to see Lead Sorcerer scraping results in terminal.
No subnet registration required - just shows what gets scraped.

Usage:
    python test_scraping.py [--num-leads N] [--industry INDUSTRY] [--region REGION]

Example:
    python test_scraping.py --num-leads 3 --industry "Technology" --region "United States"
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Force UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import Lead Sorcerer
try:
    from miner_models.lead_sorcerer_main.main_leads import get_leads
    LEAD_SORCERER_AVAILABLE = True
except ImportError as e:
    print(f"❌ Failed to import Lead Sorcerer: {e}")
    print("   Make sure you're running from the project root directory")
    LEAD_SORCERER_AVAILABLE = False


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    print(f"\n{char * 70}")
    print(f"  {text}")
    print(f"{char * 70}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{'─' * 70}")
    print(f"  {text}")
    print(f"{'─' * 70}")


def print_lead_summary(lead: Dict[str, Any], index: int):
    """Print a formatted lead summary."""
    print(f"\n{'=' * 70}")
    print(f"LEAD #{index}")
    print(f"{'=' * 70}")
    
    # Basic Info
    business = lead.get('business', 'Unknown')
    email = lead.get('email', 'No email')
    full_name = lead.get('full_name', 'Unknown')
    role = lead.get('role', 'Unknown')
    
    print(f"\n📊 BASIC INFO:")
    print(f"   Company:     {business}")
    print(f"   Contact:     {full_name}")
    print(f"   Email:       {email}")
    print(f"   Role:        {role}")
    
    # Location
    country = lead.get('country', 'Unknown')
    state = lead.get('state', '')
    city = lead.get('city', '')
    location_str = f"{city}, {state}" if state else city
    if location_str and country:
        location_str = f"{location_str}, {country}" if location_str else country
    elif country:
        location_str = country
    
    print(f"\n📍 LOCATION:")
    print(f"   {location_str}")
    
    # Company Details
    website = lead.get('website', '')
    linkedin = lead.get('linkedin', '')
    company_linkedin = lead.get('company_linkedin', '')
    employee_count = lead.get('employee_count', 'Unknown')
    industry = lead.get('industry', 'Unknown')
    sub_industry = lead.get('sub_industry', 'Unknown')
    
    print(f"\n🏢 COMPANY DETAILS:")
    if website:
        print(f"   Website:      {website}")
    if company_linkedin:
        print(f"   Company LI:   {company_linkedin}")
    if linkedin:
        print(f"   Person LI:    {linkedin}")
    print(f"   Employees:    {employee_count}")
    print(f"   Industry:     {industry}")
    if sub_industry and sub_industry != industry:
        print(f"   Sub-Industry: {sub_industry}")
    
    # Source
    source_url = lead.get('source_url', '')
    source_type = lead.get('source_type', 'Unknown')
    
    print(f"\n🔗 SOURCE:")
    print(f"   Type:         {source_type}")
    if source_url:
        print(f"   URL:          {source_url[:80]}{'...' if len(source_url) > 80 else ''}")
    
    # Description
    description = lead.get('description', '')
    if description:
        desc_preview = description[:200] + '...' if len(description) > 200 else description
        print(f"\n📝 DESCRIPTION:")
        print(f"   {desc_preview}")
    
    # Additional Fields
    additional_fields = []
    if lead.get('phone'):
        additional_fields.append(f"Phone: {lead.get('phone')}")
    if lead.get('twitter'):
        additional_fields.append(f"Twitter: {lead.get('twitter')}")
    if lead.get('github'):
        additional_fields.append(f"GitHub: {lead.get('github')}")
    
    if additional_fields:
        print(f"\n➕ ADDITIONAL:")
        for field in additional_fields:
            print(f"   {field}")


def print_statistics(leads: List[Dict[str, Any]], elapsed_time: float):
    """Print scraping statistics."""
    print_section("📊 SCRAPING STATISTICS")
    
    total_leads = len(leads)
    leads_with_email = sum(1 for l in leads if l.get('email'))
    leads_with_linkedin = sum(1 for l in leads if l.get('linkedin'))
    leads_with_website = sum(1 for l in leads if l.get('website'))
    leads_with_company_linkedin = sum(1 for l in leads if l.get('company_linkedin'))
    
    countries = {}
    industries = {}
    roles = {}
    
    for lead in leads:
        country = lead.get('country', 'Unknown')
        countries[country] = countries.get(country, 0) + 1
        
        industry = lead.get('industry', 'Unknown')
        industries[industry] = industries.get(industry, 0) + 1
        
        role = lead.get('role', 'Unknown')
        roles[role] = roles.get(role, 0) + 1
    
    print(f"\n✅ TOTAL LEADS: {total_leads}")
    print(f"⏱️  TIME TAKEN: {elapsed_time:.2f} seconds")
    print(f"⚡ RATE: {total_leads / elapsed_time:.2f} leads/second" if elapsed_time > 0 else "⚡ RATE: N/A")
    
    print(f"\n📧 EMAIL COVERAGE:")
    print(f"   Leads with email: {leads_with_email}/{total_leads} ({leads_with_email/total_leads*100:.1f}%)" if total_leads > 0 else "   No leads")
    
    print(f"\n🔗 LINKEDIN COVERAGE:")
    print(f"   Person LinkedIn: {leads_with_linkedin}/{total_leads} ({leads_with_linkedin/total_leads*100:.1f}%)" if total_leads > 0 else "   No leads")
    print(f"   Company LinkedIn: {leads_with_company_linkedin}/{total_leads} ({leads_with_company_linkedin/total_leads*100:.1f}%)" if total_leads > 0 else "   No leads")
    
    print(f"\n🌐 WEBSITE COVERAGE:")
    print(f"   Leads with website: {leads_with_website}/{total_leads} ({leads_with_website/total_leads*100:.1f}%)" if total_leads > 0 else "   No leads")
    
    if countries:
        print(f"\n🌍 COUNTRIES:")
        for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True):
            print(f"   {country}: {count}")
    
    if industries:
        print(f"\n🏭 INDUSTRIES:")
        for industry, count in sorted(industries.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {industry}: {count}")
    
    if roles:
        print(f"\n👔 TOP ROLES:")
        for role, count in sorted(roles.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {role}: {count}")


def print_json_output(leads: List[Dict[str, Any]]):
    """Print leads as JSON for programmatic use."""
    print_section("📄 JSON OUTPUT (for programmatic use)")
    print(json.dumps(leads, indent=2, ensure_ascii=False))


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Lead Sorcerer scraping without subnet registration"
    )
    parser.add_argument(
        "--num-leads",
        type=int,
        default=3,
        help="Number of leads to generate (default: 3)"
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
        "--json",
        action="store_true",
        help="Output only JSON (no human-readable format)"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show only statistics summary"
    )
    
    args = parser.parse_args()
    
    if not LEAD_SORCERER_AVAILABLE:
        print("❌ Lead Sorcerer is not available. Please check your environment setup.")
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
    if not args.json:
        print_header("🧪 LEAD SORCERER SCRAPING TEST", "=")
        print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Target: {args.num_leads} leads")
        if args.industry:
            print(f"🏭 Industry: {args.industry}")
        if args.region:
            print(f"🌍 Region: {args.region}")
        print()
    
    # Run scraping
    start_time = asyncio.get_event_loop().time()
    
    try:
        if not args.json:
            print("🔄 Starting Lead Sorcerer pipeline...")
            print("   This may take a few minutes (domain discovery → crawling → extraction)...")
            print()
        
        leads = await get_leads(
            num_leads=args.num_leads,
            industry=args.industry,
            region=args.region
        )
        
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        if not leads:
            if not args.json:
                print("⚠️  No leads generated. Possible reasons:")
                print("   - No matching companies found")
                print("   - All leads filtered out (no email/business name)")
                print("   - API rate limits or errors")
            return 1
        
        # Output results
        if args.json:
            # JSON-only output
            print(json.dumps(leads, indent=2, ensure_ascii=False))
        elif args.stats_only:
            # Statistics only
            print_statistics(leads, elapsed_time)
        else:
            # Full human-readable output
            print_header("✅ SCRAPING COMPLETE", "=")
            
            # Print each lead
            for i, lead in enumerate(leads, 1):
                print_lead_summary(lead, i)
            
            # Print statistics
            print_statistics(leads, elapsed_time)
            
            # Optionally print JSON
            print("\n")
            response = input("📄 Show JSON output? (y/n): ").strip().lower()
            if response == 'y':
                print_json_output(leads)
        
        return 0
        
    except KeyboardInterrupt:
        if not args.json:
            print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        if not args.json:
            print(f"\n❌ Error during scraping: {e}")
            import traceback
            print("\n📋 Full traceback:")
            traceback.print_exc()
        else:
            print(json.dumps({"error": str(e)}, indent=2))
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)