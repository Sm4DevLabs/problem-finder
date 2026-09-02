# 🚀 ProblemFinder: Ready for Data Collection

## ✅ Assessment Complete

The system has successfully assessed 8 active sources focused on **real problems that can become apps** (not open-source contribution tasks).

---

## 📊 Active Sources (Ready for Connectors)

### 📡 API Sources (7)

| Source | Type | Confidence | Access Method |
|--------|------|------------|---------------|
| **Razorpay Fix My Itch** | PEOPLE_SUBMITTED_PROBLEMS | 95% | GitHub API → `razorpay-fix-my-itch` organization |
| **Hacker News** | COMMUNITY_PAIN_DISCUSSIONS | 95% | Firebase API → `/askstories` endpoint |
| **Reddit** | COMMUNITY_PAIN_DISCUSSIONS | 95% | Reddit OAuth API → targeted subreddits |
| **Stack Exchange** | COMMUNITY_PAIN_DISCUSSIONS | 95% | Stack Exchange API → questions |
| **CFPB Consumer Complaint Database** | CUSTOMER_COMPLAINTS | 95% | Public API → structured complaints |
| **Civic Tech Field Guide** | CIVIC_PUBLIC_PROBLEMS | 95% | REST API → civic tech projects |
| **Kaggle Competitions** | CHALLENGE_STATEMENTS | 95% | Kaggle API → competition challenges |

### 🕷️ Web Scraping Sources (1)

| Source | Type | Confidence | Method |
|--------|------|------------|--------|
| **ProblemHunt** | PEOPLE_SUBMITTED_PROBLEMS | 35% | Sitemap-based crawling with rate limits |

---

## 🎯 Recommended First Connector

**Start with: Razorpay Fix My Itch**

**Why:**
1. ✅ Highest quality - explicitly curated problems
2. ✅ Simplest integration - GitHub API (familiar, well-documented)
3. ✅ Structured data - categories, descriptions, problem statements
4. ✅ No authentication complexity - public repositories
5. ✅ Closest to your product vision - real problems worth solving

**What it provides:**
- Curated problem statements across categories
- Each problem has: title, description, category, tags
- Direct from the source that inspired ProblemFinder

---

## 📋 Next Implementation Steps

### 1. Create `source_items` Table

```sql
CREATE TABLE source_items (
    id UUID PRIMARY KEY,
    source_id UUID REFERENCES sources(id),
    
    -- Original data from source
    external_id VARCHAR(255),
    title TEXT NOT NULL,
    description TEXT,
    url VARCHAR(500),
    raw_data JSONB,
    
    -- Metadata
    fetched_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(source_id, external_id)
);
```

### 2. Build Razorpay Connector

**File:** `backend/app/connectors/razorpay_fix_my_itch_connector.py`

**Flow:**
```python
1. Use GitHub API to list repos in razorpay-fix-my-itch org
2. For each repo:
   - Fetch README.md
   - Extract problem statement
   - Parse category from repo name/description
3. Store as SourceItem with:
   - title = repo name
   - description = README content
   - external_id = repo full name
   - raw_data = full GitHub response
```

### 3. Add Fetch Endpoint

```python
POST /api/sources/{source_id}/fetch
→ Triggers connector for that source
→ Returns: { items_fetched: 20, items_new: 15, items_updated: 5 }
```

### 4. Update Frontend

Add "🔄 Fetch Items" button to sources table (only for active sources).

---

## 💾 Database State

- ✅ 8 active sources ready
- ✅ 6 inactive sources (add connectors later)
- ✅ 0 MANUAL sources (fully autonomous)
- ✅ Evidence validated with CAPTCHA/login detection
- ✅ Idempotent evidence collection (no duplicates)
- ✅ Assessment confidence based on actual evidence

---

## 🔧 System Architecture

```
User clicks "Fetch Items"
    ↓
FastAPI endpoint /api/sources/{id}/fetch
    ↓
Connector factory picks correct connector
    ↓
Razorpay connector calls GitHub API
    ↓
Parse and validate items
    ↓
Store in source_items table (upsert)
    ↓
Return count of new/updated items
    ↓
Frontend refreshes item list
```

---

## 🚫 What Was Removed

### Sources Removed (Wrong Focus)
- ❌ GitHub Issues → OSS contribution, not app opportunities
- ❌ Good First Issue → OSS contribution, not app opportunities  
- ❌ G2 → No clear API, unclear permission
- ❌ Devpost → Low confidence, no clear access
- ❌ Challenge.gov → No verified API yet

### Collection Method Removed
- ❌ MANUAL → Defeats autonomous product vision

**Result:** ProblemFinder is now purely autonomous - no human copy-paste required.

---

## 📈 Evidence-Based Decisions

All assessments now use validated evidence:

| Evidence Type | Validation |
|---------------|------------|
| **API_DOCS** | ✅ Checks for API indicators (endpoint, authentication, rate limit) |
| **ROBOTS_TXT** | ✅ Validates format (User-agent, Disallow, Allow) |
| **CAPTCHA/Login** | ✅ Deterministic detection (not AI guessing) |

**Status Types:**
- `VALID` - Content verified, usable for decisions
- `BLOCKED` - CAPTCHA/bot protection detected
- `AUTH_REQUIRED` - Login page detected
- `NOT_FOUND` - 404 response
- `FAILED` - Network/SSL error

---

## 🎉 Ready to Build First Connector

Everything is in place to start collecting real problems:

1. ✅ Database schema ready
2. ✅ Evidence system validated
3. ✅ Sources assessed and active
4. ✅ Architecture designed
5. ✅ No blockers

**Next command:**
```bash
# Create source_items table migration
alembic revision -m "create_source_items_table"

# Build Razorpay connector
touch backend/app/connectors/razorpay_fix_my_itch_connector.py

# Start collecting real problems!
```

---

## 📚 Documentation

- Assessment logic: `app/services/ollama_service.py`
- Evidence collection: `app/services/evidence_service.py`
- Validation rules: `app/services/evidence_validation_service.py`
- Source model: `app/models/source_model.py`
- Seed data: `app/scripts/seed_script.py`

---

Generated: 2026-09-01
System: ProblemFinder Backend v1.0
Assessment: Evidence-based with Ollama (qwen2.5:14b)
