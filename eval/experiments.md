# Experiment log — local eval scores (scripts/local_eval.py)

Local scores are a proxy: glm-5p1 + deepseek-v4-pro cross-judged against
verified minimax-m3 reference reports (eval/reference_reports.json) over the
15 public bucket clips. Calibration anchor: the old pipeline scores
**0.796–0.800 locally ↔ 0.81 on the leaderboard** (2026-07-12).
Single-run noise from Stage-1 vision variance: ±0.01–0.03 — never trust a
single run to rank two variants; run twice and average.

| variant | what changed | run scores | mean |
|---|---|---|---|
| baseline (old pipeline) | pre-2026-07-12 code: emoji palettes, forced openings, 12-30w captions | 0.8004 / 0.7960 | 0.798 |
| v2 | P1 fact-density (formal 30-50w, ≥3 facts) + P2 personas/no-emoji + P3 validators + P4 verify pass + P5 judge fixes | 0.8660 | 0.866 |
| v3 | + fragile-facts rule, humorous_tech "compare TO tech not AS software" | 0.8331 | 0.833 |
| v4 | + group-gesture rule, Stage-1 temp 0.3→0.15 | 0.8619 / 0.8412 | 0.852 |
| v5 | + central-claim-must-be-main-subject rule, no timestamps in captions | 0.8371 / 0.8615 | 0.849 |

New-pipeline plateau across v2–v5 runs ≈ **0.85 local** → expected leaderboard ≈ 0.86–0.88.
v4 and v5 are statistically identical; v5 frozen (its rules also protect
against the real judge's re-watching disagreements). **FROZEN as image
`captionforge:v5-facts` (2026-07-12): container e2e = 12 clips in 68.9s,
exit 0, 0 timeouts, 0 style violations, all word ranges OK.**

Per-style picture (v5b): formal 0.94, humorous_tech 0.88, sarcastic 0.84, humorous_non_tech 0.80.
Remaining loss concentrates in humor-style ACCURACY — mostly cross-viewing
disagreement on which details are prominent. Note the local judges score
against a single reference viewing, so local accuracy is likely a LOWER
bound on what the official judge (own viewing, possibly more lenient) gives.

Next ideas if more points needed: multi-viewing merged references (better
ground truth for tuning); A/B FIREWORKS_JUDGE_MODEL=deepseek-v4-pro (needs
2+ runs per arm to beat noise); mine per-clip weak captions after each run.
