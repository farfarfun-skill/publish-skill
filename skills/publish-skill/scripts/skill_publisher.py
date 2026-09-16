#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s?(.*)$")
MIN_DESCRIPTION_LENGTH = 20
MAX_DESCRIPTION_LENGTH = 1024
MIN_BODY_LENGTH = 50


def finding(severity: str, code: str, path: str, message: str) -> dict:
    return {"severity": severity, "code": code, "path": path, "message": message}


def discover_skills(workspace: Path) -> list[Path]:
    skills_dir = workspace / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md"))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, str | None]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "SKILL.md 必须以 `---` 开头的 YAML frontmatter 开头。"
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text, "frontmatter 缺少结束的 `---`。"

    fields: dict[str, str] = {}
    last_key: str | None = None
    for line in lines[1:end]:
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            last_key = match.group(1)
            fields[last_key] = match.group(2).strip()
        elif last_key and line.strip():
            fields[last_key] = f"{fields[last_key]} {line.strip()}".strip()

    body = "\n".join(lines[end + 1:])
    return fields, body, None


def check_skill(skill_dir: Path, workspace: Path, findings: list[dict], passes: list[str]) -> None:
    relative = skill_dir.relative_to(workspace).as_posix()
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8", errors="replace")

    fields, body, error = parse_frontmatter(text)
    if error:
        findings.append(finding("block", "skill.frontmatter_invalid", f"{relative}/SKILL.md", error))
        return

    name = fields.get("name", "").strip()
    if not name:
        findings.append(finding("block", "skill.name_missing", f"{relative}/SKILL.md", "frontmatter 缺少 name 字段。"))
    elif not NAME_RE.match(name):
        findings.append(finding(
            "block", "skill.name_invalid", f"{relative}/SKILL.md",
            f"name {name!r} 必须是小写 kebab-case（如 my-skill-name）。",
        ))
    elif name != skill_dir.name:
        findings.append(finding(
            "revise", "skill.name_mismatch", f"{relative}/SKILL.md",
            f"name {name!r} 与目录名 {skill_dir.name!r} 不一致，skills.sh 按目录发现 skill。",
        ))
    else:
        passes.append(f"name 与目录一致：{relative}")

    description = fields.get("description", "").strip()
    if not description:
        findings.append(finding("block", "skill.description_missing", f"{relative}/SKILL.md", "frontmatter 缺少 description 字段。"))
    elif len(description) < MIN_DESCRIPTION_LENGTH:
        findings.append(finding(
            "revise", "skill.description_too_short", f"{relative}/SKILL.md",
            f"description 只有 {len(description)} 字符，建议说明这个 skill 做什么、何时使用。",
        ))
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        findings.append(finding(
            "block", "skill.description_too_long", f"{relative}/SKILL.md",
            f"description 有 {len(description)} 字符，超过 {MAX_DESCRIPTION_LENGTH} 上限，可能被加载器截断或拒绝。",
        ))
    else:
        passes.append(f"description 长度合规（{len(description)} 字符）：{relative}")

    if len(body.strip()) < MIN_BODY_LENGTH:
        findings.append(finding(
            "revise", "skill.body_too_short", f"{relative}/SKILL.md",
            "frontmatter 之后的正文过短，缺少可执行的具体指令。",
        ))


def analyze_validate(workspace: Path) -> dict:
    findings: list[dict] = []
    passes: list[str] = []
    skills = discover_skills(workspace)
    if not skills:
        findings.append(finding("block", "skills.none_found", "skills/", "workspace 下没有 skills/<slug>/SKILL.md，没有可发布的 skill。"))
    for skill_dir in skills:
        check_skill(skill_dir, workspace, findings, passes)

    decision = "allow"
    if any(item["severity"] == "block" for item in findings):
        decision = "block"
    elif findings:
        decision = "revise"
    return {"decision": decision, "passes": passes, "findings": findings}


def resolve_repo_slug(workspace: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(workspace), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def build_manifest(workspace: Path) -> dict:
    slug = resolve_repo_slug(workspace)
    entries = []
    for skill_dir in discover_skills(workspace):
        fields, _, error = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        if error:
            continue
        name = fields.get("name", skill_dir.name)
        entry = {"skill": name, "path": skill_dir.relative_to(workspace).as_posix()}
        if slug:
            entry["repo"] = slug
            entry["install"] = f"npx skills add {slug} --skill {name}"
        entries.append(entry)
    return {"repo": slug, "skills": entries}


def repo_exists(slug: str) -> bool:
    result = subprocess.run(["gh", "api", f"repos/{slug}"], capture_output=True, text=True, timeout=15, check=False)
    return result.returncode == 0


def run_gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60, check=False)


def mirror(workspace: Path, target_org: str, fork_name: str | None) -> dict:
    slug = resolve_repo_slug(workspace)
    if slug is None:
        return {"ok": False, "error": "无法从 git remote origin 解析出 GitHub owner/repo。"}

    owner, _, repo = slug.partition("/")
    name = fork_name or f"{owner}--{repo}"
    target_slug = f"{target_org}/{name}"

    if repo_exists(target_slug):
        result = run_gh(["repo", "sync", target_slug, "--source", slug])
        action = "synced"
    else:
        result = run_gh([
            "repo", "fork", slug,
            "--org", target_org,
            "--fork-name", name,
            "--remote=false",
            "--clone=false",
        ])
        action = "forked"

    if result.returncode != 0:
        return {"ok": False, "action": action, "target": target_slug, "error": result.stderr.strip() or result.stdout.strip()}
    return {"ok": True, "action": action, "target": target_slug, "url": f"https://github.com/{target_slug}"}


def list_org_repos(org: str) -> list[str]:
    result = run_gh([
        "repo", "list", org,
        "--visibility", "public",
        "--source",
        "--no-archived",
        "--json", "name",
        "--limit", "200",
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh repo list failed")
    return sorted(item["name"] for item in json.loads(result.stdout))


def ensure_clone(org: str, repo: str, workspaces_dir: Path) -> Path:
    target = workspaces_dir / repo
    if not target.exists():
        subprocess.run(
            ["git", "clone", f"https://github.com/{org}/{repo}.git", str(target)],
            check=True, timeout=120,
        )
    return target


def register_skill(slug: str, name: str) -> dict:
    result = subprocess.run(
        ["npx", "--yes", "skills", "add", slug, "--skill", name, "-y"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    return {
        "skill": name,
        "ok": result.returncode == 0,
        "error": None if result.returncode == 0 else (result.stderr.strip() or result.stdout.strip()),
    }


def publish_org(org: str, workspaces_dir: Path, register: bool, mirror_to: str | None) -> dict:
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    repos = list_org_repos(org)
    repo_reports = []
    all_skills: list[dict] = []

    for repo in repos:
        entry: dict = {"repo": repo}
        try:
            workspace = ensure_clone(org, repo, workspaces_dir)
        except subprocess.CalledProcessError as error:
            entry["status"] = "error"
            entry["error"] = f"git clone 失败：{error}"
            repo_reports.append(entry)
            continue

        if not (workspace / "skills").is_dir():
            entry["status"] = "skipped"
            entry["reason"] = "没有 skills/ 目录，不是一个 skill 仓库"
            repo_reports.append(entry)
            continue

        report = analyze_validate(workspace)
        entry["status"] = report["decision"]
        entry["findings"] = report["findings"]

        if report["decision"] != "block":
            manifest = build_manifest(workspace)
            entry["skills"] = manifest["skills"]
            all_skills.extend(manifest["skills"])

            if register:
                entry["register_results"] = [
                    register_skill(skill["repo"], skill["skill"])
                    for skill in manifest["skills"]
                    if skill.get("repo")
                ]

            if mirror_to:
                entry["mirror"] = mirror(workspace, mirror_to, None)

        repo_reports.append(entry)

    return {"org": org, "repos": repo_reports, "skills": all_skills}


def render_org_text(result: dict) -> str:
    lines = [f"org: {result['org']}", f"total publishable skills: {len(result['skills'])}", ""]
    for entry in result["repos"]:
        status = entry.get("status", "unknown")
        lines.append(f"[{status}] {entry['repo']}")
        if status == "skipped":
            lines.append(f"    {entry['reason']}")
        elif status == "error":
            lines.append(f"    {entry['error']}")
        else:
            for item in entry.get("findings", []):
                lines.append(f"    {item['severity'].upper()}: {item['path']} - {item['message']}")
            for skill in entry.get("skills", []):
                lines.append(f"    - {skill.get('install', skill['skill'])}")
            for reg in entry.get("register_results", []):
                mark = "ok" if reg["ok"] else f"FAILED: {reg['error']}"
                lines.append(f"    register {reg['skill']}: {mark}")
            if "mirror" in entry:
                m = entry["mirror"]
                mark = m.get("url", m.get("error")) if m.get("ok") else f"FAILED: {m.get('error')}"
                lines.append(f"    mirror: {mark}")
    return "\n".join(lines)


def render_report_text(report: dict) -> str:
    lines = [f"decision: {report['decision']}"]
    lines.extend(f"PASS: {item}" for item in report["passes"])
    for item in report["findings"]:
        lines.append(f"{item['severity'].upper()}: {item['path']} - {item['message']}")
    return "\n".join(lines)


def render_manifest_text(manifest: dict) -> str:
    if not manifest["repo"]:
        lines = ["repo: (unresolved — check git remote origin)"]
    else:
        lines = [f"repo: {manifest['repo']}"]
    for entry in manifest["skills"]:
        lines.append(f"  - {entry.get('install', entry['skill'])}")
    return "\n".join(lines)


def cmd_validate(args: argparse.Namespace) -> int:
    report = analyze_validate(Path(args.workspace).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else render_report_text(report))
    if args.fail_on == "revise" and report["decision"] in {"revise", "block"}:
        return 1
    if args.fail_on == "block" and report["decision"] == "block":
        return 1
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    manifest = build_manifest(Path(args.workspace).resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2) if args.format == "json" else render_manifest_text(manifest))
    return 0 if manifest["skills"] else 1


def cmd_mirror(args: argparse.Namespace) -> int:
    result = mirror(Path(args.workspace).resolve(), args.target_org, args.fork_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_org(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    workspaces_dir = Path(args.workspaces_dir).resolve() if args.workspaces_dir else workspace.parent
    result = publish_org(args.org, workspaces_dir, args.register, args.mirror_to)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json" else render_org_text(result))
    return 0 if all(entry.get("status") != "block" and entry.get("status") != "error" for entry in result["repos"]) else 1


def cmd_all(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    report = analyze_validate(workspace)
    manifest = build_manifest(workspace)
    combined = {"validate": report, "manifest": manifest}
    print(json.dumps(combined, ensure_ascii=False, indent=2) if args.format == "json" else
          render_report_text(report) + "\n\n" + render_manifest_text(manifest))
    if args.fail_on == "revise" and report["decision"] in {"revise", "block"}:
        return 1
    if args.fail_on == "block" and report["decision"] == "block":
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并发布 skills/<slug>/SKILL.md 到 skills.sh 或镜像组织。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", default=".", help="包含 skills/ 目录的仓库根目录")
    common.add_argument("--format", choices=("text", "json"), default="text")

    validate_parser = subparsers.add_parser("validate", parents=[common], help="校验所有 SKILL.md 的 frontmatter 和正文")
    validate_parser.add_argument("--fail-on", choices=("revise", "block"))
    validate_parser.set_defaults(func=cmd_validate)

    manifest_parser = subparsers.add_parser("manifest", parents=[common], help="生成 npx skills add 安装清单，用于 skills.sh 发现")
    manifest_parser.set_defaults(func=cmd_manifest)

    mirror_parser = subparsers.add_parser("mirror", parents=[common], help="将仓库 fork/同步到另一个 GitHub 组织（例如 farfarfun-skills）")
    mirror_parser.add_argument("--target-org", default="farfarfun-skills", help="镜像目标组织")
    mirror_parser.add_argument("--fork-name", default=None, help="镜像仓库名，默认 <owner>--<repo>")
    mirror_parser.set_defaults(func=cmd_mirror)

    all_parser = subparsers.add_parser("all", parents=[common], help="依次运行 validate 与 manifest（不含 mirror）")
    all_parser.add_argument("--fail-on", choices=("revise", "block"))
    all_parser.set_defaults(func=cmd_all)

    org_parser = subparsers.add_parser(
        "org", parents=[common],
        help="发现并发布整个 GitHub 组织下的所有 skill 仓库（一键发布入口）",
    )
    org_parser.add_argument("--org", default="farfarfun-skill", help="要发布的 GitHub 组织")
    org_parser.add_argument(
        "--workspaces-dir", default=None,
        help="本地仓库的父目录；已存在的仓库直接使用（不会 pull），缺失的会被克隆到这里。默认是 --workspace 的上一级目录",
    )
    org_parser.add_argument(
        "--register", action="store_true",
        help="额外为每个通过校验的 skill 本地执行 `npx skills add`，为 skills.sh 的安装遥测/排行榜贡献数据，并把 skill 安装进本机 agent 目录",
    )
    org_parser.add_argument(
        "--mirror-to", default=None,
        help="额外把每个通过校验的仓库 fork/同步到这个组织（例如 farfarfun-skills）",
    )
    org_parser.set_defaults(func=cmd_org)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
