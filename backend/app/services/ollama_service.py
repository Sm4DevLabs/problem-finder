import json

import ollama
from ollama import ResponseError

from app.database.database_session import settings
from app.schemas.assessment_schema import AssessmentResult
from app.schemas.evidence_schema import EvidenceSummary


async def chat_with_ollama(prompt: str) -> dict:
    """
    Send a prompt to the local Ollama model and return the response.

    Args:
        prompt: The text prompt to send to the model

    Returns:
        dict with 'model', 'response', and 'success' fields

    Raises:
        Exception if Ollama is unavailable
    """
    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return {
            "success": True,
            "model": settings.OLLAMA_MODEL,
            "response": response["message"]["content"],
        }

    except ResponseError as e:
        raise Exception(f"Ollama error: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to connect to Ollama at {settings.OLLAMA_BASE_URL}: {str(e)}")


async def assess_source_with_evidence(
    source_name: str,
    source_type: str,
    homepage_url: str,
    evidence_summary: EvidenceSummary,
) -> AssessmentResult:
    """
    Use Ollama to assess a source WITH collected evidence.

    This function sends ACTUAL EVIDENCE to the AI instead of just source name/URL.

    Args:
        source_name: Name of the source
        source_type: Type of source
        homepage_url: Homepage URL
        evidence_summary: Collected evidence (API docs, robots.txt, etc.)

    Returns:
        AssessmentResult with recommended_method, reason, confidence, evidence_needed
    """
    # Build evidence context for AI
    evidence_context = _build_evidence_context(evidence_summary)

    # Build the assessment prompt WITH EVIDENCE
    prompt = f"""You are an expert data collection analyst. You have collected evidence about this source.

Source Information:
- Name: {source_name}
- Type: {source_type}
- Homepage: {homepage_url}

EVIDENCE COLLECTED:
{evidence_context}

Task: Based on ONLY the evidence provided above, determine the best collection method.

Respond ONLY with valid JSON in this exact format:

{{
  "recommended_method": "API" | "WEB_SCRAPING" | "MANUAL",
  "reason": "Evidence-based explanation citing the evidence above",
  "confidence": 0.0 to 1.0,
  "evidence_needed": ["list of missing verification steps"]
}}

STRICT RULES:
1. Choose API ONLY if evidence confirms a documented API exists
2. Choose WEB_SCRAPING ONLY if no API was found AND robots.txt permits crawling
3. Choose MANUAL when evidence is missing, contradictory, or unclear
4. NEVER infer API existence without evidence
5. Cite specific evidence in your reason (e.g., "API documentation found at...")
6. Set confidence based on evidence quality:
   - Complete evidence with API docs = 0.90-0.95
   - Partial evidence (homepage + robots.txt) = 0.60-0.75
   - No evidence or unclear = 0.30-0.50
7. When uncertain, choose MANUAL and list what evidence is needed

Respond with ONLY the JSON, no markdown or extra text."""

    try:
        # Call Ollama with JSON format enforcement
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
        )

        # Extract and validate JSON
        json_response = response["message"]["content"]
        assessment = AssessmentResult.model_validate_json(json_response)

        return assessment

    except ResponseError as e:
        raise Exception(f"Ollama error during assessment: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Ollama returned invalid JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Assessment failed: {str(e)}")


def _build_evidence_context(evidence_summary: EvidenceSummary) -> str:
    """Build evidence context string for AI prompt."""
    lines = []

    if evidence_summary.evidence_quality == "NONE":
        return "⚠️ NO EVIDENCE COLLECTED - Unable to verify API or access methods."

    if evidence_summary.api_docs_url:
        lines.append(f"✅ API Documentation: {evidence_summary.api_docs_url}")
        if evidence_summary.api_docs_excerpt:
            excerpt = evidence_summary.api_docs_excerpt[:500]
            lines.append(f"   Excerpt: {excerpt}...")
    else:
        lines.append("❌ No API documentation found")

    if evidence_summary.robots_txt:
        robots_excerpt = evidence_summary.robots_txt[:300]
        lines.append(f"\n📄 robots.txt: {robots_excerpt}...")
    else:
        lines.append("\n⚠️ robots.txt not found or not accessible")

    if evidence_summary.homepage:
        lines.append(f"\n🏠 Homepage: {evidence_summary.homepage}")

    if evidence_summary.github_repository:
        lines.append(f"\n🔗 GitHub Repository: {evidence_summary.github_repository}")

    lines.append(f"\n📊 Evidence Quality: {evidence_summary.evidence_quality}")

    return "\n".join(lines)


async def assess_source_with_ollama(source_name: str, source_type: str, homepage_url: str) -> AssessmentResult:
    """
    Use Ollama to assess the best data collection method for a source.

    This function sends a structured prompt to Ollama and enforces JSON schema validation
    on the response using Pydantic.

    Args:
        source_name: Name of the source (e.g., "Reddit")
        source_type: Type of source (e.g., "CUSTOMER_COMPLAINTS")
        homepage_url: URL of the source homepage

    Returns:
        AssessmentResult with recommended_method, reason, confidence, evidence_needed

    Raises:
        Exception if Ollama fails or returns invalid JSON
    """
    # Build the assessment prompt
    prompt = f"""You are an expert data collection analyst. Analyze this source and determine the best data collection method.

Source Information:
- Name: {source_name}
- Type: {source_type}
- Homepage: {homepage_url}

Task: Determine the best collection method and respond ONLY with valid JSON in this exact format:

{{
  "recommended_method": "API" | "WEB_SCRAPING" | "MANUAL",
  "reason": "Brief evidence-based explanation",
  "confidence": 0.0 to 1.0,
  "evidence_needed": ["list of things to verify, if any"]
}}

Rules:
1. Choose API ONLY if you know for certain a public documented API exists (e.g., Reddit API, GitHub API, Kaggle API)
2. Choose WEB_SCRAPING if no well-documented public API exists but the site has structured HTML
3. Choose MANUAL if data requires human curation or involves complex authentication
4. Be conservative - when uncertain about an API, default to WEB_SCRAPING
5. Set confidence to 0.6 or lower if you're not certain about API availability
6. List verification steps needed (e.g., "Check API documentation", "Verify endpoint access")

Common sources with known APIs:
- Reddit: reddit.com/dev/api
- GitHub: api.github.com
- Kaggle: kaggle.com/docs/api
- Data.gov: data.gov/developers

Respond with ONLY the JSON, no markdown formatting or extra text."""

    try:
        # Call Ollama with JSON format enforcement
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",  # This tells Ollama to return valid JSON
        )

        # Extract JSON from response
        json_response = response["message"]["content"]

        # Parse and validate with Pydantic
        assessment = AssessmentResult.model_validate_json(json_response)

        return assessment

    except ResponseError as e:
        raise Exception(f"Ollama error during assessment: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Ollama returned invalid JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Assessment failed: {str(e)}")
