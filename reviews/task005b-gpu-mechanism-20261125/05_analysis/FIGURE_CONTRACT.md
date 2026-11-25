# TASK005B partial-results diagnostic figures

Conclusion: four complete contexts provide local solver-path diagnostics, while the stopped context and unexecuted S0 contexts prevent the planned full mechanism comparison.

Backend: existing Python/matplotlib workflow, using already available local CPU plotting dependencies. No packages are installed and no GPU libraries are imported.

Archetype: quantitative diagnostic grids, with no independent-replicate or accuracy claim.

1. Translation steps: A/B/C/D solver update norms in the two internal iterations; missing panels explicitly identify unexecuted or stopped contexts. RGB019 origins are the same initial state, not independent replicates.
2. Common-weight reprojection: paired A/D geometric loss after the full two-iteration call, with normalization explicitly labeled. Residual decrease is not trajectory or GT accuracy.
3. U feedback: vector difference after the second iteration, normalized by the frozen-mode update. This includes joint U/temp/affine feedback and is not a pure isolated U effect.

Source: NATIVE_ITERATION_METRICS.csv, CONTEXT_MECHANISM_SUMMARY.csv and U_FEEDBACK_CONTRASTS.csv. The failed partial context is kept in separate raw assets and diagnostic tables, not silently merged into complete-context summaries.

Export: PNG for direct review; PDF/SVG with editable text for reuse. No error bars, inferential statistics, smoothing, interpolation of missing contexts, or fabricated data. Review legibility and the explicit NOT RUN labels before packaging.
