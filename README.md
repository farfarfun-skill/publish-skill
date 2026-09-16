# Publish Skill

把 `farfarfun-skill` 组织下的 skill 仓库发布出去的命令行工具：校验 `SKILL.md`、生成 skills.sh 安装清单、可选镜像到其他平台。

skills.sh 没有提交/审核入口，它靠爬取公开仓库里的 `skills/<slug>/SKILL.md` 来发现 skill，靠 CLI 的匿名安装遥测（`npx skills add`）来排行。所以这里的"发布"就是：确认每个 `SKILL.md` 合规、仓库公开可发现，并生成/触发那份安装清单。

## Install

```bash
git clone https://github.com/farfarfun-skill/publish-skill.git
cd publish-skill
```

无第三方依赖，纯 Bash 脚本；需要 `git`、`gh`（已登录的 GitHub CLI）和 `awk`/`sed`。

## Usage

一键发布 `farfarfun-skill` 组织下的所有仓库：

```bash
./scripts/publish.sh --org farfarfun-skill --workspaces-dir /path/to/farfarfun-skill
```

`--workspaces-dir` 默认是本仓库自己所在目录的上一级目录，所以在 `publish-skill` 仓库自己的目录下直接运行，也能自动发现同级的 `project-manager`、`lang-spec-hub`、`paperclip-governance`、`service-governance` 等仓库。它会：

1. 列出该组织下所有公开、非 fork 的仓库；本地缺失的自动 `git clone`，已存在的直接用（不会 `pull`）。
2. 对每个含 `skills/` 目录的仓库跑校验，没有 `skills/` 目录的仓库（如 `.github`）会被跳过而不是判失败。
3. 逐仓库打印 `npx skills add <owner>/<repo> --skill <name>` 安装清单——这份清单就是能被 skills.sh 查到的凭证。

可选参数：

- `--register`：为每个通过校验的 skill 额外在本机执行一次 `npx skills add ... -y`，这是真正会给 skills.sh 安装遥测/排行榜贡献数据的动作（也会把 skill 装进本机 agent 目录，注意副作用）。
- `--mirror-to farfarfun-skills`：额外把每个通过校验的仓库 fork/同步到另一个组织。

## Validation

已针对真实的 `farfarfun-skill` 组织跑通（校验各仓库 `SKILL.md`、正确跳过 `publish-skill`/`.github` 等无 `skills/` 目录的仓库），并用临时目录手工验证过 WARN/BLOCK 各分支：

```bash
bash -n scripts/publish.sh
./scripts/publish.sh --org farfarfun-skill --workspaces-dir /path/to/farfarfun-skill
```
