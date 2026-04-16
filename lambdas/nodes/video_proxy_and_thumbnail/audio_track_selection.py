"""
Audio Track Selection Rule Engine

Pure-Python module for parsing, validating, matching, and resolving
audio track selection rules for the video_proxy_and_thumbnail Lambda.

No AWS dependencies — fully testable in isolation.
"""

import json


def parse_rules(raw_json: str) -> list[dict]:
    """Parse and validate the JSON rules string.

    Validates schema correctness (track numbers ≥ 1, min ≤ max, valid tracks
    field, condition has exactly one of exact/min) AND detects unreachable
    rules whose conditions are fully shadowed by an earlier rule.

    Args:
        raw_json: JSON string from node configuration parameter.
                  Empty string or whitespace returns an empty list.

    Returns:
        List of validated rule dicts.

    Raises:
        ValueError: On malformed JSON, schema validation failure, or when
                    any rule is unreachable due to shadowing by a prior rule.
    """
    if not raw_json or not raw_json.strip():
        return []

    try:
        rules = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed JSON in audio track selection rules: {exc}"
        ) from exc

    if not isinstance(rules, list):
        raise ValueError("Audio track selection rules must be a JSON array")

    for idx, rule in enumerate(rules):
        _validate_rule(rule, idx)

    # Shadowing detection: walk the list and check each rule against all prior conditions
    prior_conditions: list[dict] = []
    for idx, rule in enumerate(rules):
        condition = rule["condition"]
        if prior_conditions and _is_condition_shadowed(condition, prior_conditions):
            # Find which prior rule shadows this one
            for prior_idx, prior_cond in enumerate(prior_conditions):
                if _is_condition_shadowed(condition, [prior_cond]):
                    raise ValueError(
                        f"Rule at index {idx} is unreachable: its condition is fully "
                        f"shadowed by rule at index {prior_idx}. "
                        f"Every track count matching rule {idx} would already match rule {prior_idx}."
                    )
            # Fallback: covered by union of multiple prior conditions
            raise ValueError(
                f"Rule at index {idx} is unreachable: its condition is fully "
                f"covered by the union of earlier rules."
            )
        prior_conditions.append(condition)

    return rules


def _validate_rule(rule: dict, idx: int) -> None:
    """Validate a single rule dict.

    Args:
        rule: The rule dict to validate.
        idx: The index of the rule in the list (for error messages).

    Raises:
        ValueError: If the rule fails schema validation.
    """
    if not isinstance(rule, dict):
        raise ValueError(
            f"Rule at index {idx} must be an object, got {type(rule).__name__}"
        )

    # Validate condition
    if "condition" not in rule:
        raise ValueError(f"Rule at index {idx} is missing required 'condition' field")

    condition = rule["condition"]
    if not isinstance(condition, dict):
        raise ValueError(f"Rule at index {idx}: 'condition' must be an object")

    has_exact = "exact" in condition
    has_min = "min" in condition
    has_max = "max" in condition

    if has_exact and has_min:
        raise ValueError(
            f"Rule at index {idx}: condition must have exactly one of 'exact' or 'min', not both"
        )
    if not has_exact and not has_min:
        raise ValueError(
            f"Rule at index {idx}: condition must have exactly one of 'exact' or 'min'"
        )
    if has_max and not has_min:
        raise ValueError(
            f"Rule at index {idx}: condition has 'max' but no 'min'; "
            f"'max' is only valid alongside 'min'"
        )

    if has_exact:
        exact = condition["exact"]
        if not isinstance(exact, int) or isinstance(exact, bool) or exact < 1:
            raise ValueError(
                f"Rule at index {idx}: condition 'exact' must be an integer ≥ 1, got {exact!r}"
            )

    if has_min:
        min_val = condition["min"]
        if not isinstance(min_val, int) or isinstance(min_val, bool) or min_val < 1:
            raise ValueError(
                f"Rule at index {idx}: condition 'min' must be an integer ≥ 1, got {min_val!r}"
            )

    if has_max:
        max_val = condition["max"]
        if not isinstance(max_val, int) or isinstance(max_val, bool) or max_val < 1:
            raise ValueError(
                f"Rule at index {idx}: condition 'max' must be an integer ≥ 1, got {max_val!r}"
            )
        if max_val < condition["min"]:
            raise ValueError(
                f"Rule at index {idx}: condition 'max' ({max_val}) must be ≥ 'min' ({condition['min']})"
            )

    # Validate tracks
    if "tracks" not in rule:
        raise ValueError(f"Rule at index {idx} is missing required 'tracks' field")

    tracks = rule["tracks"]
    if tracks == "all":
        pass  # valid wildcard
    elif isinstance(tracks, list):
        if len(tracks) == 0:
            raise ValueError(f"Rule at index {idx}: 'tracks' list must not be empty")
        for track_num in tracks:
            if (
                not isinstance(track_num, int)
                or isinstance(track_num, bool)
                or track_num < 1
            ):
                raise ValueError(
                    f"Rule at index {idx}: all track numbers must be integers ≥ 1, got {track_num!r}"
                )
    else:
        raise ValueError(
            f"Rule at index {idx}: 'tracks' must be the string \"all\" or a non-empty list of integers, "
            f"got {tracks!r}"
        )


def match_rule(rules: list[dict], track_count: int) -> dict | None:
    """Return the first rule whose condition matches track_count, or None.

    Condition types:
    - Exact: track_count == condition["exact"]
    - Range: condition["min"] <= track_count <= condition["max"]
    - Min-only: track_count >= condition["min"]

    Args:
        rules: List of validated rule dicts (from parse_rules).
        track_count: Number of audio tracks in the source file.

    Returns:
        The first matching rule dict, or None if no rule matches.
    """
    for rule in rules:
        condition = rule["condition"]
        if _condition_matches(condition, track_count):
            return rule
    return None


def _condition_matches(condition: dict, track_count: int) -> bool:
    """Return True if the condition matches the given track_count."""
    if "exact" in condition:
        return track_count == condition["exact"]
    # min (with optional max)
    min_val = condition["min"]
    if track_count < min_val:
        return False
    if "max" in condition:
        return track_count <= condition["max"]
    return True  # min-only: track_count >= min_val


def resolve_tracks(rule: dict, track_count: int) -> list[int]:
    """Resolve the track list from a matched rule.

    Args:
        rule: A matched rule dict (from match_rule).
        track_count: Number of audio tracks in the source file.

    Returns:
        For explicit tracks: the tracks list as-is.
        For "all": list(range(1, track_count + 1)).
    """
    tracks = rule["tracks"]
    if tracks == "all":
        return list(range(1, track_count + 1))
    return tracks


def validate_track_bounds(
    tracks: list[int],
    track_count: int,
    rule_index: int,
    source_id: str,
) -> None:
    """Raise RuntimeError if any track number exceeds track_count.

    Args:
        tracks: Resolved list of 1-based track numbers.
        track_count: Total number of audio tracks in the source file.
        rule_index: Index of the matched rule (for error messages).
        source_id: Source file identifier (for error messages).

    Raises:
        RuntimeError: If any track number exceeds track_count, with a message
                      including rule_index, out-of-bounds track numbers,
                      track_count, and source_id.
    """
    out_of_bounds = [t for t in tracks if t > track_count]
    if out_of_bounds:
        raise RuntimeError(
            f"Rule at index {rule_index} references out-of-bounds track(s) {out_of_bounds} "
            f"but source file '{source_id}' only has {track_count} audio track(s). "
            f"Please update the rule to reference valid track numbers."
        )


def _is_condition_shadowed(candidate: dict, prior_conditions: list[dict]) -> bool:
    """Return True if candidate condition is fully covered by prior conditions.

    A condition is shadowed when every integer that could match it would also
    match at least one earlier condition. Uses interval arithmetic:
    - {"exact": N}       → interval [N, N]
    - {"min": M, "max": N} → interval [M, N]
    - {"min": M}         → interval [M, ∞)

    For a single prior condition, checks if it fully contains the candidate.
    For multiple prior conditions, checks if their union covers the candidate.

    Args:
        candidate: The condition dict to check.
        prior_conditions: List of earlier condition dicts.

    Returns:
        True if the candidate is fully shadowed by the prior conditions.
    """
    # Represent ∞ as a large sentinel
    INF = float("inf")

    def to_interval(cond: dict) -> tuple[int | float, int | float]:
        if "exact" in cond:
            n = cond["exact"]
            return (n, n)
        min_val = cond["min"]
        max_val = cond.get("max", INF)
        return (min_val, max_val)

    cand_lo, cand_hi = to_interval(candidate)

    # Build list of prior intervals
    prior_intervals = [to_interval(c) for c in prior_conditions]

    # Check if the union of prior intervals covers [cand_lo, cand_hi]
    # Strategy: sweep from cand_lo to cand_hi, checking coverage
    # Sort intervals by start point
    relevant = [
        (lo, hi) for lo, hi in prior_intervals if lo <= cand_hi and hi >= cand_lo
    ]
    if not relevant:
        return False

    relevant.sort(key=lambda x: x[0])

    # Check if the union of relevant intervals covers [cand_lo, cand_hi]
    covered_up_to = (
        cand_lo - 1
    )  # last integer we've confirmed is covered (exclusive start)

    for lo, hi in relevant:
        if lo > covered_up_to + 1:
            # There's a gap between covered_up_to and lo
            return False
        # Extend coverage
        if hi == INF:
            covered_up_to = INF
            break
        covered_up_to = max(covered_up_to, hi)

    # Check if we've covered up to cand_hi
    if cand_hi == INF:
        return covered_up_to == INF
    return covered_up_to >= cand_hi
