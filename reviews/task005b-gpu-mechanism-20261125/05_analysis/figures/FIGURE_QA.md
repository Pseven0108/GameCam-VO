# Diagnostic figure QA

These are report diagnostics, not a journal submission. Three figures export to PNG, editable-text SVG and TrueType PDF from the same Python backend. All three PNGs were visually inspected; the first pass found a title/legend overlap, corrected by reserving a bottom figure legend before the final exports.

All panels trace to the three CSVs named in FIGURE_CONTRACT.md. S0 panels explicitly say NOT RUN. D0_S1_RGB233 is marked stopped and RGB401 not replayed. The two RGB019 origin labels represent the same common starting state; they are not independent replication. No p-values, confidence intervals or error bars are claimed.

Axes use log/symlog where labeled. Plot ranges are fitted independently per panel; compare labeled values rather than apparent line angles across panels. Lines connect the three observed contexts as a visual guide, not interpolated measurements. No missing data are replaced with zeros. The C diagnostic cross-cell can produce very large updates; it is not a deployed baseline or an accuracy result.

The U comparison is joint U/temp/affine feedback. No images, crops, brightness adjustments or generated data are used. Full numeric arrays are preserved as separate immutable Release assets; the failed context is excluded from complete-context aggregate curves and supplied separately.
