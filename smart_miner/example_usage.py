"""
Example Usage of Smart Miner
=============================

This file demonstrates how to use the smart miner agent.
"""

import asyncio
import bittensor as bt
from smart_miner.orchestrator import run_smart_miner_batch
from smart_miner.lead_scorer import score_lead
from smart_miner.lead_validator import validate_lead


async def example_score_lead():
    """Example: Score a single lead."""
    from smart_miner.lead_scorer import score_lead
    
    lead = {
        "email": "john.doe@example.com",
        "first": "John",
        "last": "Doe",
        "full_name": "John Doe",
        "business": "Example Corp",
        "website": "https://example.com",
        "industry": "Software",
        "sub_industry": "SaaS",
        "country": "United States",
        "state": "California",
        "city": "San Francisco",
        "role": "CEO",
        "linkedin": "https://linkedin.com/in/johndoe",
        "company_linkedin": "https://linkedin.com/company/example-corp",
        "source_url": "https://example.com/about",
        "description": "A technology company",
        "employee_count": "51-200"
    }
    
    total_score, component_scores, should_submit = await score_lead(lead, min_threshold=0.7)
    
    print(f"Total Score: {total_score:.2f}")
    print(f"Should Submit: {should_submit}")
    print("\nComponent Scores:")
    for component, (score, reason) in component_scores.items():
        print(f"  {component}: {score:.2f} - {reason}")


async def example_validate_lead():
    """Example: Validate a lead."""
    from smart_miner.lead_validator import validate_lead
    
    lead = {
        "email": "john.doe@example.com",
        "first": "John",
        "last": "Doe",
        "full_name": "John Doe",
        "business": "Example Corp",
        "website": "https://example.com",
        "industry": "Software",
        "sub_industry": "SaaS",
        "country": "United States",
        "state": "California",
        "city": "San Francisco",
        "role": "CEO",
        "linkedin": "https://linkedin.com/in/johndoe",
        "company_linkedin": "https://linkedin.com/company/example-corp",
        "source_url": "https://example.com/about",
        "description": "A technology company",
        "employee_count": "51-200"
    }
    
    is_valid, error_msg, rejection_reasons = validate_lead(lead)
    
    print(f"Valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error_msg}")
        print("Rejection Reasons:")
        for reason in rejection_reasons:
            print(f"  - {reason}")


async def example_submit_batch():
    """Example: Submit a batch of leads using smart miner."""
    # Note: This requires a valid Bittensor wallet
    # config = bt.Config()
    # config.wallet.name = "miner"
    # config.wallet.hotkey = "default"
    # wallet = bt.wallet(config=config)
    
    # results = await run_smart_miner_batch(
    #     num_leads=10,
    #     wallet=wallet,
    #     industry="Technology",
    #     region="United States",
    #     min_score_threshold=0.7,
    #     max_daily_submissions=50
    # )
    
    # print(f"Results: {results}")
    print("Example: Submit batch (requires wallet - uncomment code)")


if __name__ == "__main__":
    print("=== Example 1: Score Lead ===")
    asyncio.run(example_score_lead())
    
    print("\n=== Example 2: Validate Lead ===")
    asyncio.run(example_validate_lead())
    
    print("\n=== Example 3: Submit Batch ===")
    asyncio.run(example_submit_batch())
