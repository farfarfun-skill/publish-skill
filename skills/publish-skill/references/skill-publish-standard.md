# Skill Publish Standard

## SKILL.md Frontmatter

- File starts with `---`, a block of `key: value` lines, and a closing `---`.
- `name` is required, lowercase kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), and matches the containing directory name — installers and skills.sh discover a skill by its folder, a mismatch makes the skill unfindable by the name users expect.
- `description` is required, 20–1024 characters. Below 20 it cannot explain what the skill does or when to use it; above 1024 some loaders truncate or reject it. Write it as: what the skill does, then when to use it, then what to use instead for adjacent concerns.
- The body after the closing `---` must contain real procedural instructions, not a stub — treat anything under ~50 characters as unfinished.

## Publishing Model

skills.sh and comparable installers (`npx skills add <owner>/<repo>`) crawl public GitHub repositories for `skills/<slug>/SKILL.md`; there is no submission form or review queue. A skill is "published" once:

1. The repository is public.
2. Every `SKILL.md` in `skills/` passes the frontmatter/body checks above.
3. The repository's own discoverability metadata (README, GitHub description, Topics) is in order — see `github-repo-standards` in a sibling repository for that check.

## Secondary Mirrors

Some marketplaces or aggregator orgs index repositories they hold directly rather than crawling arbitrary GitHub. For those, mirror the source repo into the target org as a fork named `<owner>--<repo>`, and re-sync it after every release. Only do this for a repo that already passed validation — a mirror should never be ahead of its source in correctness.

## Out Of Scope

README structure, repository description, and Topics are governed by `github-repo-standards`. Internal file placement is governed by `project-structure-governance`. This standard only covers `SKILL.md` itself and the act of making it installable.
