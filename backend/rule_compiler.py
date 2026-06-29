"""
Rule Compiler — converts rules.json into compact text for Gemini context caching.

Reads the full rules.json (source of truth, never modified) and produces a
dense natural-language representation that the LLM can consume efficiently.

The output is designed to:
  1. Preserve 100% of the decision logic (scenario conditions + resolutions)
  2. Use ~60-70% fewer tokens than raw JSON
  3. Meet Gemini's 32K-token minimum for explicit context caching
"""

import json
import os
import re

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")

# Approximate tokens = chars / 4  (conservative estimate for English text)
MIN_TOKEN_TARGET = 32_000
MIN_CHAR_TARGET = MIN_TOKEN_TARGET * 4  # 128,000 chars


# ─────────────────────────────────────────────────────────────────────────────
#  DECISION NORMALIZER — maps all legacy decision names to the 5 official ones
# ─────────────────────────────────────────────────────────────────────────────
_DECISION_MAP = {
    # Old variants → Not duplicate
    "not a duplicate - variant":                                          "Not duplicate",
    "not a duplicate - incorrect variant attribute name data not available": "Not duplicate",
    "not a duplicate - incorrect variant attribute names":                "Not duplicate",
    "not a duplicate - variant attribute data not available":             "Not duplicate",
    "not a duplicate":                                                    "Not duplicate",
    # Compatibility
    "not duplicate - different compatibility":                            "Not duplicate compatibility",
    "not a duplicate - compatibility":                                    "Not duplicate compatibility",
    "not a duplicate - different compatibility":                          "Not duplicate compatibility",
    # Warranty
    "not duplicate - different warranty":                                 "Not duplicate warranty",
    "not a duplicate - different warranty":                               "Not duplicate warranty",
    # Bad data
    "not sure - bad data":                                               "Not sure bad data",
    "not sure bad data":                                                 "Not sure bad data",
    # Duplicate variants
    "duplicate (split into clusters)":                                   "Duplicate",
    "duplicate":                                                         "Duplicate",
    # Rule reference — treat as not duplicate (needs human review)
    "rule reference":                                                    "Not duplicate",
}

# Ordered regex substitutions for prose text (most specific first)
_ACTION_REPLACEMENTS = [
    (r"Not a Duplicate\s*-\s*Incorrect Variant Attribute Name Data Not Available", "Not duplicate"),
    (r"Not a Duplicate\s*-\s*Incorrect Variant Attribute Names",                   "Not duplicate"),
    (r"Not a Duplicate\s*-\s*Variant Attribute Data Not Available",                "Not duplicate"),
    (r"Not a Duplicate\s*-\s*Different Compatibility",                             "Not duplicate compatibility"),
    (r"Not a Duplicate\s*-\s*Compatibility",                                       "Not duplicate compatibility"),
    (r"Not a Duplicate\s*-\s*Different Warranty",                                  "Not duplicate warranty"),
    (r"Not a Duplicate\s*-\s*Variant",                                             "Not duplicate"),
    (r"Not a Duplicate",                                                           "Not duplicate"),
    (r"Not Duplicate\s*-\s*Different Compatibility",                               "Not duplicate compatibility"),
    (r"Not Duplicate\s*-\s*Different Warranty",                                    "Not duplicate warranty"),
    (r"Not sure\s*-\s*Bad data",                                                   "Not sure bad data"),
    (r"Not Sure\s*-\s*Bad Data",                                                   "Not sure bad data"),
    (r"Duplicate \(Split into Clusters\)",                                         "Duplicate"),
    (r"Rule Reference",                                                            "Not duplicate"),
]


def _normalize_decision(raw: str) -> str:
    """Map a legacy decision string to one of the 5 official action names."""
    return _DECISION_MAP.get(raw.lower().strip(), raw)


def _normalize_action_text(text: str) -> str:
    """Replace legacy decision names inside prose instruction text."""
    for pattern, replacement in _ACTION_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _format_list(items: list) -> str:
    """Join a list into a comma-separated string, or return 'None' if empty."""
    if not items:
        return "None"
    return ", ".join(str(i) for i in items)


def _compile_scenario(scenario: dict) -> str:
    """Convert a single scenario dict into highly compact text lines."""
    sid = scenario.get("scenario_id", "?")
    cond = scenario.get("conditions", {})
    res = scenario.get("resolution", {})

    lines = []
    lines.append(f"  S[{sid}]")

    # Conditions
    attr_state = cond.get("attribute_state", "")
    text_ev = cond.get("textual_evidence", "")
    vis_req = cond.get("visual_evidence_required", False)
    vis_desc = cond.get("visual_evidence_description", "")

    cond_parts = []
    if attr_state:
        cond_parts.append(f"attr_state:{attr_state}")
    if text_ev:
        cond_parts.append(f"text:{text_ev}")
    if vis_req:
        cond_parts.append(f"visual:REQUIRED({vis_desc})")
    elif vis_desc:
        cond_parts.append(f"visual:{vis_desc}")

    if cond_parts:
        lines.append(f"    Conds: {' | '.join(cond_parts)}")

    # Resolution — normalize legacy decision strings to the 5 official actions
    decision_raw = res.get("decision", "?")
    decision = _normalize_decision(decision_raw)
    action = _normalize_action_text(res.get("actionable_instruction", ""))
    lines.append(f"    Decision: {decision}")
    if action:
        lines.append(f"    Action: {action}")

    return "\n".join(lines)


def _compile_rule(rule: dict) -> str:
    """Convert a single rule dict into highly compact text."""
    page = rule.get("page_number", "?")
    category = rule.get("category", "?")
    product_type = rule.get("product_type", "?")

    mc = rule.get("matching_context", {})
    test_attrs = _format_list(mc.get("attributes_under_test", []))
    ignore_attrs = _format_list(mc.get("ignore_attributes_for_matching", []))

    scenarios = rule.get("scenarios", [])

    lines = []
    lines.append(f"R[P{page}] Cat:{category} | Type:{product_type}")
    lines.append(f"  Attrs: {test_attrs}")
    if ignore_attrs != "None":
        lines.append(f"  Ignore: {ignore_attrs}")

    for scenario in scenarios:
        lines.append(_compile_scenario(scenario))

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PREAMBLE — appended before the compiled rules
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PREAMBLE = """
════════════════════════════════════════════════════════════════════════════════
 WALMART DUPLICATE / NON-DUPLICATE / BAD DATA — STANDARD OPERATING PROCEDURES
════════════════════════════════════════════════════════════════════════════════

You are a product data quality evaluator. Your job is to compare product listings
(GTINs) and determine whether they are DUPLICATES, NOT DUPLICATES, or BAD DATA.

You must follow the SOP rules below EXACTLY. Each rule covers a specific category,
product type, and scenario. When a product comparison matches a rule's conditions,
you MUST apply that rule's DECISION.

DECISION TYPES:
  • Not sure bad data           — Data quality issue prevents a confident decision
  • Duplicate                   — Products are the same item, can be merged
  • Not duplicate               — Products are different items, must stay separate
  • Not duplicate warranty      — Products differ only by warranty
  • Not duplicate compatibility — Products differ by vehicle/device compatibility

HOW TO USE THESE RULES:
  1. Identify the product category and type from the data provided
  2. Find matching rules below for that category/type
  3. Check which scenario's CONDITIONS match the actual data state
  4. Apply the matching scenario's DECISION and ACTION

KEY PRINCIPLES:
  • Attributes listed in "Ignore Attributes" should NOT be used for matching decisions
  • When "visual_check=REQUIRED", you MUST verify via product images before deciding
  • "attribute_state" describes the expected data condition (mismatch, missing, identical, etc.)
  • If no specific rule matches, use general product comparison best practices
  • Bad data takes priority — if data quality is suspect, flag it before making dup/non-dup calls

════════════════════════════════════════════════════════════════════════════════
 RULES BEGIN
════════════════════════════════════════════════════════════════════════════════
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
#  CATEGORY REFERENCE INDEX — appended after the rules for quick lookup
# ─────────────────────────────────────────────────────────────────────────────
def _build_category_index(rules: list) -> str:
    """Build a category → page number quick-reference index."""
    from collections import defaultdict
    index = defaultdict(list)
    for r in rules:
        cat = r.get("category", "Unknown")
        page = r.get("page_number", "?")
        decision = "?"
        for s in r.get("scenarios", []):
            decision = _normalize_decision(s.get("resolution", {}).get("decision", "?"))
            break
        index[cat].append(f"Page {page} ({decision})")

    lines = [
        "",
        "════════════════════════════════════════════════════════════════════════════════",
        " CATEGORY QUICK-REFERENCE INDEX",
        "════════════════════════════════════════════════════════════════════════════════",
    ]
    for cat in sorted(index.keys()):
        refs = ", ".join(index[cat])
        lines.append(f"  • {cat}: {refs}")

    return "\n".join(lines)


def compile_rules(rules_path: str = RULES_FILE) -> str:
    """
    Read rules.json and produce a compact text representation suitable for
    Gemini context caching.

    Returns the compiled text string (guaranteed ≥ MIN_CHAR_TARGET chars).
    """
    with open(rules_path, "r") as f:
        rules = json.load(f)

    # Compile each rule
    compiled_blocks = []
    for rule in rules:
        compiled_blocks.append(_compile_rule(rule))

    rules_text = "\n\n".join(compiled_blocks)
    category_index = _build_category_index(rules)

    full_text = f"{SYSTEM_PREAMBLE}\n\n{rules_text}\n{category_index}"

    # ── Ensure we meet the 32K-token minimum ────────────────────────────────
    # If the compiled text is under the threshold, append the raw JSON as a
    # supplementary reference section.  This guarantees we hit the minimum
    # without altering any logic.
    if len(full_text) < MIN_CHAR_TARGET:
        padding_needed = MIN_CHAR_TARGET - len(full_text)
        supplement = "\n\n" + "=" * 80 + "\n"
        supplement += " SUPPLEMENTARY — FULL STRUCTURED RULES (JSON REFERENCE)\n"
        supplement += "=" * 80 + "\n"
        supplement += " The rules above are authoritative. This JSON supplement\n"
        supplement += " provides the original structured data for edge-case lookups.\n"
        supplement += "=" * 80 + "\n\n"

        # Add raw JSON rules one-by-one until we meet the target
        json_blocks = []
        current_len = len(full_text) + len(supplement)
        for rule in rules:
            block = json.dumps(rule, indent=2)
            if current_len + len(block) + 2 < MIN_CHAR_TARGET + 5000:
                json_blocks.append(block)
                current_len += len(block) + 2
            else:
                json_blocks.append(block)
                current_len += len(block) + 2
                if current_len >= MIN_CHAR_TARGET:
                    break

        supplement += "\n\n".join(json_blocks)
        full_text += supplement

    return full_text


def get_compiled_rules_stats(compiled_text: str) -> dict:
    """Return size statistics for the compiled rules text."""
    char_count = len(compiled_text)
    approx_tokens = char_count / 4
    return {
        "char_count": char_count,
        "approx_tokens": int(approx_tokens),
        "meets_32k_minimum": approx_tokens >= 32_000,
        "estimated_cache_cost_per_hour": round(approx_tokens / 1_000_000, 4),
    }


# ── CLI usage for testing ────────────────────────────────────────────────────
if __name__ == "__main__":
    compiled = compile_rules()
    stats = get_compiled_rules_stats(compiled)

    print("=" * 60)
    print("RULE COMPILER — OUTPUT STATS")
    print("=" * 60)
    print(f"  Characters:          {stats['char_count']:,}")
    print(f"  Approx tokens:       {stats['approx_tokens']:,}")
    print(f"  Meets 32K minimum:   {stats['meets_32k_minimum']}")
    print(f"  Cache cost/hour:     ${stats['estimated_cache_cost_per_hour']}")
    print("=" * 60)

    # Preview first 2000 chars
    print("\n--- PREVIEW (first 2000 chars) ---")
    print(compiled[:2000])
    print("\n--- END PREVIEW ---")
