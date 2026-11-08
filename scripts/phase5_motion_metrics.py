"""Explicit motion ranking, fixed operating points and calibration statistics."""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def binary_statistics(labels, predicted):
    y, p = np.asarray(labels, bool).ravel(), np.asarray(predicted, bool).ravel()
    if y.shape != p.shape or not len(y):
        raise ValueError("Matching nonempty binary support required")
    tp, fp = int(np.sum(y & p)), int(np.sum(~y & p))
    fn, tn = int(np.sum(y & ~p)), int(np.sum(~y & ~p))
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "precision": tp/(tp+fp) if tp+fp else None, "recall": tp/(tp+fn) if tp+fn else None,
        "IoU": tp/(tp+fp+fn) if tp+fp+fn else None,
        "false_positive_rate": fp/(fp+tn) if fp+tn else None, "predicted_positive_fraction": float(p.mean())}


def evaluate_motion_scores(labels, scores, *, semantics, probability_threshold=None, threshold_inclusive=True, continuous_speed=None):
    y, score = np.asarray(labels, bool).ravel(), np.asarray(scores, np.float64).ravel()
    if y.shape != score.shape or not len(y) or not np.isfinite(score).all():
        raise ValueError("Keep explicit matching finite score/GT support; do not silently drop failed predictions")
    if semantics not in ("uncalibrated_uncertainty", "dynamic_sigmoid"):
        raise ValueError("Declare score semantics; do not silently treat uncertainty as probability")
    positives, negatives = int(y.sum()), int((~y).sum())
    result = {"samples": len(y), "GT_positive_samples": positives, "GT_negative_samples": negatives,
        "GT_prevalence": float(y.mean()), "semantics": semantics, "higher_score_means": "less trusted/more dynamic, fixed from source before GT scores",
        "AUROC": None, "average_precision": None, "PR_AUC_trapezoidal": None,
        "ranking_unavailable_reason": "SINGLE_CLASS_GROUND_TRUTH" if not positives or not negatives else None}
    curves = {}
    if positives and negatives:
        order = np.argsort(-score, kind="stable")
        sorted_score, sorted_y = score[order], y[order]
        endpoints = np.flatnonzero(np.r_[sorted_score[1:] != sorted_score[:-1], True])
        tp = np.cumsum(sorted_y)[endpoints]
        fp = endpoints+1-tp
        precision, recall = tp/(tp+fp), tp/positives
        fpr, tpr = np.r_[0., fp/negatives], np.r_[0., recall]
        result.update(AUROC=float(np.trapezoid(tpr, fpr)), average_precision=float(np.sum(np.diff(np.r_[0., recall])*precision)),
            PR_AUC_trapezoidal=float(np.trapezoid(np.r_[1., precision], np.r_[0., recall])))
        curves = {"threshold": sorted_score[endpoints], "precision": precision, "recall": recall, "false_positive_rate": fpr, "true_positive_rate": tpr}
    if semantics == "dynamic_sigmoid":
        if (score < 0).any() or (score > 1).any() or probability_threshold is None:
            raise ValueError("Native sigmoid range and its declared native threshold are required")
        threshold = float(probability_threshold)
        bins = np.minimum((score*10).astype(int), 9)
        edges = np.linspace(0, 1, 11)
        result["Brier_score"] = float(np.mean((score-y)**2))
        result["operating_point"] = "Native predeclared sigmoid threshold"
    else:
        threshold = float(np.quantile(score, .8))
        edges = np.unique(np.quantile(score, np.linspace(0, 1, 11)))
        bins = np.searchsorted(edges[1:-1], score, side="right") if len(edges) > 1 else np.zeros(len(score), int)
        result["Brier_score"] = None
        result["operating_point"] = "Fixed 80th-percentile uncertainty threshold, ties included; actual coverage reported"
    result["threshold"] = threshold
    inclusive = threshold_inclusive if semantics == "dynamic_sigmoid" else True
    result["threshold_comparison"] = ">=" if inclusive else ">"
    result.update(binary_statistics(y, score >= threshold if inclusive else score > threshold))
    reliability, weighted_gap = [], 0.
    for index in range(10 if semantics == "dynamic_sigmoid" else max(1, len(edges)-1)):
        mask = bins == index
        count = int(mask.sum())
        mean_score, rate = (float(score[mask].mean()), float(y[mask].mean())) if count else (None, None)
        reliability.append({"bin": index, "samples": count, "score_lower": float(edges[index]),
            "score_upper": float(edges[min(index+1, len(edges)-1)]), "mean_score": mean_score, "empirical_dynamic_frequency": rate})
        if count and semantics == "dynamic_sigmoid":
            weighted_gap += count/len(y)*abs(mean_score-rate)
    result["probability_ECE_10_fixed_bins"] = float(weighted_gap) if semantics == "dynamic_sigmoid" else None
    result["reliability_semantics"] = "Empirical probability calibration" if semantics == "dynamic_sigmoid" else "Ranking reliability only; raw uncertainty is not a probability"
    result["reliability_bins"] = reliability
    result["continuous_speed_Spearman_rho"] = None
    if continuous_speed is not None:
        speed = np.asarray(continuous_speed, np.float64).ravel()
        if speed.shape != score.shape or not np.isfinite(speed).all():
            raise ValueError("Continuous GT speed must match the exact reported support")
        if np.ptp(score) > 0 and np.ptp(speed) > 0:
            result["continuous_speed_Spearman_rho"] = float(np.corrcoef(rankdata(score), rankdata(speed))[0, 1])
    return result, curves

