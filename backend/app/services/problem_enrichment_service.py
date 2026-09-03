"""
Unified AI enrichment for collected problems.

Every problem is normalized to the same shape, regardless of source:

1. Describe the problem            -> description
2. How often does it occur         -> problem_frequency
3. Attempts / apps solving it       -> existing_solutions
4. Willingness to pay / pricing     -> pricing_estimate
5. Problem author                   -> problem_author

Analytical fields (2, 3, 4) are kept when a source already provides them
(e.g. ProblemHunt answers) and AI-generated only when missing. Tech-stack
recommendations are ALWAYS brainstormed by AI for every problem:

- tech_stack_options       (2-4 candidate stacks with pros/cons)
- recommended_tech_stack   (the best option)
- tech_stack_justification (why it is the best fit)
"""

from app.services import llm_service

# Canonical solution-type tags. The AI must choose from this closed set so the
# frontend can offer consistent tag filtering. "Not Software-Solvable" marks
# problems that cannot be solved with software (common in Razorpay's set).
SOLUTION_TAGS = [
    "Web App",
    "Mobile App",
    "Browser Extension",
    "Desktop App",
    "Library / SDK",
    "API / Backend Service",
    "AI / ML",
    "Automation / Bot",
    "Not Software-Solvable",
]
_TAG_LOOKUP = {tag.lower(): tag for tag in SOLUTION_TAGS}

# Substring synonyms so slightly-off AI phrasings still map to a canonical tag
# (order matters: more specific checks first).
_TAG_SYNONYMS = [
    (("not software", "non-software", "hardware", "physical", "offline", "not solvable"), "Not Software-Solvable"),
    (("browser extension", "extension", "chrome extension", "plugin"), "Browser Extension"),
    (("mobile", "ios", "android", "app store"), "Mobile App"),
    (("desktop", "electron", "native app"), "Desktop App"),
    (("library", "sdk", "package"), "Library / SDK"),
    (("api", "backend", "service", "server"), "API / Backend Service"),
    (("ai", "ml", "machine learning", "llm", "model"), "AI / ML"),
    (("automation", "bot", "script", "workflow"), "Automation / Bot"),
    (("web", "website", "saas", "dashboard", "portal"), "Web App"),
]


def _canonical_tag(value: str) -> str | None:
    key = value.strip().lower()
    if not key:
        return None
    if key in _TAG_LOOKUP:
        return _TAG_LOOKUP[key]
    for needles, canonical in _TAG_SYNONYMS:
        if any(n in key for n in needles):
            return canonical
    return None


# Strict, authoritative solvability check. A capable model follows this rule well;
# it prevents "a reporting app could help" from marking a physically-rooted problem
# as software-solvable.
_CLASSIFY_PROMPT = """Classify how software relates to this problem.

CRITICAL RULE: A reporting app, marketplace, directory, or coordination tool that
merely connects people to a PHYSICAL service (repair, plumbing, cleaning, delivery,
construction, cooking, manufacturing, physically handling goods) does NOT count as
solving the problem. If the CORE fix is a physical act, answer "physical" even
though an app could help coordinate it.
Answer "software" only when software itself delivers the core value (e.g. a CRM, a
fintech flow, a website builder, an analytics/AI tool, a booking system where the
software IS the product).

Problem: {title}
Details: {description}
JSON only: {{"kind": "software" or "physical", "why": "few words"}}"""


def _has_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


async def classify_solvability(title: str, description: str) -> tuple[str, str]:
    """Return ("software"|"physical", why). Defaults to "software" on failure so
    problems are never wrongly marked non-software."""
    prompt = _CLASSIFY_PROMPT.format(title=title or "", description=description or title or "")
    try:
        data = await llm_service.chat_json(prompt, temperature=0)
    except Exception as e:  # noqa: BLE001
        print(f"[enrichment] solvability check failed: {e}")
        return "software", ""
    kind = str(data.get("kind", "software")).strip().lower()
    why = data.get("why") if _has_text(data.get("why")) else ""
    return ("physical" if kind.startswith("phys") else "software"), why


def _normalize_tags(raw) -> list[str]:
    """Map AI-returned tags onto the canonical vocabulary, dropping unknowns."""
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for tag in raw:
        if not isinstance(tag, str):
            continue
        canonical = _canonical_tag(tag)
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    # "Not Software-Solvable" is exclusive: if present, it is the only tag.
    if "Not Software-Solvable" in normalized:
        return ["Not Software-Solvable"]
    return normalized


def _build_prompt(problem: dict) -> str:
    title = (problem.get("title") or "").strip()
    description = (problem.get("description") or "").strip()
    raw = problem.get("raw_data") or {}
    category = raw.get("category") or raw.get("industry") or ""

    known_lines = []
    if _has_text(problem.get("problem_frequency")):
        known_lines.append(f"- Known frequency: {problem['problem_frequency']}")
    if _has_text(problem.get("existing_solutions")):
        known_lines.append(f"- Known existing solutions / attempts: {problem['existing_solutions']}")
    if _has_text(problem.get("pricing_estimate")):
        known_lines.append(f"- Known willingness to pay: {problem['pricing_estimate']}")
    known_block = "\n".join(known_lines) or "- (none provided; infer sensible values)"

    tag_list = ", ".join(f'"{t}"' for t in SOLUTION_TAGS)

    return f"""You are a product and software-architecture analyst. Analyze the problem below
and return a strict JSON object describing how (and whether) a software product could solve it.

Problem title: {title}
Problem description: {description or title}
Category / industry: {category or "unknown"}

Fields already collected from the source (keep them accurate, do not contradict):
{known_block}

Produce ALL of the following:
- "solution_tags": an array choosing ONLY from this exact list: [{tag_list}].
  Pick the 1-3 BEST-FIT mediums that could solve this problem (do NOT list every
  option). Most business, fintech, marketplace, booking, and information problems
  are software-solvable. Only return exactly ["Not Software-Solvable"] when the
  core of the problem is a physical act software cannot perform (e.g. physically
  repairing, manufacturing, cooking, or handling goods) and no software product
  would meaningfully solve it.
- "solution_approach": 1-2 sentences explaining concretely HOW such a product would
  solve the problem — or, for ["Not Software-Solvable"], why software cannot solve
  the core problem and what is actually required.
- "problem_frequency": one short sentence on how often this problem occurs.
- "existing_solutions": current tools/apps that try to solve this and their gaps.
- "pricing_estimate": realistic price a solution could charge (or users would pay).
- "tech_stack_options": an array of 2-4 objects, each {{"name": str, "technologies": [str, ...], "pros": str, "cons": str}}.
- "recommended_tech_stack": one object {{"name": str, "technologies": [str, ...]}} chosen from the options.
- "tech_stack_justification": one or two sentences on why the recommended stack is best.

Respond with ONLY valid JSON in exactly this shape:
{{
  "solution_tags": ["Web App", "Mobile App"],
  "solution_approach": "...",
  "problem_frequency": "...",
  "existing_solutions": "...",
  "pricing_estimate": "...",
  "tech_stack_options": [
    {{"name": "Stack 1", "technologies": ["React", "Node.js", "PostgreSQL"], "pros": "...", "cons": "..."}},
    {{"name": "Stack 2", "technologies": ["Next.js", "Python", "MongoDB"], "pros": "...", "cons": "..."}}
  ],
  "recommended_tech_stack": {{"name": "Stack 1", "technologies": ["React", "Node.js", "PostgreSQL"]}},
  "tech_stack_justification": "..."
}}
No markdown, no commentary."""


async def enrich_problem(problem: dict) -> dict:
    """
    Enrich a single problem dict in place and return it.

    - Fills problem_frequency / existing_solutions / pricing_estimate only when the
      source did not already provide them.
    - Always (re)generates tech_stack_options / recommended_tech_stack /
      tech_stack_justification.

    On any AI failure, the problem is returned with whatever fields were already
    present so the fetch pipeline never breaks on a single item.
    """
    # Authoritative, strict solvability judgment (short, fast call).
    kind, why = await classify_solvability(
        problem.get("title") or "", problem.get("description") or ""
    )

    enriched: dict = {}
    try:
        # Uses hosted NIM when configured, else local Ollama (see llm_service).
        result = await llm_service.chat_json(_build_prompt(problem))
        if isinstance(result, dict):
            enriched = result
    except Exception as e:  # noqa: BLE001 - never let one bad item abort a fetch
        print(f"[enrichment] AI enrichment failed for '{problem.get('title', '')[:60]}': {e}")

    # Analytical fields: keep scraped values, fall back to AI for gaps.
    if not _has_text(problem.get("problem_frequency")) and _has_text(enriched.get("problem_frequency")):
        problem["problem_frequency"] = enriched["problem_frequency"].strip()
    if not _has_text(problem.get("existing_solutions")) and _has_text(enriched.get("existing_solutions")):
        problem["existing_solutions"] = enriched["existing_solutions"].strip()
    if not _has_text(problem.get("pricing_estimate")) and _has_text(enriched.get("pricing_estimate")):
        problem["pricing_estimate"] = enriched["pricing_estimate"].strip()

    # Solution classification: which mediums can solve it + how.
    tags = _normalize_tags(enriched.get("solution_tags"))
    if tags:
        problem["solution_tags"] = tags
    if _has_text(enriched.get("solution_approach")):
        problem["solution_approach"] = enriched["solution_approach"].strip()

    # The strict classifier is authoritative for the software/physical split.
    if kind == "physical":
        problem["solution_tags"] = ["Not Software-Solvable"]
        if why:
            problem["solution_approach"] = f"Not solvable by software alone: {why}."

    not_software = problem.get("solution_tags") == ["Not Software-Solvable"]

    # Tech stack recommendations: always AI-generated, except when the problem is
    # not software-solvable (a stack would be meaningless).
    if not_software:
        problem["tech_stack_options"] = None
        problem["recommended_tech_stack"] = None
        problem["tech_stack_justification"] = None
    else:
        options = enriched.get("tech_stack_options")
        if isinstance(options, list) and options:
            problem["tech_stack_options"] = options
        recommended = enriched.get("recommended_tech_stack")
        if isinstance(recommended, dict) and recommended:
            problem["recommended_tech_stack"] = recommended
        if _has_text(enriched.get("tech_stack_justification")):
            problem["tech_stack_justification"] = enriched["tech_stack_justification"].strip()

    return problem
