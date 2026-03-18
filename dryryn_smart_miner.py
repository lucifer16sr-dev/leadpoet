"""
Safe dry-run test for SN71 Leadpoet Smart Miner (Windows friendly)
===============================================================

This script:
1) Generates 5-10 FAKE test leads (schema-shaped for SN71)
2) Runs lead scoring (no network reachability checks)
3) Runs strict validation
4) Runs submitter in DRY-RUN mode (NO gateway / NO SN71 calls)
5) Prints everything verbosely to terminal

Run:
  python test_smart_miner.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Tuple


THRESHOLD = 0.7


def _fake_linkedin_profile(first: str, last: str, n: int) -> str:
    # Must match validator regex: https://linkedin.com/in/<slug>
    slug = f"fake-{first.lower()}-{last.lower()}-{n:04d}"
    return f"https://linkedin.com/in/{slug}"


def _fake_linkedin_company(company: str) -> str:
    slug = (
        company.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace(",", "")
        .replace("'", "")
        .replace('"', "")
        .replace(" ", "-")
    )
    slug = "-".join([p for p in slug.split("-") if p])[:60]
    return f"https://linkedin.com/company/{slug}"


def generate_fake_leads() -> List[Dict[str, Any]]:
    """
    Generate 8 fake leads:
    - Mixture of US and non-US
    - All required fields present
    - Fake-but-realistic emails + LinkedIn URLs (not real people)
    - Valid industry/sub_industry pairs from taxonomy
    """
    leads: List[Dict[str, Any]] = []

    # Use .test and .example TLDs to avoid any real domains.
    # Note: we will SKIP reachability checks, so these won't fail scoring.

    samples = [
        # US lead - Software/SaaS
        dict(
            business="Acme Cloud Tools",
            first="John",
            last="Doe",
            role="VP of Sales",
            website="https://acmecloudtools.test",
            industry="Software",
            sub_industry="SaaS",
            employee_count="51-200",
            country="United States",
            state="California",
            city="San Francisco",
            source_url="https://acmecloudtools.test/about",
            description="Acme Cloud Tools builds subscription SaaS tools for mid-market sales teams.",
        ),
        # US lead - Financial Services/Accounting
        dict(
            business="LedgerPeak Advisors",
            first="Priya",
            last="Shah",
            role="Managing Partner",
            website="https://ledgerpeak.example",
            industry="Financial Services",
            sub_industry="Accounting",
            employee_count="11-50",
            country="United States",
            state="New York",
            city="New York City",
            source_url="https://ledgerpeak.example/team",
            description="LedgerPeak Advisors is a boutique accounting and advisory firm serving SMBs.",
        ),
        # Non-US lead - Software/SaaS (UK)
        dict(
            business="Northbridge Analytics",
            first="Emma",
            last="Taylor",
            role="Head of Revenue Operations",
            website="https://northbridge-analytics.test",
            industry="Software",
            sub_industry="SaaS",
            employee_count="201-500",
            country="United Kingdom",
            state="",  # optional for non-US
            city="London",
            source_url="https://northbridge-analytics.test/company",
            description="Northbridge Analytics provides analytics SaaS for ecommerce operations teams.",
        ),
        # Non-US lead - Professional Services/Accounting (Germany)
        dict(
            business="Rhein Consult Group",
            first="Lukas",
            last="Meyer",
            role="Director",
            website="https://rhein-consult.example",
            industry="Professional Services",
            sub_industry="Accounting",
            employee_count="2-10",
            country="Germany",
            state="",
            city="Berlin",
            source_url="https://rhein-consult.example/about-us",
            description="Rhein Consult Group offers accounting and finance process consulting for SMEs.",
        ),
        # US lead - Data and Analytics/A-B Testing
        dict(
            business="SignalSplit Labs",
            first="Carlos",
            last="Rivera",
            role="CEO",
            website="https://signalsplit.test",
            industry="Data and Analytics",
            sub_industry="A/B Testing",
            employee_count="2-10",
            country="United States",
            state="Texas",
            city="Austin",
            source_url="https://signalsplit.test/team",
            description="SignalSplit Labs builds experimentation and A/B testing tooling for product teams.",
        ),
        # Non-US lead - Travel and Tourism/Adventure Travel (Canada)
        dict(
            business="Maple Ridge Adventures",
            first="Noah",
            last="Campbell",
            role="Operations Manager",
            website="https://mapleridgeadventures.example",
            industry="Travel and Tourism",
            sub_industry="Adventure Travel",
            employee_count="11-50",
            country="Canada",
            state="",
            city="Vancouver",
            source_url="https://mapleridgeadventures.example/about",
            description="Maple Ridge Adventures runs guided adventure travel experiences across Western Canada.",
        ),
        # US lead - Advertising/Ad Network
        dict(
            business="BrightBanner Media",
            first="Alyssa",
            last="Nguyen",
            role="Director of Partnerships",
            website="https://brightbanner.test",
            industry="Advertising",
            sub_industry="Ad Network",
            employee_count="51-200",
            country="United States",
            state="Illinois",
            city="Chicago",
            source_url="https://brightbanner.test/about-us",
            description="BrightBanner Media operates an advertising network and publisher monetization platform.",
        ),
        # Non-US lead - Agriculture and Farming/AgTech (Australia)
        dict(
            business="Outback AgTech Systems",
            first="Olivia",
            last="Wilson",
            role="General Manager",
            website="https://outbackagtech.example",
            industry="Agriculture and Farming",
            sub_industry="AgTech",
            employee_count="201-500",
            country="Australia",
            state="",
            city="Sydney",
            source_url="https://outbackagtech.example/our-team",
            description="Outback AgTech Systems provides farm operations software and IoT monitoring solutions.",
        ),
    ]

    for i, s in enumerate(samples, start=1):
        full_name = f"{s['first']} {s['last']}"
        # Ensure name-email match patterns pass (e.g., first.last)
        email_domain = s["website"].replace("https://", "").replace("http://", "")
        email = f"{s['first'].lower()}.{s['last'].lower()}@{email_domain}"

        lead = {
            # Required person/company fields
            "business": s["business"],
            "full_name": full_name,
            "first": s["first"],
            "last": s["last"],
            "email": email,
            "role": s["role"],
            "website": s["website"],
            "industry": s["industry"],
            "sub_industry": s["sub_industry"],
            "country": s["country"],
            "state": s["state"],
            "city": s["city"],
            "description": s["description"],
            "employee_count": s["employee_count"],
            "linkedin": _fake_linkedin_profile(s["first"], s["last"], i),
            "company_linkedin": _fake_linkedin_company(s["business"]),
            # Source provenance (must not be LinkedIn)
            "source_url": s["source_url"],
            "source_type": "company_site",
            # Extra fields tolerated by validator (won't hurt submission)
            "phone_numbers": [],
            "socials": {},
        }
        leads.append(lead)

    return leads


def _print_json(title: str, obj: Any) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(json.dumps(obj, indent=2, ensure_ascii=False))


async def main() -> None:
    # Windows terminals can default to legacy encodings; force UTF-8 and avoid emoji output.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    from smart_miner.lead_scorer import score_lead
    from smart_miner.lead_validator import validate_lead
    from smart_miner.submitter import submit_leads_smart

    # 1) Generate fake leads
    leads = generate_fake_leads()
    _print_json(f"STEP 1) GENERATED {len(leads)} FAKE LEADS (SN71-shaped JSON)", leads)

    # 2) Score leads (skip network reachability checks for safe dry-run)
    print("\n" + "=" * 80)
    print(f"STEP 2) SCORING LEADS (threshold={THRESHOLD}, reachability_checks=OFF)")
    print("=" * 80)

    scored: List[Tuple[Dict[str, Any], float, Dict[str, Tuple[float, str]], bool]] = []
    for idx, lead in enumerate(leads, start=1):
        total, components, allow = await score_lead(
            lead,
            THRESHOLD,
            check_reachability=False,
        )
        scored.append((lead, total, components, allow))
        print(f"\n[{idx}] {lead['business']} | {lead['email']}")
        print(f"  total_score: {total:.3f} | allow_submit: {allow}")
        for k in ("email", "domain", "company", "source"):
            sc, reason = components.get(k, (0.0, "missing"))
            print(f"  - {k:7s}: {sc:.3f} | {reason}")

    allowed_scored = [s for s in scored if s[3]]
    print("\n" + "-" * 80)
    print(f"Scoring summary: {len(allowed_scored)}/{len(scored)} leads >= {THRESHOLD}")

    # 3) Validate leads
    print("\n" + "=" * 80)
    print("STEP 3) VALIDATING LEADS (strict SN71 rules, local-only)")
    print("=" * 80)

    validated_leads: List[Dict[str, Any]] = []
    for idx, (lead, total, components, allow) in enumerate(scored, start=1):
        is_valid, error_msg, reasons = validate_lead(lead, use_gateway_checks=False)
        status = "PASS" if is_valid else "FAIL"
        print(f"\n[{idx}] {status} | {lead['business']} | score={total:.3f}")
        if is_valid:
            validated_leads.append(lead)
        else:
            print(f"  main_error: {error_msg}")
            print("  rejection_reasons:")
            for r in reasons:
                print(f"    - {r}")

    print("\n" + "-" * 80)
    print(f"Validation summary: {len(validated_leads)}/{len(leads)} leads passed validation")

    # 4) Dry-run submitter
    print("\n" + "=" * 80)
    print("STEP 4) DRY-RUN SUBMISSION (NO gateway, NO SN71 network)")
    print("=" * 80)
    print("Leads that would be submitted (after scoring+validation inside submitter):")

    # NOTE: wallet is unused in dry_run mode; pass None safely.
    submission_results = await submit_leads_smart(
        leads=leads,
        wallet=None,
        min_score_threshold=THRESHOLD,
        max_daily_submissions=50,
        dry_run=True,
        skip_duplicate_check=True,
        check_reachability=False,
        use_gateway_checks=False,
    )

    _print_json("DRY-RUN SUBMISSION RESULTS", submission_results)

    # 5) Final summary
    print("\n" + "=" * 80)
    print("DONE (Safe dry-run completed)")
    print("=" * 80)
    print("Nothing was submitted to SN71. No external APIs were called.")


if __name__ == "__main__":
    asyncio.run(main())

