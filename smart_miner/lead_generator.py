"""
Lead Sourcing Strategy - High Quality Lead Generation
======================================================

Focuses on HIGH QUALITY sources:
- Company websites (about/team pages)
- Public directories
- Avoids noisy scraping

Strategy:
- Real companies
- Real roles
- Real emails
- Valid source URLs (not LinkedIn)
"""

import logging
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)


async def generate_high_quality_leads(
    num_leads: int,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    use_existing_generator: bool = True
) -> List[Dict]:
    """
    Generate high-quality leads using existing lead generation model.
    
    This function wraps the existing get_leads() function but adds
    quality filtering and validation.
    
    Args:
        num_leads: Number of leads to generate
        industry: Target industry (optional)
        region: Target region (optional)
        use_existing_generator: Use existing miner_models.get_leads (default: True)
    
    Returns:
        List of high-quality lead dictionaries
    """
    if use_existing_generator:
        try:
            from miner_models.lead_sorcerer_main.main_leads import get_leads
            
            # Generate leads using existing model
            leads = await get_leads(num_leads * 2, industry, region)  # Generate 2x to filter
            
            # Filter for quality
            quality_leads = []
            for lead in leads:
                # Basic quality checks
                if lead.get('email') and lead.get('business'):
                    # Get source_url - use website as fallback if source_url not set
                    source_url = lead.get('source_url') or lead.get('website') or lead.get('Website', '')
                    
                    # If no source_url at all but website exists, use website as source_url
                    # This handles leads from company sites where website is the source
                    if not lead.get('source_url') and lead.get('website'):
                        lead['source_url'] = lead.get('website')
                        source_url = lead.get('website')
                    
                    # Reject only if source_url exists AND is LinkedIn
                    # Allow leads without source_url (they'll be validated later)
                    if source_url and 'linkedin.com' in source_url.lower():
                        continue  # Skip LinkedIn sources
                    
                    quality_leads.append(lead)
                
                if len(quality_leads) >= num_leads:
                    break
            
            logger.info(f"Generated {len(quality_leads)}/{len(leads)} quality leads")
            return quality_leads[:num_leads]
            
        except ImportError:
            logger.warning("Lead Sorcerer not available - returning empty list")
            return []
        except Exception as e:
            logger.error(f"Error generating leads: {e}")
            return []
    else:
        # Placeholder for custom lead generation
        logger.warning("Custom lead generation not implemented - use use_existing_generator=True")
        return []


def prioritize_lead_sources() -> List[str]:
    """
    Return prioritized list of source types (best to worst).
    
    Higher priority sources are more reliable and have better approval rates.
    """
    return [
        "company_site",  # Direct company websites (highest quality)
        "public_registry",  # Public directories (Crunchbase, Companies House, etc.)
        "first_party_form",  # Contact forms on company sites
        "licensed_resale",  # Licensed data brokers (requires license_doc_hash)
        "proprietary_database",  # Proprietary databases (requires proper attestation)
    ]


def is_high_quality_source(source_url: str, source_type: str = "") -> bool:
    """
    Check if source is considered high quality.
    
    High quality sources:
    - Company websites (not LinkedIn)
    - Public registries
    - Not restricted data brokers (unless licensed)
    """
    if not source_url:
        return False
    
    # LinkedIn not allowed
    if 'linkedin.com' in source_url.lower():
        return False
    
    # Check for restricted sources
    try:
        from Leadpoet.utils.source_provenance import is_restricted_source
        
        from urllib.parse import urlparse
        parsed = urlparse(source_url if source_url.startswith(('http://', 'https://')) else f"https://{source_url}")
        domain = parsed.netloc or parsed.path
        if ':' in domain:
            domain = domain.split(':')[0]
        domain = domain.lower().strip()
        
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Licensed resale is OK
        if source_type == "licensed_resale":
            return True
        
        # Restricted sources without license are not high quality
        if is_restricted_source(domain):
            return False
    except Exception:
        pass  # Continue if check fails
    
    return True
