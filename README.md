# Publish Skill

面向 Codex 的 Skill 发布工具：校验 `SKILL.md`、生成 skills.sh 安装清单、把仓库镜像到其他平台。

## Skills

| Skill | 能力 |
| --- | --- |
| [`publish-skill`](skills/publish-skill/SKILL.md) | 校验 SKILL.md frontmatter/正文，生成 `npx skills add` 安装清单，将仓库 fork/同步到另一个 GitHub 组织 |

## 相关仓库

- [`farfarfun-skill/project-manager`](https://github.com/farfarfun-skill/project-manager)
- [`farfarfun-skill/lang-spec-hub`](https://github.com/farfarfun-skill/lang-spec-hub)
- [`farfarfun-skill/paperclip-governance`](https://github.com/farfarfun-skill/paperclip-governance)
- [`farfarfun-skill/service-governance`](https://github.com/farfarfun-skill/service-governance)

`project-manager` 仓库里的 `github-repo-standards` skill 负责审计 README 结构和 GitHub 仓库描述/Topics；本仓库只负责 `SKILL.md` 本身是否达到可发布的标准，以及发布动作本身。

## Requirements

- Codex
- Python 3.12（标准库即可，无第三方依赖）
- Git
- GitHub CLI（`gh`），已登录，`mirror` 子命令需要它

## Install

```bash
git clone https://github.com/farfarfun-skill/publish-skill.git
cd publish-skill

mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
for skill in skills/*; do
  ln -s "$(pwd)/$skill" "${CODEX_HOME:-$HOME/.codex}/skills/$(basename "$skill")"
done
```

链接命令在同名 Skill 已存在时会失败，不会覆盖现有安装。

## Quick Start

在 Codex 中直接说明要使用的 Skill：

```text
Use $publish-skill to validate this repository's SKILL.md files before I publish it.
```

也可以直接运行确定性脚本：

```bash
cd skills/publish-skill

# 1. 校验：每个 skills/<slug>/SKILL.md 的 frontmatter 和正文是否合规
python3 scripts/skill_publisher.py validate --workspace /path/to/repo --fail-on block

# 2. 生成安装清单：skills.sh 没有提交入口，装的人直接用这条命令
python3 scripts/skill_publisher.py manifest --workspace /path/to/repo

# 3. 可选：镜像到另一个 GitHub 组织（例如聚合类的 marketplace 组织）
python3 scripts/skill_publisher.py mirror --workspace /path/to/repo --target-org farfarfun-skills
```

`all` 子命令会依次跑 `validate` 和 `manifest`；`mirror` 会改变远端 GitHub 状态，需单独调用，且只应该在 `validate` 通过之后运行。

## Validation

```bash
(cd skills/publish-skill && python3 -m unittest discover -s tests -v)
```
