"""
Submission Strategy - Rate Limiting and Quality Control
========================================================

Manages lead submission with:
- Daily submission limits
- Quality prioritization
- Rejection tracking
- Logging for every rejection reason
"""

import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# Daily limits (from gateway rate_limiter)
MAX_SUBMISSIONS_PER_DAY = 1000
MAX_REJECTIONS_PER_DAY = 200


class SubmissionTracker:
    """Track submissions and rejections to avoid hitting limits."""
    
    def __init__(self):
        self.submissions_today = 0
        self.rejections_today = 0
        self.last_reset_date = datetime.now(timezone.utc).date()
        self.rejection_reasons = defaultdict(int)
    
    def reset_if_new_day(self):
        """Reset counters if it's a new day (UTC)."""
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset_date:
            logger.info(f"New day detected - resetting counters (was: {self.last_reset_date}, now: {today})")
            self.submissions_today = 0
            self.rejections_today = 0
            self.rejection_reasons.clear()
            self.last_reset_date = today
    
    def can_submit(self) -> Tuple[bool, str]:
        """Check if we can submit more leads today."""
        self.reset_if_new_day()
        
        if self.submissions_today >= MAX_SUBMISSIONS_PER_DAY:
            return False, f"Daily submission limit reached ({MAX_SUBMISSIONS_PER_DAY})"
        
        if self.rejections_today >= MAX_REJECTIONS_PER_DAY:
            return False, f"Daily rejection limit reached ({MAX_REJECTIONS_PER_DAY})"
        
        return True, "OK"
    
    def record_submission(self):
        """Record a submission attempt."""
        self.reset_if_new_day()
        self.submissions_today += 1
    
    def record_rejection(self, reason: str):
        """Record a rejection with reason."""
        self.reset_if_new_day()
        self.rejections_today += 1
        self.rejection_reasons[reason] += 1
        logger.warning(f"Rejection recorded: {reason} (total rejections today: {self.rejections_today}/{MAX_REJECTIONS_PER_DAY})")
    
    def get_stats(self) -> Dict:
        """Get current submission statistics."""
        self.reset_if_new_day()
        return {
            "submissions_today": self.submissions_today,
            "max_submissions": MAX_SUBMISSIONS_PER_DAY,
            "rejections_today": self.rejections_today,
            "max_rejections": MAX_REJECTIONS_PER_DAY,
            "submission_remaining": MAX_SUBMISSIONS_PER_DAY - self.submissions_today,
            "rejection_remaining": MAX_REJECTIONS_PER_DAY - self.rejections_today,
            "top_rejection_reasons": dict(sorted(self.rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:10])
        }


# Global tracker instance
_tracker = SubmissionTracker()


async def submit_leads_smart(
    leads: List[Dict],
    wallet,
    min_score_threshold: float = 0.7,
    max_daily_submissions: int = 50,
    *,
    dry_run: bool = False,
    skip_duplicate_check: bool = True,
    check_reachability: bool = True,
    use_gateway_checks: bool = True,
) -> Dict:
    """
    Submit leads with smart filtering and rate limiting.
    
    Strategy:
    1. Score each lead
    2. Filter by score threshold
    3. Validate each lead
    4. Check duplicates
    5. Submit with rate limiting
    6. Track rejections
    
    Args:
        leads: List of lead dictionaries
        wallet: Bittensor wallet for signing
        min_score_threshold: Minimum score to submit (default 0.7)
        max_daily_submissions: Max submissions per day (default 50, conservative)
    
    Returns:
        Dict with submission results:
        {
            "submitted": int,
            "rejected": int,
            "skipped": int,
            "rejection_reasons": List[str],
            "stats": Dict
        }
    """
    from smart_miner.lead_scorer import score_lead
    from smart_miner.lead_validator import validate_lead, check_duplicates
    
    results = {
        "submitted": 0,
        "rejected": 0,
        "skipped": 0,
        "rejection_reasons": [],
        "stats": _tracker.get_stats()
    }
    
    # Check if we can submit
    can_submit, reason = _tracker.can_submit()
    if not can_submit:
        logger.warning(f"Cannot submit: {reason}")
        results["rejection_reasons"].append(f"Rate limit: {reason}")
        return results
    
    # Process each lead
    for lead in leads:
        # Check daily limits
        can_submit, reason = _tracker.can_submit()
        if not can_submit:
            logger.warning(f"Daily limit reached - stopping submissions")
            results["rejection_reasons"].append(f"Rate limit: {reason}")
            break
        
        # Check max daily submissions (conservative limit)
        if _tracker.submissions_today >= max_daily_submissions:
            logger.info(f"Reached max daily submissions ({max_daily_submissions}) - stopping")
            results["rejection_reasons"].append(f"Max daily submissions reached: {max_daily_submissions}")
            break
        
        try:
            # Step 1: Score lead
            total_score, component_scores, should_submit = await score_lead(
                lead,
                min_score_threshold,
                check_reachability=check_reachability,
            )
            
            if not should_submit:
                reason = f"Score too low: {total_score:.2f} < {min_score_threshold}"
                logger.debug(f"Lead rejected: {reason}")
                _tracker.record_rejection(reason)
                results["rejected"] += 1
                results["rejection_reasons"].append(reason)
                continue
            
            # Step 2: Validate lead
            is_valid, error_msg, rejection_reasons = validate_lead(
                lead,
                use_gateway_checks=use_gateway_checks,
            )
            
            if not is_valid:
                reason = f"Validation failed: {error_msg}"
                logger.debug(f"Lead rejected: {reason}")
                _tracker.record_rejection(reason)
                results["rejected"] += 1
                results["rejection_reasons"].extend(rejection_reasons)
                continue
            
            # Step 3: Check duplicates (optional)
            if not skip_duplicate_check and not dry_run:
                is_unique, dup_reason = await check_duplicates(lead, wallet)
                if not is_unique:
                    reason = f"Duplicate: {dup_reason}"
                    logger.debug(f"Lead rejected: {reason}")
                    _tracker.record_rejection(reason)
                    results["rejected"] += 1
                    results["rejection_reasons"].append(reason)
                    continue
            elif dry_run:
                # In dry-run mode we intentionally skip duplicate checks to avoid any external calls.
                pass
            
            # Step 4: Submit lead
            try:
                if dry_run:
                    # No network calls, no gateway interaction. We only show what would be submitted.
                    _tracker.record_submission()
                    results["submitted"] += 1
                    logger.info(
                        f"[DRY-RUN] Would submit: {lead.get('business', 'Unknown')} "
                        f"({lead.get('email', '')}) score={total_score:.2f}"
                    )
                    continue

                from Leadpoet.utils.cloud_db import (
                    gateway_get_presigned_url,
                    gateway_upload_lead,
                    gateway_verify_submission
                )
                
                # Get presigned URL
                presign_result = gateway_get_presigned_url(wallet, lead)
                if not presign_result:
                    reason = "Failed to get presigned URL"
                    logger.warning(f"Lead submission failed: {reason}")
                    _tracker.record_rejection(reason)
                    results["rejected"] += 1
                    results["rejection_reasons"].append(reason)
                    continue
                
                # Upload to S3
                s3_uploaded = gateway_upload_lead(presign_result['s3_url'], lead)
                if not s3_uploaded:
                    reason = "Failed to upload to S3"
                    logger.warning(f"Lead submission failed: {reason}")
                    _tracker.record_rejection(reason)
                    results["rejected"] += 1
                    results["rejection_reasons"].append(reason)
                    continue
                
                # Verify submission
                verification_result = gateway_verify_submission(
                    wallet,
                    presign_result['lead_id']
                )
                
                if verification_result:
                    _tracker.record_submission()
                    results["submitted"] += 1
                    logger.info(f"✅ Lead submitted successfully: {lead.get('business', 'Unknown')} (score: {total_score:.2f})")
                else:
                    reason = "Verification failed"
                    logger.warning(f"Lead submission failed: {reason}")
                    _tracker.record_rejection(reason)
                    results["rejected"] += 1
                    results["rejection_reasons"].append(reason)
                    
            except Exception as e:
                reason = f"Submission error: {str(e)}"
                logger.error(f"Lead submission error: {reason}")
                _tracker.record_rejection(reason)
                results["rejected"] += 1
                results["rejection_reasons"].append(reason)
        
        except Exception as e:
            reason = f"Processing error: {str(e)}"
            logger.error(f"Error processing lead: {reason}")
            _tracker.record_rejection(reason)
            results["rejected"] += 1
            results["rejection_reasons"].append(reason)
    
    # Update stats
    results["stats"] = _tracker.get_stats()
    
    logger.info(
        f"Submission batch complete: {results['submitted']} submitted, "
        f"{results['rejected']} rejected, {results['skipped']} skipped"
    )
    
    return results


def get_submission_stats() -> Dict:
    """Get current submission statistics."""
    return _tracker.get_stats()
