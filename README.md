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

也可以直接运行确定性脚本。一键发布 `farfarfun-skill` 组织下的所有 skill 仓库：

```bash
cd skills/publish-skill
python3 scripts/skill_publisher.py org --org farfarfun-skill --workspaces-dir /home/bingtao/workspace/github/farfarfun-skill
```

`workspaces-dir` 默认就是 `--workspace`（默认当前目录）的上一级目录，所以在 `publish-skill` 仓库自己的目录下直接运行也能自动发现同级的 `project-manager`、`lang-spec-hub`、`paperclip-governance`、`service-governance` 等仓库。它会：

1. 列出该组织下所有公开、非 fork 的仓库；本地缺失的自动 `git clone`，已存在的直接用（不会 `pull`）。
2. 对每个含 `skills/` 目录的仓库跑 `validate`，没有 `skills/` 目录的仓库（如 `.github`）会被跳过而不是判失败。
3. 汇总打印整个组织的 `npx skills add <owner>/<repo> --skill <name>` 安装清单——skills.sh 没有提交入口，这份清单就是"发布"的产物。

可选参数：

- `--register`：为每个通过校验的 skill 额外在本机执行一次 `npx skills add ... -y`，这是真正会给 skills.sh 安装遥测/排行榜贡献数据的动作（也会把 skill 装进本机 agent 目录，注意副作用）。
- `--mirror-to farfarfun-skills`：额外把每个通过校验的仓库 fork/同步到另一个组织。

单仓库场景也可以用更细粒度的子命令：

```bash
# 校验：单个仓库里每个 skills/<slug>/SKILL.md 的 frontmatter 和正文是否合规
python3 scripts/skill_publisher.py validate --workspace /path/to/repo --fail-on block

# 生成单个仓库的安装清单
python3 scripts/skill_publisher.py manifest --workspace /path/to/repo

# 把单个仓库镜像到另一个 GitHub 组织
python3 scripts/skill_publisher.py mirror --workspace /path/to/repo --target-org farfarfun-skills
```

`all` 子命令会依次跑 `validate` 和 `manifest`；`mirror` 会改变远端 GitHub 状态，只应该在 `validate` 通过之后运行。

## Validation

```bash
(cd skills/publish-skill && python3 -m unittest discover -s tests -v)
```
