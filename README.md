# daxuan-figure-router

[![Tests](https://github.com/DaXuanGarden/daxuan-figure-router/actions/workflows/tests.yml/badge.svg)](https://github.com/DaXuanGarden/daxuan-figure-router/actions/workflows/tests.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

不用记住几十个绘图技能的名字：按当前任务找到合适的已有技能，再继续绘图。

Route installed scientific figure skills, preserve existing code and language choices, and load only the capabilities the task needs.

处理本机技能的发现、选择和交接。已有代码的小修改直接沿用；新图按输入状态、语言、领域、图型和输出要求选主技能；配色、模板和终检只在需要时加入。

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
python "$ROUTER_SKILL/scripts/skill_index.py" search "forest 森林图" --intent create --role primary --language R --limit 4
python "$ROUTER_SKILL/scripts/skill_index.py" show gwas-figure
python "$ROUTER_SKILL/scripts/skill_index.py" search "配色 palette" --intent palette
python "$ROUTER_SKILL/scripts/skill_index.py" vocabulary
python "$ROUTER_SKILL/scripts/skill_index.py" doctor
```

`search`/`list` 默认返回精简摘要；`show` 或 `--details` 展开完整信息。JSON结果包含准确路径、命中依据、过滤诊断和核验状态。依赖原有完整JSON结构的脚本应使用 `--details`。检索命中只是候选；路由 Skill 还会核对用户要求并读取被选技能原文。`doctor` 检查登记路径和文件，不能证明绘图依赖已安装或模板已跑通。

用户点名技能时优先用 `show` 无过滤查找。带过滤的查询把新装、迁移或源文档更新后命中的未知能力单列为有界 `review_candidates`，默认最多3项，可用 `--review-limit` 调整。这些候选需要复读原文，**不代表语言兼容或可以执行**；旧卡片不再作为当前能力的筛选依据。已核验且明确不兼容的能力不会混入这个分支。

`vocabulary` 展示实际可用的领域、任务标签和意图。`generic`→`general`、`clinical`→`medical` 有明确别名映射；未知领域或标签给出诊断。普通forest/map词不自动证明GWAS领域，常见中文图词会提取检索词，英文独立词优先于子串命中。

`--language` 约束要继续编辑/生成的数据图源代码。配色、QA、PPT重建和参考检索使用对应 `--intent`，避免把R源图的语言限制错误套到所有助手。后端与SVG/PPTX等输出形式分别记录。

查找新数据图的主执行者可加 `--role primary`，配色或QA任务按其职责检索。没有具体检索词时，未知候选仅报告待核验数量和补词提示，避免从全部安装技能中任意推荐。

能力摘要是首次整理时的参考快照。`source_hashes` 只核对文件内容版本；其他版本或换行差异可能产生 `review_required`，含义是需要复读原文，不代表安装损坏。摘要中的历史资源状态不代表其他机器的状态，CLI 会重新检查本机文件。

默认查找 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）、`~/.agents/skills`、当前项目的技能目录和 Codex 插件缓存。新技能不用先改注册表也能被搜索到，但能力状态为未精读；新增或更新后再次检索即可，不维护后台索引。

仅查询自定义根时重复传入 `--root /path/to/skills`；配合 `--catalog /path/to/catalog.json` 可使用自己核对过的相对路径与卡片。卡片按准确路径绑定，不会因为同名就自动套用。迁移后未重新绑定的技能仍可发现并精读，不能继承旧路径的已核验状态。

## 从技能到具体代码

部分高频能力带 `entry_points`：标明具体unit/模板、后端、输入类型、分析行为、来源和输出。选中后仍读取当次原文及入口：

| 请求 | 合适的安排 |
|---|---|
| 已有R森林图，只改字号和颜色 | 修改原代码，允许没有额外主技能 |
| 已完成MAGMA，用R画gene-level Manhattan | 找gwas-figure的通用R入口，核对P/FDR和阈值；不因历史Python adapter换语言 |
| 已有HR/CI，只要Lancet样式 | 借布局或改原代码；不直接运行会从生存数据拟合Cox的原项目模板 |
| R图截图转可编辑PPTX | 按重建职责查入口；R来源不要求PPT工具也用R后端 |
| 中国站点地图 | 查easyplot的地图函数和经纬度合同；map与heatmap不同 |

入口文件存在、hash相同，都不能证明运行环境或本次数据合同成立。输入是已完成结果时，`refit_or_test` 或未知分析行为的入口不得直接执行。详见 [路由记录与入口合同](references/routing-records.md)。

## 验证与边界

单一验证入口，无需安装清单中的第三方技能或访问网络：

```bash
python -B "$ROUTER_SKILL/scripts/verify.py"
```

验证覆盖临时目录发现、源变更、新装/迁移、词表、中文与领域检索、只读性，以及能力/验收合同和错误路由记录。CI在Python 3.10、3.13运行同一入口。测试数量以实际日志为准。

`test-prompts.json` 保存语义路由验收提示。独立演练记录可用以下命令检查覆盖和机械边界：

```bash
python "$ROUTER_SKILL/scripts/check_routes.py" --prompts "$ROUTER_SKILL/test-prompts.json" --records /path/to/route-records.json
```

记录校验会检查主技能、语言、显式选择、禁止动作，以及合理的“直接改原码”路线。自由文本科学条件和真实原文读取仍需独立审阅；通过记录检查不等于模型每次都会重现该路线，更不代表科研图已经渲染。仓库内的 [合成输入示例](examples/fixtures/) 用于编辑/路由演练，全部是模拟值，不包含真实研究数据。

路由器不改动原技能，不运行检索到的代码，不上传数据，不自动安装依赖或开启外部服务。只有具体绘图任务进入所选技能后，才按该技能和用户要求执行。

本地能力摘要与已知限制见 [capabilities.json](references/capabilities.json)，实际文件和所选技能原文优先。后续只按真实误路由修正规则；视觉灵感、文献检索和项目工作台留待后续需要时开发。

本仓库的原创代码与文档采用 [MIT](LICENSE) 许可证。第三方技能仍适用各自的许可证，能力摘要不授予其源码或素材的使用权。版本变更见 [CHANGELOG.md](CHANGELOG.md)。
