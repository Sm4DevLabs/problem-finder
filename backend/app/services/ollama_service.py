import json

import ollama
from ollama import ResponseError

from app.database.database_session import settings
from app.schemas.assessment_schema import AssessmentResult


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
