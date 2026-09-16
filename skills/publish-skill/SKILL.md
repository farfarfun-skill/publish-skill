---
name: publish-skill
description: Validate skills/<slug>/SKILL.md frontmatter and body across a skill repository, generate the npx skills add install manifest for skills.sh discovery, and mirror/sync a public skill repo into another GitHub org (e.g. a marketplace or aggregator). Use when Codex needs to check a skill is ready to publish, produce install commands for skills.sh, or fork/sync a skill repo to a secondary platform. Use github-repo-standards instead for README structure and repository Topics/description.
---

# Publish Skill

skills.sh has no submission queue — it discovers skills by crawling public GitHub repositories for well-formed `skills/<slug>/SKILL.md` files. "Publishing" therefore means: the repository is public, every `SKILL.md` has valid frontmatter, and (optionally) the skill is also mirrored into a secondary marketplace/org that indexes repositories directly.

## Validate

Run from this skill directory:

```bash
python3 scripts/skill_publisher.py validate --workspace /path/to/repo --fail-on block
```

Checks every `skills/<slug>/SKILL.md`: frontmatter starts and ends with `---`, `name` is present and lowercase kebab-case, `name` matches its directory, `description` is present and between 20 and 1024 characters, and the body after the frontmatter has actual instructions (not just a stub).

Use `--fail-on revise` for a stricter gate, `--format json` for machine consumption.

## Generate The Install Manifest

```bash
python3 scripts/skill_publisher.py manifest --workspace /path/to/repo
```

Resolves the repo's GitHub slug from `git remote origin` and prints one `npx skills add <owner>/<repo> --skill <name>` line per valid skill. This is what to hand out (or paste into a README/announcement) as the "install from skills.sh" instructions — there is no separate submission step.

`all` runs `validate` then `manifest` in one call and shares the same `--fail-on` gate.

## Publish An Entire Org In One Command

```bash
python3 scripts/skill_publisher.py org --org farfarfun-skill --workspaces-dir /path/to/farfarfun-skill
```

This is the one-shot "publish everything" entrypoint. It lists every public, non-fork repo in `--org` via `gh repo list`, clones any that aren't already checked out under `--workspaces-dir` (never pulls or mutates an existing clone), skips repos with no `skills/` directory, runs `validate` on the rest, and prints the combined install manifest across the whole org. `--workspaces-dir` defaults to the parent directory of `--workspace`, so running it from inside a repo that sits next to its siblings on disk needs no extra flags.

Add `--register` to also run `npx skills add <owner>/<repo> --skill <name> -y` locally for every skill that passed validation — this is the actual mechanism that feeds skills.sh's install telemetry/leaderboard (there is no submission API) and it also installs the skill into this machine's agent skill directories, so only pass it when that side effect is wanted.

Add `--mirror-to <org>` to additionally fork/sync every passing repo into a secondary org (see below).

## Mirror To Another Platform

```bash
python3 scripts/skill_publisher.py mirror --workspace /path/to/repo --target-org farfarfun-skills
```

Forks the repo into `--target-org` (default `farfarfun-skills`) as `<owner>--<repo>` on first run, and re-syncs that fork from the source on every later run — matching how this org already mirrors `farfarfun-skill/*` repositories for secondary discovery. Requires `gh` authenticated with permission to create repos in the target org. This is the only subcommand that changes remote GitHub state; run `validate` first and only mirror a repo that passed.

## Return Results

Return `allow`, `revise`, or `block` from `validate`, the passed checks, and concrete repair paths for any finding (which file, which field, what to change). `manifest` and `mirror` are informational/action outputs, not gates — do not block on them.
