import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.skill_publisher import analyze_validate, build_manifest, publish_org

VALID_BODY = (
    "\n# Demo Skill\n\n"
    "This is the procedural body of the skill, long enough to pass the minimum body length check.\n"
)


def write_skill(workspace: Path, slug: str, name: str, description: str, body: str = VALID_BODY) -> Path:
    skill_dir = workspace / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nname: {name}\ndescription: {description}\n---\n{body}"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


VALID_DESCRIPTION = "Do the demo thing. Use when Codex needs to demonstrate a valid skill package."


class ValidateTests(unittest.TestCase):
    def test_no_skills_dir_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = analyze_validate(Path(temp_dir))
            self.assertEqual("block", report["decision"])
            self.assertTrue(any(item["code"] == "skills.none_found" for item in report["findings"]))

    def test_valid_skill_allows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", VALID_DESCRIPTION)
            report = analyze_validate(workspace)
            self.assertEqual("allow", report["decision"])
            self.assertEqual([], report["findings"])

    def test_name_mismatch_revises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "other-name", VALID_DESCRIPTION)
            report = analyze_validate(workspace)
            self.assertEqual("revise", report["decision"])
            self.assertTrue(any(item["code"] == "skill.name_mismatch" for item in report["findings"]))

    def test_invalid_name_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "Demo_Skill", "Demo_Skill", VALID_DESCRIPTION)
            report = analyze_validate(workspace)
            self.assertEqual("block", report["decision"])
            self.assertTrue(any(item["code"] == "skill.name_invalid" for item in report["findings"]))

    def test_missing_description_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", "")
            report = analyze_validate(workspace)
            self.assertEqual("block", report["decision"])
            self.assertTrue(any(item["code"] == "skill.description_missing" for item in report["findings"]))

    def test_short_description_revises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", "too short")
            report = analyze_validate(workspace)
            self.assertEqual("revise", report["decision"])
            self.assertTrue(any(item["code"] == "skill.description_too_short" for item in report["findings"]))

    def test_long_description_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", "x" * 1025)
            report = analyze_validate(workspace)
            self.assertEqual("block", report["decision"])
            self.assertTrue(any(item["code"] == "skill.description_too_long" for item in report["findings"]))

    def test_short_body_revises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", VALID_DESCRIPTION, body="\ntiny\n")
            report = analyze_validate(workspace)
            self.assertEqual("revise", report["decision"])
            self.assertTrue(any(item["code"] == "skill.body_too_short" for item in report["findings"]))

    def test_missing_frontmatter_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_dir = workspace / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# no frontmatter here\n", encoding="utf-8")
            report = analyze_validate(workspace)
            self.assertEqual("block", report["decision"])
            self.assertTrue(any(item["code"] == "skill.frontmatter_invalid" for item in report["findings"]))


class ManifestTests(unittest.TestCase):
    def test_manifest_includes_install_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", VALID_DESCRIPTION)
            with patch("scripts.skill_publisher.resolve_repo_slug", return_value="acme/demo-repo"):
                manifest = build_manifest(workspace)
            self.assertEqual("acme/demo-repo", manifest["repo"])
            self.assertEqual(1, len(manifest["skills"]))
            self.assertEqual("npx skills add acme/demo-repo --skill demo-skill", manifest["skills"][0]["install"])

    def test_manifest_without_remote_skips_install_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_skill(workspace, "demo-skill", "demo-skill", VALID_DESCRIPTION)
            with patch("scripts.skill_publisher.resolve_repo_slug", return_value=None):
                manifest = build_manifest(workspace)
            self.assertIsNone(manifest["repo"])
            self.assertNotIn("install", manifest["skills"][0])


class PublishOrgTests(unittest.TestCase):
    def test_skips_repo_without_skills_dir_and_aggregates_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspaces_dir = Path(temp_dir)
            (workspaces_dir / "no-skills-repo").mkdir()
            write_skill(workspaces_dir / "good-repo", "demo-skill", "demo-skill", VALID_DESCRIPTION)

            def fake_ensure_clone(org, repo, ws_dir):
                return ws_dir / repo

            with patch("scripts.skill_publisher.list_org_repos", return_value=["no-skills-repo", "good-repo"]), \
                 patch("scripts.skill_publisher.ensure_clone", side_effect=fake_ensure_clone), \
                 patch("scripts.skill_publisher.resolve_repo_slug", return_value="acme/good-repo"):
                result = publish_org("acme", workspaces_dir, register=False, mirror_to=None)

            statuses = {entry["repo"]: entry["status"] for entry in result["repos"]}
            self.assertEqual("skipped", statuses["no-skills-repo"])
            self.assertEqual("allow", statuses["good-repo"])
            self.assertEqual(1, len(result["skills"]))
            self.assertEqual(
                "npx skills add acme/good-repo --skill demo-skill",
                result["skills"][0]["install"],
            )

    def test_register_flag_calls_register_skill_for_each_valid_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspaces_dir = Path(temp_dir)
            write_skill(workspaces_dir / "good-repo", "demo-skill", "demo-skill", VALID_DESCRIPTION)

            def fake_ensure_clone(org, repo, ws_dir):
                return ws_dir / repo

            with patch("scripts.skill_publisher.list_org_repos", return_value=["good-repo"]), \
                 patch("scripts.skill_publisher.ensure_clone", side_effect=fake_ensure_clone), \
                 patch("scripts.skill_publisher.resolve_repo_slug", return_value="acme/good-repo"), \
                 patch("scripts.skill_publisher.register_skill", return_value={"skill": "demo-skill", "ok": True, "error": None}) as register_mock:
                result = publish_org("acme", workspaces_dir, register=True, mirror_to=None)

            register_mock.assert_called_once_with("acme/good-repo", "demo-skill")
            self.assertTrue(result["repos"][0]["register_results"][0]["ok"])

    def test_blocked_repo_is_excluded_from_aggregate_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspaces_dir = Path(temp_dir)
            write_skill(workspaces_dir / "broken-repo", "demo-skill", "demo-skill", "")

            def fake_ensure_clone(org, repo, ws_dir):
                return ws_dir / repo

            with patch("scripts.skill_publisher.list_org_repos", return_value=["broken-repo"]), \
                 patch("scripts.skill_publisher.ensure_clone", side_effect=fake_ensure_clone):
                result = publish_org("acme", workspaces_dir, register=False, mirror_to=None)

            self.assertEqual("block", result["repos"][0]["status"])
            self.assertEqual([], result["skills"])


if __name__ == "__main__":
    unittest.main()
