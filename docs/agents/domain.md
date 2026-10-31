# Domain Docs

Read the glossary and relevant architecture decision records (ADRs) before exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root defines the repo's terms.
- **`docs/adr/`** holds decisions. Read those that touch the area you're working in.

If these files are missing, proceed silently. Create them with `/domain-modeling`
when terms or decisions get resolved, rather than suggesting empty docs upfront.

## File structure

This repo uses a single-context layout:

```
/
├── GLOSSARY.md
└── docs/adr/
    └── 0001-<decision>.md
```

## Use the glossary's vocabulary

Use the terms defined in `GLOSSARY.md` in issue titles, proposals, hypotheses,
and test names. Avoid synonyms the glossary rules out.

If a term is missing, check whether the project already has a name for it.
Note any real gap for `/domain-modeling`.

## Flag ADR conflicts

If a proposal contradicts an ADR, say which decision it changes and why:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
