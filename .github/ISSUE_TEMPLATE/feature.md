---
name: Feature
about: Propose a feature or design decision
title: "[FEATURE] "
labels: feature, design
assignees: ''

---

## Decision Brief

**Problem:** [What are we trying to solve?]

**Approach:** [How do we solve it? Any forks or alternatives?]

**Scope:** [What's included? What's explicitly excluded?]

## Acceptance Criteria

- [ ] Passes full validation chain: `py_compile` → `--selftest` → `--batch 30` → `--smoke`
- [ ] One new selftest assertion added (describe what it tests)
- [ ] UK spelling throughout
- [ ] Code documented (docstrings, physics sources cited)
- [ ] (If graphics) Pixel-probe assertions for render correctness
- [ ] (If AI) Emergent behaviour validated via `--aigame` (no decision scripts)

## Validation Plan

```bash
python3 hustler.py --selftest      # Should show 28/28 (or higher)
python3 hustler.py --batch 30      # Containment check
python3 hustler.py --smoke         # Interactive loop validation
python3 hustler.py --smoke-gl      # (If graphics changes)
python3 hustler.py --snap /tmp/new.png  # (If render changes)
```

## Related Issues

[Link to blocked issues, supersedes, etc.]

## Notes

[Additional context: design rationale, similar work, reference implementations]
