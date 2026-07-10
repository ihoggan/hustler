---
name: Bug Report
about: Report a bug or crash
title: "[BUG] "
labels: bug
assignees: ''

---

## Description

[Clear description of the bug. What were you doing when it happened?]

## Reproduction

**Steps to reproduce:**
1. Run: `python3 hustler.py [command]`
2. [Action] (e.g., "Strike the cue ball at angle 45°")
3. [Expected outcome]
4. [Actual outcome]

**Example:**
```bash
python3 hustler.py
# Click on cue ball, drag to aim
# Press SPACE to strike
# Expected: ball moves forward
# Actual: ball moves sideways, then crashes
```

## Validation Status

- [ ] Reproducible: [Yes / No / Sometimes]
- [ ] Affects: `--selftest` / interactive / `--batch` / `--smoke` / other
- [ ] Regression: [Known to work in R6.2 / new issue]

## Environment

- **OS:** [Linux / macOS / Windows]
- **Python:** [version from `python3 --version`]
- **Key packages:** pygame 2.6.1, pymunk 7.3.0, moderngl [if applicable]

## Logs / Output

```
[Paste error message or crash log here]
```

## Notes

[Any additional context: recent changes, system specs, related issues]

---

**Triage checklist (maintainer):**
- [ ] Can reproduce?
- [ ] Validation chain status (selftest 27/27 pass?)
- [ ] Physics or rules issue?
- [ ] Graphics or interaction issue?
- [ ] Assign to release milestone
