"""
Smart Miner Orchestrator
========================

Main orchestrator that coordinates:
- Lead generation
- Lead scoring
- Lead validation
- Lead submission

This is the main entry point for the smart miner agent.
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SmartMinerOrchestrator:
    """
    Orchestrates the smart miner pipeline.
    
    Pipeline:
    1. Generate leads (lead_generator)
    2. Score leads (lead_scorer)
    3. Validate leads (lead_validator)
    4. Submit leads (submitter)
    """
    
    def __init__(
        self,
        min_score_threshold: float = 0.7,
        max_daily_submissions: int = 50,
        max_leads_per_batch: int = 10
    ):
        """
        Initialize smart miner orchestrator.
        
        Args:
            min_score_threshold: Minimum score to submit (0.0-1.0)
            max_daily_submissions: Max submissions per day (conservative limit)
            max_leads_per_batch: Max leads to process per batch
        """
        self.min_score_threshold = min_score_threshold
        self.max_daily_submissions = max_daily_submissions
        self.max_leads_per_batch = max_leads_per_batch
    
    async def process_and_submit_leads(
        self,
        num_leads: int,
        wallet,
        industry: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict:
        """
        Main entry point: Generate, score, validate, and submit leads.
        
        Args:
            num_leads: Target number of leads to submit
            wallet: Bittensor wallet for signing
            industry: Target industry (optional)
            region: Target region (optional)
        
        Returns:
            Dict with results:
            {
                "generated": int,
                "scored_above_threshold": int,
                "validated": int,
                "submitted": int,
                "rejected": int,
                "stats": Dict
            }
        """
        from smart_miner.lead_generator import generate_high_quality_leads
        from smart_miner.lead_scorer import score_lead
        from smart_miner.lead_validator import validate_lead, check_duplicates
        from smart_miner.submitter import submit_leads_smart, get_submission_stats
        
        results = {
            "generated": 0,
            "scored_above_threshold": 0,
            "validated": 0,
            "submitted": 0,
            "rejected": 0,
            "skipped": 0,
            "stats": get_submission_stats()
        }
        
        logger.info(f"🚀 Smart Miner: Starting pipeline for {num_leads} leads")
        
        # Step 1: Generate leads
        logger.info("📊 Step 1: Generating leads...")
        leads = await generate_high_quality_leads(
            num_leads * 2,  # Generate 2x to account for filtering
            industry,
            region
        )
        results["generated"] = len(leads)
        logger.info(f"   Generated {len(leads)} leads")
        
        if not leads:
            logger.warning("No leads generated - stopping pipeline")
            return results
        
        # Step 2: Score leads
        logger.info("📊 Step 2: Scoring leads...")
        scored_leads = []
        for lead in leads:
            try:
                total_score, component_scores, should_submit = await score_lead(
                    lead,
                    self.min_score_threshold
                )
                
                if should_submit:
                    lead['_smart_score'] = total_score
                    lead['_component_scores'] = component_scores
                    scored_leads.append(lead)
                    results["scored_above_threshold"] += 1
                else:
                    logger.debug(f"   Lead rejected (score {total_score:.2f} < {self.min_score_threshold}): {lead.get('business', 'Unknown')}")
            except Exception as e:
                logger.error(f"   Error scoring lead: {e}")
                continue
        
        logger.info(f"   {len(scored_leads)}/{len(leads)} leads scored above threshold")
        
        if not scored_leads:
            logger.warning("No leads scored above threshold - stopping pipeline")
            return results
        
        # Step 3: Validate leads
        logger.info("📊 Step 3: Validating leads...")
        validated_leads = []
        for lead in scored_leads:
            try:
                is_valid, error_msg, rejection_reasons = validate_lead(lead)
                
                if is_valid:
                    # Check duplicates
                    is_unique, dup_reason = await check_duplicates(lead, wallet)
                    if is_unique:
                        validated_leads.append(lead)
                        results["validated"] += 1
                    else:
                        logger.debug(f"   Lead rejected (duplicate): {dup_reason}")
                else:
                    logger.debug(f"   Lead rejected (validation): {error_msg}")
            except Exception as e:
                logger.error(f"   Error validating lead: {e}")
                continue
        
        logger.info(f"   {len(validated_leads)}/{len(scored_leads)} leads validated")
        
        if not validated_leads:
            logger.warning("No leads passed validation - stopping pipeline")
            return results
        
        # Step 4: Submit leads (with rate limiting)
        logger.info("📊 Step 4: Submitting leads...")
        submission_results = await submit_leads_smart(
            validated_leads[:self.max_leads_per_batch],  # Limit batch size
            wallet,
            self.min_score_threshold,
            self.max_daily_submissions
        )
        
        results["submitted"] = submission_results["submitted"]
        results["rejected"] = submission_results["rejected"]
        results["skipped"] = submission_results["skipped"]
        results["stats"] = submission_results["stats"]
        
        logger.info(
            f"✅ Pipeline complete: {results['submitted']} submitted, "
            f"{results['rejected']} rejected, {results['skipped']} skipped"
        )
        
        return results


async def run_smart_miner_batch(
    num_leads: int,
    wallet,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    min_score_threshold: float = 0.7,
    max_daily_submissions: int = 50
) -> Dict:
    """
    Convenience function to run smart miner batch.
    
    Args:
        num_leads: Target number of leads to submit
        wallet: Bittensor wallet for signing
        industry: Target industry (optional)
        region: Target region (optional)
        min_score_threshold: Minimum score to submit (default 0.7)
        max_daily_submissions: Max submissions per day (default 50)
    
    Returns:
        Dict with results
    """
    orchestrator = SmartMinerOrchestrator(
        min_score_threshold=min_score_threshold,
        max_daily_submissions=max_daily_submissions
    )
    
    return await orchestrator.process_and_submit_leads(
        num_leads,
        wallet,
        industry,
        region
    )
