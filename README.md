# daxuan-figure-router

[![Tests](https://github.com/DaXuanGarden/daxuan-figure-router/actions/workflows/tests.yml/badge.svg)](https://github.com/DaXuanGarden/daxuan-figure-router/actions/workflows/tests.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

不用记住几十个绘图技能的名字：按当前任务找到合适的已有技能，再继续绘图。

Route installed scientific figure skills, preserve existing code and language choices, and load only the capabilities the task needs.

第一版只处理本机技能的发现、选择和交接。已有代码的小修改直接沿用；新图按语言、领域、图型和输出要求选主技能；配色、模板和终检只在需要时加入。

## 安装

需要 Python 3.10+ 和 Git；检索脚本没有第三方 Python 依赖。在已安装 Codex 的机器上，全新安装：

```bash
git clone https://github.com/DaXuanGarden/daxuan-figure-router.git "${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
```

已有同名目录时不要直接覆盖，先确认它是独立安装副本还是 Git 克隆。新会话中可调用 `$daxuan-figure-router`；也可以直接引用安装目录中的 `SKILL.md`。

**参考清单中的 39 项绘图能力不随本仓库提供，也无需全部安装。** 路由器只选择当前机器上实际存在的技能。它们的模板、图片、运行时和服务按各自技能的安装方式及许可证提供；仓库仅包含本路由器、能力摘要和测试。即使没有清单中的技能，检索仍能运行并报告空结果或缺项。

## 使用示例

在 Codex 中调用：

```text
用 $daxuan-figure-router 看看这份数据适合画什么图，然后完成绘图。
用 $daxuan-figure-router 修改这份 R 森林图脚本，只调整字号和配色。
用 $daxuan-figure-router 给已有 TWAS 结果选择合适的绘图技能，保留 R。
```

自动技能选择保持启用。已安装的技能通常会在新会话中发现，也可以用绝对路径引用本目录的 `SKILL.md`。

更多请求与职责安排见 [路由示例](examples/routing.md)。

## 只读检索

需要 Python 3.10+，无第三方 Python 依赖。在项目目录运行，以便发现项目内技能：

```bash
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/skill_index.py" search "forest 森林图" --language R --limit 4
python "$ROUTER_SKILL/scripts/skill_index.py" show gwas-figure
python "$ROUTER_SKILL/scripts/skill_index.py" list --role helper
python "$ROUTER_SKILL/scripts/skill_index.py" doctor
```

JSON 结果给出实际路径、能力摘要和资源检查。检索命中只是候选；路由 Skill 还会核对用户要求并读取被选技能原文。`doctor` 检查登记路径和文件，不能证明绘图依赖已安装或模板已跑通。

用户点名技能时优先用 `show` 无过滤查找。未登记技能的语言/角色未知，带这些过滤条件会排除它；文件发生变化时结果会提示重新阅读，不能把旧摘要当作更新后的能力。

能力摘要是首次整理时的参考快照。`source_hashes` 只核对文件内容版本；其他版本或换行差异可能产生 `review_required`，含义是需要复读原文，不代表安装损坏。摘要中的历史资源状态不代表其他机器的状态，CLI 会重新检查本机文件。

默认查找 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）、`~/.agents/skills`、当前项目的技能目录和 Codex 插件缓存。新技能不用先改注册表也能被搜索到，但能力状态为未精读；新增或更新后再次检索即可，不维护后台索引。

## 验证与边界

运行脚本回归检查：

```bash
python -B -m unittest discover -s "$ROUTER_SKILL/tests" -p 'test_*.py' -v
```

回归检查使用临时技能目录，不要求安装参考清单中的技能。初始版本包含 8 项脚本回归检查与 16 个路由验收提示；开发阶段另做过 10 项路由演练，验证了检索和交接，没有将演练计为科研图的实际渲染验证。

路由器不改动原技能，不运行检索到的代码，不上传数据，不自动安装依赖或开启外部服务。只有具体绘图任务进入所选技能后，才按该技能和用户要求执行。

本地能力摘要与已知限制见 [capabilities.json](references/capabilities.json)，实际文件和所选技能原文优先。后续只按真实误路由修正规则；视觉灵感、文献检索和项目工作台留待后续需要时开发。

本仓库的原创代码与文档采用 [MIT](LICENSE) 许可证。第三方技能仍适用各自的许可证，能力摘要不授予其源码或素材的使用权。版本变更见 [CHANGELOG.md](CHANGELOG.md)。
