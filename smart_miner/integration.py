"""
Integration with Existing Miner
================================

Provides integration functions to use smart miner with existing miner.py
"""

import logging
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)


async def smart_sourcing_loop_wrapper(
    get_leads_func,
    process_generated_leads_func,
    sanitize_prospect_func,
    wallet,
    miner_hotkey: str,
    interval: int = 60,
    use_smart_miner: bool = True,
    min_score_threshold: float = 0.7,
    max_daily_submissions: int = 50
):
    """
    Wrapper for sourcing_loop that uses smart miner.
    
    This can replace the existing sourcing_loop in miner.py to add
    intelligent filtering and scoring.
    
    Args:
        get_leads_func: Function to generate leads (e.g., get_leads)
        process_generated_leads_func: Function to process leads (e.g., process_generated_leads)
        sanitize_prospect_func: Function to sanitize leads (e.g., sanitize_prospect)
        wallet: Bittensor wallet
        miner_hotkey: Miner hotkey string
        interval: Loop interval in seconds
        use_smart_miner: Enable smart miner (default: True)
        min_score_threshold: Minimum score threshold (default: 0.7)
        max_daily_submissions: Max daily submissions (default: 50)
    """
    from smart_miner.orchestrator import SmartMinerOrchestrator
    from smart_miner.lead_scorer import score_lead
    from smart_miner.lead_validator import validate_lead, check_duplicates
    
    orchestrator = SmartMinerOrchestrator(
        min_score_threshold=min_score_threshold,
        max_daily_submissions=max_daily_submissions
    )
    
    print(f"🤖 Smart Miner enabled (threshold: {min_score_threshold}, max daily: {max_daily_submissions})")
    print(f"🔄 Starting smart sourcing loop (interval: {interval}s)")
    
    while True:
        try:
            print("\n🔄 Smart Miner: Sourcing new leads...")
            
            # Generate leads
            new_leads = await get_leads_func(1, industry=None, region=None)
            
            if not new_leads:
                print("⚠️  No leads generated")
                await asyncio.sleep(interval)
                continue
            
            # Process through source provenance validation
            validated_leads = await process_generated_leads_func(new_leads)
            
            if not validated_leads:
                print("⚠️  No leads passed source provenance validation")
                await asyncio.sleep(interval)
                continue
            
            # Sanitize leads
            sanitized = [
                sanitize_prospect_func(p, miner_hotkey) for p in validated_leads
            ]
            
            print(f"🔄 Generated {len(sanitized)} leads, applying smart filtering...")
            
            # Smart miner processing
            if use_smart_miner:
                # Score and filter leads
                scored_leads = []
                for lead in sanitized:
                    try:
                        total_score, component_scores, should_submit = await score_lead(
                            lead,
                            min_score_threshold
                        )
                        
                        if should_submit:
                            # Validate lead
                            is_valid, error_msg, rejection_reasons = validate_lead(lead)
                            
                            if is_valid:
                                # Check duplicates
                                is_unique, dup_reason = await check_duplicates(lead, wallet)
                                
                                if is_unique:
                                    lead['_smart_score'] = total_score
                                    scored_leads.append(lead)
                                    print(f"  ✅ Lead passed: {lead.get('business', 'Unknown')} (score: {total_score:.2f})")
                                else:
                                    print(f"  ⏭️  Lead rejected (duplicate): {lead.get('business', 'Unknown')}")
                            else:
                                print(f"  ⏭️  Lead rejected (validation): {lead.get('business', 'Unknown')} - {error_msg}")
                        else:
                            print(f"  ⏭️  Lead rejected (low score {total_score:.2f}): {lead.get('business', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"Error processing lead: {e}")
                        continue
                
                if not scored_leads:
                    print("⚠️  No leads passed smart miner filtering")
                    await asyncio.sleep(interval)
                    continue
                
                # Submit using smart submitter
                from smart_miner.submitter import submit_leads_smart
                submission_results = await submit_leads_smart(
                    scored_leads,
                    wallet,
                    min_score_threshold,
                    max_daily_submissions
                )
                
                print(f"✅ Smart Miner results: {submission_results['submitted']} submitted, "
                      f"{submission_results['rejected']} rejected")
                
                if submission_results['stats']:
                    stats = submission_results['stats']
                    print(f"   📊 Stats: {stats.get('submissions_today', 0)}/{stats.get('max_submissions', 1000)} submissions today, "
                          f"{stats.get('rejections_today', 0)}/{stats.get('max_rejections', 200)} rejections today")
            else:
                # Fallback to original submission logic
                print("⚠️  Smart miner disabled - using original submission logic")
                # (Original submission code would go here)
            
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            print("🛑 Smart sourcing task cancelled")
            break
        except Exception as e:
            print(f"❌ Error in smart sourcing loop: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(interval)
