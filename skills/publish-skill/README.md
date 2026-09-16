# Publish Skill

用于把一个 skill 仓库发布出去的 Codex skill：校验 `skills/<slug>/SKILL.md` 是否符合 skills.sh 等安装工具的发现规则，生成安装清单，并可选地把仓库镜像到另一个 GitHub 组织。

## 功能

- 校验每个 `SKILL.md` 的 frontmatter（`name`、`description`）与正文是否完整、格式是否合规。
- 生成 `npx skills add <owner>/<repo> --skill <name>` 安装命令清单，用于 skills.sh 发现（skills.sh 没有提交入口，靠爬取公开仓库）。
- 将仓库 fork/同步到另一个 GitHub 组织（例如聚合类的 marketplace 组织），命名规则 `<owner>--<repo>`。

## 快速开始

```bash
python3 scripts/skill_publisher.py validate --workspace /path/to/repo --fail-on block
python3 scripts/skill_publisher.py manifest --workspace /path/to/repo
python3 scripts/skill_publisher.py mirror --workspace /path/to/repo --target-org farfarfun-skills
```

## 文档

- [Skill 使用说明](SKILL.md)
