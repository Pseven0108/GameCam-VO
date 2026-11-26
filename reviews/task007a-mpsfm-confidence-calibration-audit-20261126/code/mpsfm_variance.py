"""Unfitted CPU float64 reference for MP-SfM's finite, positive single prior.

This is a source-derived algebraic mapping, NOT a VIPER uncertainty calibration.
No GT reader, fitting, model import or baseline integration is included.
See SOURCE_METHOD_AUDIT.md for exact upstream scope and reference defaults.
"""
from __future__ import annotations

import numpy as np


def _inputs(depth, confidence):
    d = np.asarray(depth, dtype=np.float64)
    c = np.asarray(confidence, dtype=np.float64)
    if d.shape != c.shape or d.size == 0:
        raise ValueError("Nonempty matching grids are required; broadcasting is forbidden")
    if not np.isfinite(d).all() or (d <= 0).any():
        raise ValueError("Finite positive predicted depth required; never hide bad predictions")
    if not np.isfinite(c).all():
        raise ValueError("Finite raw Confidence required")
    return d, c


def mp_sfm_raw_variance(depth, confidence):
    """[d * (1 - clip(c, 0, 1))]^2, after spatial restoration.

    Upstream Metric3Dv2.step() restores confidence before clipping it. The caller
    must supply a depth and confidence pair on the same verified spatial grid.
    Result units are depth_units**2. Values can be exactly zero at c >= 1.
    """
    d, c = _inputs(depth, confidence)
    with np.errstate(over="raise", invalid="raise"):
        return np.square(d * (1.0 - np.clip(c, 0.0, 1.0)))


def _nonnegative(name, value, *, positive=False):
    x = float(value)
    if not np.isfinite(x) or (x <= 0 if positive else x < 0):
        raise ValueError(f"Invalid {name}")
    return x


def mp_sfm_single_prior_variance(
    depth, confidence, *, prior_std_multiplier=3.33, depth_uncertainty=0.0263,
    inherent_noise=0.02, std_multiplier=1.0, max_std=None,
):
    """Source-default single-prior variance including the floors/scales.

    Reproduces Depth._init's prior_uncertainty=True, flip_consistency=False,
    depth_uncertainty!=None arithmetic for finite positive already-restored
    inputs. It does not emulate continuity/validity masks, depth replacement,
    keypoint sampling, fused priors or camera resizing. These defaults are
    upstream reference constants, not fitted or validated for VIPER/Metric3D-L.
    Absolute floors use the caller's depth unit; they cannot certify that unit.
    """
    d, c = _inputs(depth, confidence)
    a = _nonnegative("prior_std_multiplier", prior_std_multiplier)
    r = _nonnegative("depth_uncertainty", depth_uncertainty)
    n = _nonnegative("inherent_noise", inherent_noise)
    s = _nonnegative("std_multiplier", std_multiplier, positive=True)
    upper = None if max_std is None else _nonnegative("max_std", max_std, positive=True)
    if upper is not None and upper < n:
        raise ValueError("max_std below inherent_noise would invalidate the floor")
    with np.errstate(over="raise", invalid="raise"):
        variance = np.maximum(mp_sfm_raw_variance(d, c) * a**2, np.square(d * r))
        variance = np.maximum(variance, n**2)
        if upper is not None:
            variance = np.minimum(variance, upper**2)
        return variance * s**2
