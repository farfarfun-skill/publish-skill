#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT

ORG="farfarfun-skill"
WORKSPACES_DIR=""
REGISTER=0
MIRROR_TO=""

readonly MIN_DESCRIPTION_LEN=20
readonly MAX_DESCRIPTION_LEN=1024
readonly MIN_BODY_LEN=50

usage() {
  cat >&2 <<EOF
Usage: ${0##*/} [--org ORG] [--workspaces-dir DIR] [--register] [--mirror-to ORG]

Validate every skills/<slug>/SKILL.md across all public repos in --org,
clone any repo missing locally, and print the "npx skills add" install
manifest that skills.sh uses for discovery.

  --org ORG              GitHub org to publish (default: farfarfun-skill)
  --workspaces-dir DIR   parent directory for repo checkouts (default: the
                         parent directory of this repo's own checkout)
  --register             also run "npx skills add" locally for each valid
                         skill (contributes to skills.sh install telemetry)
  --mirror-to ORG        also fork/sync each passing repo into ORG
  -h, --help             show this help
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 2
}

skill_field() {
  local file="$1" field="$2"
  sed -n "/^---\$/,/^---\$/{/^${field}:/{s/^${field}: *//;p}}" "$file" | head -n1
}

skill_body_len() {
  local file="$1"
  awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$file" | tr -d '[:space:]' | wc -c
}

# Validates a single workspace's skills/*/SKILL.md files.
# Returns: 0 = at least one skill validated with no blocking issues
#          1 = at least one skill has a blocking issue
#          2 = not a skill repo (no skills/ dir, or no SKILL.md files)
validate_repo() {
  local workspace="$1"
  local skills_dir="$workspace/skills"
  local rc=0 found=0
  local dir slug name description body_len

  if [[ ! -d "$skills_dir" ]]; then
    echo "  skipped: no skills/ directory"
    return 2
  fi

  for dir in "$skills_dir"/*/; do
    [[ -f "${dir}SKILL.md" ]] || continue
    found=1
    slug="$(basename "$dir")"
    local skill_md="${dir}SKILL.md"

    if [[ "$(sed -n '1p' "$skill_md")" != "---" ]]; then
      echo "  BLOCK: $slug/SKILL.md - missing opening frontmatter delimiter (---)"
      rc=1
      continue
    fi

    name="$(skill_field "$skill_md" name)"
    description="$(skill_field "$skill_md" description)"
    body_len="$(skill_body_len "$skill_md")"

    if [[ -z "$name" ]]; then
      echo "  BLOCK: $slug/SKILL.md - missing name"
      rc=1
    elif [[ ! "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
      echo "  BLOCK: $slug/SKILL.md - name '$name' must be lowercase kebab-case"
      rc=1
    elif [[ "$name" != "$slug" ]]; then
      echo "  WARN: $slug/SKILL.md - name '$name' does not match directory '$slug'"
    fi

    if [[ -z "$description" ]]; then
      echo "  BLOCK: $slug/SKILL.md - missing description"
      rc=1
    elif (( ${#description} < MIN_DESCRIPTION_LEN )); then
      echo "  WARN: $slug/SKILL.md - description too short (${#description} chars)"
    elif (( ${#description} > MAX_DESCRIPTION_LEN )); then
      echo "  BLOCK: $slug/SKILL.md - description too long (${#description} chars, max $MAX_DESCRIPTION_LEN)"
      rc=1
    fi

    if (( body_len < MIN_BODY_LEN )); then
      echo "  WARN: $slug/SKILL.md - body too short ($body_len chars, min $MIN_BODY_LEN)"
    fi
  done

  if (( found == 0 )); then
    echo "  skipped: skills/ has no SKILL.md files"
    return 2
  fi

  return "$rc"
}

resolve_repo_slug() {
  local workspace="$1" url
  url="$(git -C "$workspace" remote get-url origin 2>/dev/null)" || return 1
  echo "$url" | sed -E 's#^.*github\.com[:/]##; s#\.git$##'
}

manifest_repo() {
  local workspace="$1" slug dir name
  slug="$(resolve_repo_slug "$workspace")" || slug=""
  [[ -n "$slug" ]] || { echo "  manifest skipped: no origin remote"; return 0; }

  for dir in "$workspace"/skills/*/; do
    [[ -f "${dir}SKILL.md" ]] || continue
    name="$(skill_field "${dir}SKILL.md" name)"
    name="${name:-$(basename "$dir")}"
    echo "  npx skills add $slug --skill $name"
  done
}

register_repo_skills() {
  local workspace="$1" slug dir name
  slug="$(resolve_repo_slug "$workspace")" || { echo "  register skipped: no origin remote"; return 0; }

  for dir in "$workspace"/skills/*/; do
    [[ -f "${dir}SKILL.md" ]] || continue
    name="$(skill_field "${dir}SKILL.md" name)"
    name="${name:-$(basename "$dir")}"
    if npx --yes skills add "$slug" --skill "$name" -y >/dev/null 2>&1; then
      echo "  register: $name ok"
    else
      echo "  register: $name FAILED"
    fi
  done
}

mirror_repo() {
  local workspace="$1" target_org="$2"
  local slug owner repo name target_slug
  slug="$(resolve_repo_slug "$workspace")" || { echo "  mirror skipped: no origin remote"; return 0; }
  owner="${slug%%/*}"
  repo="${slug##*/}"
  name="${owner}--${repo}"
  target_slug="${target_org}/${name}"

  if gh api "repos/${target_slug}" >/dev/null 2>&1; then
    if gh repo sync "${target_slug}" --source "${slug}" >/dev/null 2>&1; then
      echo "  mirror: synced https://github.com/${target_slug}"
    else
      echo "  mirror: sync FAILED for https://github.com/${target_slug}"
    fi
  else
    if gh repo fork "${slug}" --org "${target_org}" --fork-name "${name}" --remote=false --clone=false >/dev/null 2>&1; then
      echo "  mirror: forked https://github.com/${target_slug}"
    else
      echo "  mirror: fork FAILED for ${slug}"
    fi
  fi
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --org)
        [[ $# -ge 2 ]] || die "--org requires a value"
        ORG="$2"; shift 2 ;;
      --workspaces-dir)
        [[ $# -ge 2 ]] || die "--workspaces-dir requires a value"
        WORKSPACES_DIR="$2"; shift 2 ;;
      --register)
        REGISTER=1; shift ;;
      --mirror-to)
        [[ $# -ge 2 ]] || die "--mirror-to requires a value"
        MIRROR_TO="$2"; shift 2 ;;
      -h|--help)
        usage; exit 0 ;;
      *)
        usage; die "unknown argument: $1" ;;
    esac
  done

  [[ -n "$WORKSPACES_DIR" ]] || WORKSPACES_DIR="$(dirname "$ROOT")"

  command -v git >/dev/null 2>&1 || die "git is required"
  command -v gh >/dev/null 2>&1 || die "gh (GitHub CLI) is required"

  mkdir -p "$WORKSPACES_DIR"

  local repos
  repos="$(gh repo list "$ORG" --visibility public --source --no-archived --json name -q '.[].name')"
  [[ -n "$repos" ]] || die "no public repos found in org: $ORG"

  echo "org: $ORG"
  echo "workspaces-dir: $WORKSPACES_DIR"
  echo

  local repo ws rc overall_rc=0 published=0

  while IFS= read -r repo; do
    [[ -n "$repo" ]] || continue
    ws="${WORKSPACES_DIR}/${repo}"
    echo "== ${repo} =="

    if [[ ! -d "$ws" ]]; then
      if ! git clone --quiet "https://github.com/${ORG}/${repo}.git" "$ws"; then
        echo "  error: git clone failed"
        overall_rc=1
        echo
        continue
      fi
    fi

    rc=0
    validate_repo "$ws" || rc=$?

    case "$rc" in
      0)
        manifest_repo "$ws"
        published=$((published + 1))
        (( REGISTER )) && register_repo_skills "$ws"
        [[ -n "$MIRROR_TO" ]] && mirror_repo "$ws" "$MIRROR_TO"
        ;;
      2)
        : ;;
      *)
        overall_rc=1 ;;
    esac
    echo
  done <<< "$repos"

  echo "done: ${published} repo(s) published to the manifest above"
  return "$overall_rc"
}

main "$@"
