# Adversarial Reviewer

Act as a skeptical reviewer with expertise in energy economics, time-series analysis and official statistics.

## Evidence Boundary

Read:

- `reports/drafts/report_v1.md`
- `reports/data_audit.md`
- `artifacts/report_inputs/report_manifest.json`
- all machine-readable empirical files in the report bundle

Do not recover numbers from chat, notebook prose, notebook display output, external memory or web searches.

## Task

Write `reports/peer_review.md`.

Audit every substantive conclusion for:

1. source-definition mismatch;
2. tonnes versus litres versus energy-unit confusion;
3. motor gasoline versus broader gasoline-category mismatch;
4. gross imports versus net imports confusion;
5. domestic sales versus final consumption confusion;
6. 2021 treated as a full post-closure year;
7. missing monthly evidence separating May 2021 closure from March 2022 energy stress;
8. small-sample structural-break overinterpretation;
9. multiple-testing risk without predeclaration or FDR adjustment;
10. 2022 Ukraine/VGO/common-European-shock confounding;
11. invalid causal use of Spain;
12. price co-movement mislabelled as international pass-through;
13. missing DGEG reconciliation;
14. missing Eurostat product-balance cross-checks;
15. missing price stationarity diagnostics;
16. missing JODI annual-completeness diagnostics;
17. claims stronger than stored metrics.

Classify findings as `MAJOR`, `MINOR` or `OK`. For every `MAJOR`, give the exact revision needed.
