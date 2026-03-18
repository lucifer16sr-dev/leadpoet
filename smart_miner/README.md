# Smart Miner Agent for SN71 (Leadpoet)

A high-performance miner agent designed to maximize rewards by:
- **Maximizing approval rate** through intelligent lead scoring
- **Maximizing lead reputation score** through quality filtering
- **Minimizing rejections** through strict pre-validation

## Architecture

The smart miner consists of four core modules:

### 1. Lead Intelligence Layer (`lead_scorer.py`)

Scores each lead before submission across four dimensions:

- **Email Quality (40% weight)**
  - Name-email matching using 26 common patterns
  - Generic email detection (rejects hello@, info@, etc.)
  - Email format validation

- **Domain Quality (30% weight)**
  - Real website verification
  - Domain age check (≥7 days)
  - Spam/blacklist detection
  - URL reachability

- **Company Quality (20% weight)**
  - Known company signals
  - Employee count validation
  - Industry taxonomy match

- **Source Quality (10% weight)**
  - Reliable URL (not LinkedIn)
  - Source type validation
  - URL reachability

**Only leads above threshold (default 0.7) are allowed for submission.**

### 2. Strict Validation Layer (`lead_validator.py`)

Enforces ALL SN71 schema rules before submission:

- Required fields validation
- Email format + pattern validation
- Location rules (US vs non-US)
- Industry taxonomy validation
- Employee count format
- LinkedIn URL format
- Role sanity checks
- Description sanity checks
- Duplicate detection (email, LinkedIn combo)

**Rejects leads BEFORE submission to avoid hitting rejection cap.**

### 3. Lead Sourcing Strategy (`lead_generator.py`)

Focuses on HIGH QUALITY sources:

- Company websites (about/team pages)
- Public directories
- Avoids noisy scraping
- Real companies, real roles, real emails
- Valid source URLs (not LinkedIn)

### 4. Submission Strategy (`submitter.py`)

Manages lead submission with:

- Daily submission limits (1000 submissions, 200 rejections per day)
- Quality prioritization
- Rejection tracking
- Logging for every rejection reason
- Conservative daily limits (default: 50 submissions/day)

## Usage

### Basic Integration

Replace the existing `sourcing_loop` in `neurons/miner.py`:

```python
from smart_miner.integration import smart_sourcing_loop_wrapper

# In Miner class __init__ or sourcing_loop:
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

### Standalone Usage

```python
from smart_miner.orchestrator import run_smart_miner_batch

# Process and submit leads
results = await run_smart_miner_batch(
    num_leads=10,
    wallet=wallet,
    industry="Technology",
    region="United States",
    min_score_threshold=0.7,
    max_daily_submissions=50
)

print(f"Submitted: {results['submitted']}")
print(f"Rejected: {results['rejected']}")
print(f"Stats: {results['stats']}")
```

### Configuration

Key parameters:

- `min_score_threshold` (default: 0.7): Minimum total score (0.0-1.0) to submit
  - Higher = stricter filtering, fewer submissions, higher quality
  - Lower = more submissions, lower quality

- `max_daily_submissions` (default: 50): Conservative daily limit
  - Prevents hitting rejection cap
  - Adjust based on your approval rate

- Component weights (in `lead_scorer.py`):
  - Email: 40% (most important)
  - Domain: 30%
  - Company: 20%
  - Source: 10%

## Scoring Details

### Email Quality Scoring

1. **Name-Email Matching (High Priority)**
   - Checks 26 common patterns:
     - `johndoe@`, `john.doe@`, `john_doe@`, `john-doe@`
     - `jdoe@`, `j.doe@`, `j_doe@`, `j-doe@`
     - `doejohn@`, `doe.john@`, `doe_john@`, `doe-john@`
     - `djohn@`, `d.john@`, `d_john@`, `d-john@`
     - `john@`, `doe@` (single tokens)
   - Confidence scores: 1.0 (strong), 0.8 (good), 0.6 (weak)

2. **Generic Email Detection (Reject)**
   - Rejects: hello@, info@, contact@, support@, team@, etc.
   - Rejects: test@, demo@, example@, temp@, etc.

### Domain Quality Scoring

1. **URL Format Validation**
   - Must be valid HTTP/HTTPS URL
   - Domain extraction and normalization

2. **Restricted Source Check**
   - Blocks restricted data brokers (ZoomInfo, Apollo, etc.)
   - Unless `source_type = "licensed_resale"` with `license_doc_hash`

3. **LinkedIn Block**
   - LinkedIn URLs not allowed as `source_url`

4. **Reachability Check**
   - Verifies URL is accessible (HTTP HEAD request)
   - Handles redirects and status codes

### Company Quality Scoring

1. **Company Name**
   - Must be present and non-empty

2. **Employee Count**
   - Validates against SN71 format:
     - `"0-1"`, `"2-10"`, `"11-50"`, `"51-200"`, `"201-500"`, `"501-1,000"`, `"1,001-5,000"`, `"5,001-10,000"`, `"10,001+"`

3. **Industry Taxonomy**
   - Validates `industry` and `sub_industry` against taxonomy
   - Uses `gateway.api.submit.check_industry_taxonomy`

### Source Quality Scoring

1. **Source URL Validation**
   - Must be valid URL or `"proprietary_database"`
   - LinkedIn URLs blocked
   - Restricted sources blocked (unless licensed)

2. **Source Type Validation**
   - If `source_url = "proprietary_database"`, `source_type` must match

## Validation Details

### Required Fields

All of these must be present:
- `email`, `business`, `full_name`, `first`, `last`
- `website`, `industry`, `sub_industry`
- `country`, `city`
- `state` (for US leads only)
- `role`, `linkedin`, `company_linkedin`
- `source_url`, `description`, `employee_count`

### Location Rules

- **US leads**: Require `country`, `state`, AND `city`
- **Non-US leads**: Require `country` and `city` (state optional)

### Industry Taxonomy

- Validates against `validator_models.industry_taxonomy`
- Ensures `sub_industry` exists and `industry` is valid parent

### LinkedIn URLs

- Personal: `https://linkedin.com/in/username`
- Company: `https://linkedin.com/company/companyname`

### Role & Description

- Uses gateway sanity checks (`check_role_sanity`, `check_description_sanity`)
- Catches garbage roles/descriptions before submission

## Submission Strategy

### Rate Limiting

- **Daily Limits** (from gateway):
  - 1000 submission attempts per day
  - 200 rejections per day

- **Conservative Limits** (smart miner default):
  - 50 submissions per day (prevents hitting rejection cap)

### Rejection Tracking

Every rejection is logged with reason:
- Low score
- Validation failure
- Duplicate
- Submission error

### Statistics

Track daily stats:
- Submissions today / max
- Rejections today / max
- Top rejection reasons

## Best Practices

1. **Start Conservative**
   - Use `min_score_threshold=0.7` initially
   - Use `max_daily_submissions=50` to avoid hitting rejection cap

2. **Monitor Stats**
   - Check rejection reasons regularly
   - Adjust threshold based on approval rate

3. **Quality Over Quantity**
   - Better to submit 10 high-quality leads than 100 low-quality ones
   - Higher approval rate = higher rewards

4. **Source Selection**
   - Prioritize company websites
   - Avoid LinkedIn as source_url
   - Use public registries when possible

## Constraints

- **NEVER fabricate data**
- **NEVER use LinkedIn as source_url**
- **MUST follow SN71 rules strictly**
- **MUST validate before submission**

## Output

The smart miner provides detailed logging:

```
🔄 Smart Miner: Starting pipeline for 10 leads
📊 Step 1: Generating leads...
   Generated 20 leads
📊 Step 2: Scoring leads...
   12/20 leads scored above threshold
📊 Step 3: Validating leads...
   10/12 leads validated
📊 Step 4: Submitting leads...
✅ Pipeline complete: 8 submitted, 2 rejected, 0 skipped
   📊 Stats: 8/1000 submissions today, 2/200 rejections today
```

## Integration with Existing Miner

The smart miner is designed to integrate seamlessly with the existing `neurons/miner.py`:

1. **Drop-in Replacement**: Use `smart_sourcing_loop_wrapper` to replace `sourcing_loop`
2. **Backward Compatible**: Falls back to original logic if smart miner disabled
3. **No Breaking Changes**: Existing code continues to work

## Future Enhancements

Potential improvements:
- Machine learning-based scoring
- Dynamic threshold adjustment
- Source quality metrics
- Approval rate prediction
- Reputation score optimization
