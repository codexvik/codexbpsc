"""
Eligibility verdict logic (design doc, section 3.3). Deliberately generic --
reads criteria from an exam's eligibility_json rather than hardcoding any
Bihar-specific numbers (age limits, category relaxations) in code, since we
have no verified source for those yet. An exam with no eligibility_json
correctly reports "unavailable" rather than fabricating a verdict.
"""

from __future__ import annotations

from typing import Optional


def evaluate_eligibility(
    eligibility_json: Optional[dict],
    degree: str,
    age: int,
    category: str,
) -> tuple[Optional[bool], str]:
    if not eligibility_json:
        return None, "Eligibility criteria for this exam haven't been added yet -- check the official notification directly."

    required_degrees = eligibility_json.get("required_degree")
    if required_degrees and degree not in required_degrees:
        return False, f"Required qualification not met -- this exam requires: {', '.join(required_degrees)}."

    min_age = eligibility_json.get("min_age")
    max_age = eligibility_json.get("max_age")
    relaxation = (eligibility_json.get("category_age_relaxation") or {}).get(category, 0)
    effective_max_age = max_age + relaxation if max_age is not None else None

    if min_age is not None and age < min_age:
        return False, f"Minimum age is {min_age}; you are {age}."
    if effective_max_age is not None and age > effective_max_age:
        return False, f"Maximum age (with {category} relaxation) is {effective_max_age}; you are {age}."

    return True, "You meet the degree and age criteria for this exam."
