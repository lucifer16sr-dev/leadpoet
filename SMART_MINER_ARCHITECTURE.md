# Smart Miner Agent - Architecture & Implementation

## Overview

The Smart Miner Agent is a high-performance lead mining system for SN71 (Leadpoet) that maximizes rewards by:
- **Maximizing approval rate** through intelligent lead scoring
- **Maximizing lead reputation score** through quality filtering  
- **Minimizing rejections** through strict pre-validation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Smart Miner Orchestrator                  │
│                  (orchestrator.py)                           │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Lead       │    │   Lead       │    │   Lead       │
│  Generator   │───▶│   Scorer     │───▶│  Validator   │
│              │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Submitter   │
                    │  (Rate Limit)│
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Gateway    │
                    │  (SN71 API)  │
                    └──────────────┘
```

## Component Details

### 1. Lead Intelligence Layer (`lead_scorer.py`)

**Purpose**: Score each lead before submission to maximize approval rate.

**Scoring Components** (weighted average):

| Component | Weight | Checks |
|-----------|--------|--------|
| **Email Quality** | 40% | Name-email matching (26 patterns), generic email detection, format validation |
| **Domain Quality** | 30% | Real website, domain age (≥7 days), spam/blacklist, reachability |
| **Company Quality** | 20% | Company name, employee count format, industry taxonomy |
| **Source Quality** | 10% | Reliable URL (not LinkedIn), source type validation |

**Threshold**: Only leads with total score ≥ 0.7 (default) are submitted.

**Key Features**:
- 26 name-email matching patterns (johndoe@, john.doe@, jdoe@, etc.)
- Generic email rejection (hello@, info@, contact@, etc.)
- Domain reachability verification
- Restricted source detection

### 2. Strict Validation Layer (`lead_validator.py`)

**Purpose**: Enforce ALL SN71 schema rules before submission.

**Validation Checks**:

1. **Required Fields**: email, business, full_name, first, last, website, industry, sub_industry, country, city, state (US only), role, linkedin, company_linkedin, source_url, description, employee_count

2. **Email Format**: Standard email regex validation

3. **Location Rules**:
   - US leads: require country, state, AND city
   - Non-US leads: require country and city (state optional)

4. **Industry Taxonomy**: Validates against `validator_models.industry_taxonomy`

5. **Employee Count**: Must be one of: `"0-1"`, `"2-10"`, `"11-50"`, `"51-200"`, `"201-500"`, `"501-1,000"`, `"1,001-5,000"`, `"5,001-10,000"`, `"10,001+"`

6. **LinkedIn URLs**:
   - Personal: `https://linkedin.com/in/username`
   - Company: `https://linkedin.com/company/companyname`

7. **Role Sanity**: Uses `gateway.api.submit.check_role_sanity`

8. **Description Sanity**: Uses `gateway.api.submit.check_description_sanity`

9. **Source URL**: Valid URL or `"proprietary_database"`, not LinkedIn

10. **Duplicate Detection**: Checks email and LinkedIn combo duplicates

**Rejection Logging**: Every rejection reason is logged for analysis.

### 3. Lead Sourcing Strategy (`lead_generator.py`)

**Purpose**: Generate high-quality leads from reliable sources.

**Strategy**:
- Uses existing `miner_models.lead_sorcerer_main.main_leads.get_leads`
- Filters for quality (email present, business present, source_url not LinkedIn)
- Prioritizes company websites and public directories

**Source Priority** (best to worst):
1. `company_site` - Direct company websites
2. `public_registry` - Public directories (Crunchbase, Companies House)
3. `first_party_form` - Contact forms on company sites
4. `licensed_resale` - Licensed data brokers (requires license_doc_hash)
5. `proprietary_database` - Proprietary databases (requires proper attestation)

### 4. Submission Strategy (`submitter.py`)

**Purpose**: Manage lead submission with rate limiting and quality control.

**Features**:
- **Daily Limits**: 
  - 1000 submission attempts per day (gateway limit)
  - 200 rejections per day (gateway limit)
  - 50 submissions per day (conservative smart miner default)

- **Rejection Tracking**: 
  - Tracks all rejection reasons
  - Logs top rejection reasons
  - Prevents hitting rejection cap

- **Statistics**:
  - Submissions today / max
  - Rejections today / max
  - Submission remaining
  - Rejection remaining
  - Top rejection reasons

**Submission Flow**:
1. Check daily limits
2. Score lead
3. Validate lead
4. Check duplicates
5. Get presigned URL
6. Upload to S3
7. Verify submission
8. Track results

## File Structure

```
smart_miner/
├── __init__.py              # Package initialization
├── lead_scorer.py           # Lead scoring system
├── lead_validator.py         # Strict validation layer
├── lead_generator.py         # High-quality lead sourcing
├── submitter.py             # Submission strategy with rate limiting
├── orchestrator.py          # Main orchestrator
├── integration.py           # Integration with existing miner.py
├── README.md                # Documentation
└── example_usage.py         # Usage examples
```

## Integration Points

### With Existing Miner (`neurons/miner.py`)

The smart miner integrates via `smart_miner.integration.smart_sourcing_loop_wrapper`:

```python
from smart_miner.integration import smart_sourcing_loop_wrapper

async def sourcing_loop(self, interval: int, miner_hotkey: str):
    await smart_sourcing_loop_wrapper(
        get_leads_func=get_leads,
        process_generated_leads_func=self.process_generated_leads,
        sanitize_prospect_func=sanitize_prospect,
        wallet=self.wallet,
        miner_hotkey=miner_hotkey,
        interval=interval,
        use_smart_miner=True,
        min_score_threshold=0.7,
        max_daily_submissions=50
    )
```

### With Gateway (`gateway/api/submit.py`)

Uses existing gateway functions:
- `gateway_get_presigned_url` - Get presigned S3 URL
- `gateway_upload_lead` - Upload lead to S3
- `gateway_verify_submission` - Verify submission

### With Validation (`gateway/api/submit.py`)

Uses gateway validation functions:
- `check_role_sanity` - Role format validation
- `check_description_sanity` - Description format validation
- `check_industry_taxonomy` - Industry taxonomy validation

### With Cloud DB (`Leadpoet/utils/cloud_db.py`)

Uses cloud DB functions:
- `check_email_duplicate` - Check for duplicate emails
- `check_linkedin_combo_duplicate` - Check for duplicate LinkedIn combos

### With Source Provenance (`Leadpoet/utils/source_provenance.py`)

Uses source provenance functions:
- `is_restricted_source` - Check if domain is restricted
- `validate_source_url` - Validate source URL
- `determine_source_type` - Determine source type

## Configuration

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_score_threshold` | 0.7 | Minimum total score (0.0-1.0) to submit |
| `max_daily_submissions` | 50 | Conservative daily submission limit |
| `max_leads_per_batch` | 10 | Max leads to process per batch |

### Component Weights

| Component | Weight | Rationale |
|-----------|--------|------------|
| Email Quality | 40% | Most important - email validation is strict |
| Domain Quality | 30% | Important - domain must be real and reachable |
| Company Quality | 20% | Moderate - company data must be valid |
| Source Quality | 10% | Lower - source validation is less critical |

## Workflow

### Lead Processing Pipeline

```
1. Generate Leads
   └─> lead_generator.generate_high_quality_leads()
       └─> Uses existing get_leads() function
       └─> Filters for basic quality

2. Score Leads
   └─> lead_scorer.score_lead()
       └─> Email Quality (40%)
       └─> Domain Quality (30%)
       └─> Company Quality (20%)
       └─> Source Quality (10%)
       └─> Total Score = weighted average
       └─> Filter: score >= threshold

3. Validate Leads
   └─> lead_validator.validate_lead()
       └─> Required fields
       └─> Email format
       └─> Location rules
       └─> Industry taxonomy
       └─> Employee count
       └─> LinkedIn URLs
       └─> Role sanity
       └─> Description sanity
       └─> Source URL
       └─> Duplicate check

4. Submit Leads
   └─> submitter.submit_leads_smart()
       └─> Check daily limits
       └─> Get presigned URL
       └─> Upload to S3
       └─> Verify submission
       └─> Track results
```

## Performance Metrics

### Expected Outcomes

- **Approval Rate**: 70-90% (vs 30-50% without smart miner)
- **Rejection Rate**: <10% (vs 50-70% without smart miner)
- **Daily Submissions**: 50 (conservative) to 200 (aggressive)
- **Rejection Cap**: Rarely hit (due to pre-validation)

### Monitoring

Track these metrics:
- Submission success rate
- Rejection reasons (top 10)
- Average lead score
- Component score breakdown
- Daily submission/rejection counts

## Best Practices

1. **Start Conservative**
   - Use `min_score_threshold=0.7` initially
   - Use `max_daily_submissions=50` to avoid hitting rejection cap
   - Monitor approval rate and adjust

2. **Quality Over Quantity**
   - Better to submit 10 high-quality leads than 100 low-quality ones
   - Higher approval rate = higher rewards
   - Higher reputation score = higher rewards

3. **Monitor Rejection Reasons**
   - Check top rejection reasons regularly
   - Adjust scoring weights if needed
   - Fix common validation issues

4. **Source Selection**
   - Prioritize company websites
   - Avoid LinkedIn as source_url
   - Use public registries when possible
   - Avoid restricted sources (unless licensed)

## Constraints

- **NEVER fabricate data** - All data must be real
- **NEVER use LinkedIn as source_url** - LinkedIn URLs are blocked
- **MUST follow SN71 rules strictly** - All validation rules must pass
- **MUST validate before submission** - Prevents hitting rejection cap

## Future Enhancements

Potential improvements:
- Machine learning-based scoring
- Dynamic threshold adjustment based on approval rate
- Source quality metrics and tracking
- Approval rate prediction
- Reputation score optimization
- A/B testing different scoring weights

## Summary

The Smart Miner Agent provides:

✅ **Intelligent Scoring** - Multi-dimensional lead quality scoring  
✅ **Strict Validation** - Pre-submission validation prevents rejections  
✅ **Quality Sourcing** - Focus on high-quality sources  
✅ **Rate Limiting** - Conservative limits prevent hitting rejection cap  
✅ **Comprehensive Logging** - Track all rejections and reasons  
✅ **Easy Integration** - Drop-in replacement for existing sourcing loop  

This maximizes rewards by ensuring only high-quality, validated leads are submitted, resulting in higher approval rates and reputation scores.
