from __future__ import annotations

import numpy as np


def timestamp_diagnostics(values: np.ndarray, gap_factor: float = 2.0) -> dict:
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    delta = np.diff(values)
    positive = delta[np.isfinite(delta) & (delta > 0)]
    median = float(np.median(positive)) if len(positive) else None
    return {"count": len(values), "missing": int((~finite).sum()),
            "strictly_increasing": bool(finite.all() and np.all(delta > 0)),
            "duplicate_count": int(len(values[finite]) - len(np.unique(values[finite]))),
            "nonpositive_intervals": int(np.sum(delta <= 0)),
            "median_interval_seconds": median,
            "large_gap_indices": np.where(delta > gap_factor * median)[0].tolist() if median else []}


def match_timestamps(query: np.ndarray, reference: np.ndarray, tolerance: float) -> tuple[np.ndarray, np.ndarray]:
    """Nearest timestamps, one-to-one, no interpolation or implicit clock reset."""
    query, reference = np.asarray(query, float), np.asarray(reference, float)
    if tolerance < 0 or not np.isfinite(tolerance):
        raise ValueError("Invalid timestamp tolerance")
    for values in (query, reference):
        if not np.isfinite(values).all() or np.any(np.diff(values) <= 0):
            raise ValueError("Timestamps must be finite, strictly increasing and unique")
    indices = np.full(len(query), -1, dtype=int)
    errors = np.full(len(query), np.nan)
    if not len(reference):
        return indices, errors
    for i, value in enumerate(query):
        right = np.searchsorted(reference, value)
        candidates = [j for j in (right - 1, right) if 0 <= j < len(reference)]
        distances = np.array([abs(value - reference[j]) for j in candidates])
        if len(distances) == 2 and np.isclose(distances[0], distances[1], atol=1e-12, rtol=0):
            continue  # An equally near pair is ambiguous, even within tolerance.
        j = candidates[int(np.argmin(distances))]
        error = abs(value - reference[j])
        if error <= tolerance:
            indices[i], errors[i] = j, error
    matched = indices[indices >= 0]
    if len(np.unique(matched)) != len(matched):
        raise ValueError("Many-to-one timestamp association; mapping is not trustworthy")
    return indices, errors
