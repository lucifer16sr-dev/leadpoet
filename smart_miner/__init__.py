"""
Smart Miner Agent for SN71 (Leadpoet)
======================================

A high-performance miner agent that maximizes rewards by:
- Maximizing approval rate through intelligent lead scoring
- Maximizing lead reputation score through quality filtering
- Minimizing rejections through strict pre-validation

Architecture:
- lead_scorer.py: Scores leads before submission (email, domain, company, source quality)
- lead_validator.py: Strict SN71 schema validation
- lead_generator.py: High-quality lead sourcing strategy
- submitter.py: Submission strategy with rate limiting
"""

__version__ = "1.0.0"
