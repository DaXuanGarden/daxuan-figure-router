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

公开发布后的标准安装入口（当前版本尚未完成 GitHub/Release 验证）为：

```bash
npx skills add DaXuanGarden/daxuan-figure-router --skill daxuan-figure-router --yes
```

本包借鉴并遵循 [Qiaomu Skill Publisher](https://github.com/joeseesun/qiaomu-skill-publisher)
的证据、评估和发布边界；当前目录的本地验证不能替代远端安装证据。

维护信息：Copyright (c) 向阳乔木；X: https://x.com/vista8；GitHub: https://github.com/joeseesun/。

## Prerequisites

- [ ] Python 3.10+
- [ ] Git（仅用于完整安装或发布）
- [ ] 目标绘图 Skill、R/Python 后端和字体按各自项目需要安装

<!-- qiaomu-profile:start -->
## 关于向阳乔木

向阳乔木（乔向阳 / Joe）是一位实践型 AI 产品与内容创作者，长期把前沿 AI 变化转译成可复用的工作流、产品判断、AI 编程实践、AI 搜索实践和 GEO/AI 营销方法。

- 个人网站: https://qiaomu.ai
- 博客: https://blog.qiaomu.ai
- X: https://x.com/vista8
- GitHub: https://github.com/joeseesun/
- 微信公众号: 向阳乔木推荐看

### 支持与关注

| 打赏支持 | 微信公众号 |
|---|---|
| <img src="assets/qiaomu-profile/qiaomu_reward_qr.png" alt="向阳乔木打赏二维码" width="180" /> | <img src="assets/qiaomu-profile/qiaomu_wechat_public_account_qr.jpg" alt="向阳乔木推荐看公众号二维码" width="180" /> |
| 感谢支持乔木持续分享 AI 实践 | 扫码关注「向阳乔木推荐看」 |

<!-- qiaomu-profile:end -->

## License

本路由器原创代码和文档采用 [MIT License](LICENSE)；第三方绘图 Skill、字体、模板和
素材继续遵循各自许可证。

已有同名目录时不要直接覆盖，先确认它是独立安装副本还是 Git 克隆。新会话中可调用 `$daxuan-figure-router`；也可以直接引用安装目录中的 `SKILL.md`。

**参考清单中的 39 项绘图能力不随本仓库提供，也无需全部安装。** 可按明确的 profile 下载有核实来源的技能文件，已有安装自动跳过。 路由器只选择当前机器上实际存在的技能。它们的模板、图片、运行时和服务按各自技能的安装方式及许可证提供；仓库仅包含本路由器、能力摘要和测试。即使没有清单中的技能，检索仍能运行并报告空结果或缺项。

## 给同事补齐绘图技能

安装路由器后，只需运行一次所需的集合；已有技能会跳过：

```bash
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/skill_bundle.py" plan --profile python_starter
python "$ROUTER_SKILL/scripts/skill_bundle.py" install --profile python_starter
```

R 使用 `r_starter`；单项可用 `--skill easyplot`。默认不下载全部清单。来源固定到 commit 并核验身份/哈希、保留许可证；没有核实来源的项明确报告，现有目录不覆盖。技能文件安装成功不等于 Python/R 包、字体或外部服务已可用。详见 [安装与来源说明](references/skill-bootstrap.md)。

## 使用示例

你可以直接这样说：

在 Codex 中调用：

```text
用 $daxuan-figure-router 看看这份数据适合画什么图，然后完成绘图。
用 $daxuan-figure-router 修改这份 R 森林图脚本，只调整字号和配色。
用 $daxuan-figure-router 给已有 TWAS 结果选择合适的绘图技能，保留 R。
```

自动技能选择保持启用。已安装的技能通常会在新会话中发现，也可以用绝对路径引用本目录的 `SKILL.md`。

更多请求与职责安排见 [路由示例](examples/routing.md)。

## 验证

```bash
python3 scripts/validate_skill.py .
python3 scripts/trigger_eval.py . --cases evals/trigger_cases.json
python3 scripts/figure_brief.py validate --brief path/to/brief.json --check-paths
python3 scripts/verify.py
```

### Troubleshooting

- `review_required`：先补齐输入表、基因组版本、祖源、阈值或注释来源，再生成候选图。
- `analysis_effect` 不是 `none`：该入口可能会重跑上游统计，不能直接用于已验收结果的样式比较。
- renderer 或字体缺失：记录 `degraded`/`missing evidence`，不要把文件导出成功写成真实渲染已验证。
- 只有一个候选图：先检查 FigureBrief 是否声明了足够的表达目的；颜色变化单独归为样式变体。

GWAS/MTAG/PLACO+/coloc/MR 等已完成结果的图形合同、候选图比较和合成演练见
[GWAS figure recipes](references/gwas-figure-recipes.md) 与
[GWAS recipe dry-run](examples/gwas/README.md)。这些配方只负责展示已验收结果，
不会重新运行上游统计分析。

## 同一数据的候选图

作者要求“给几种形式/样式比较”时，使用 [comparison workflow](references/comparison-workflow.md)：先冻结输入与科学合同，再由已有绘图 Skill 生成真实 PNG/SVG/PDF，最后用离线 gallery 供作者选择。默认只生成 4–6 个有理由的候选；不同图型、版式和色板分开记录，颜色变化不会伪装成新的科学表达。一个可运行的 accepted-results forest 示例见 [showcase](showcase/README.md)。

```bash
python "$ROUTER_SKILL/scripts/comparison.py" plan --brief brief.json --outdir comparison-run
# 由选中的现有绘图 Skill 生成 results.json 后：
python "$ROUTER_SKILL/scripts/comparison.py" assemble --plan comparison-run/plan.json --results results.json
python "$ROUTER_SKILL/scripts/comparison.py" check --run comparison-run
python "$ROUTER_SKILL/scripts/comparison.py" select --run comparison-run --id candidate-id --reason "作者选择理由"
```

`comparison.py` 不执行 JSON 中任意命令；阻塞候选、未审阅和 QA 失败都保留原因。选择记录只表示待精修，不代表投稿就绪。

### GWAS FigureBrief

项目有多种已完成 GWAS/post-GWAS 结果时，建议先保存一份版本化 FigureBrief，
再进入同一数据的候选图比较。FigureBrief 固定科学问题、结果来源、候选图目的、
ANNOVAR/coloc/PLACO+ 等证据边界和导出要求；它不替代上游统计脚本，也不改变任何
P 值、FDR、clumping 或共定位阈值。

```bash
python "$ROUTER_SKILL/scripts/figure_brief.py" validate --brief path/to/brief.json
# 项目级 brief 可声明 project_root，再检查真实输入文件：
python "$ROUTER_SKILL/scripts/figure_brief.py" validate --brief path/to/brief.json --check-paths
python "$ROUTER_SKILL/scripts/figure_brief.py" list-recipes
```

当前 recipe 覆盖 global/local genetic correlation、PLACO+、PLACO+–coloc shared loci、
MR 和 gene-level 图形。每个 recipe 都声明 `analysis_effect: none`，并明确要求把候选
基因注释与因果基因结论分开。`--check-paths` 是可选的项目文件存在性检查；默认只校验
可移植的结构合同。

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

只读检索不执行代码或联网；明确调用 bootstrap 才安装锁表中的技能文件，运行时与外部服务独立检查。只有具体绘图任务进入所选技能后，才按该技能和用户要求执行。

本地能力摘要与已知限制见 [capabilities.json](references/capabilities.json)，实际文件和所选技能原文优先。后续只按真实误路由修正规则；视觉灵感、文献检索和项目工作台留待后续需要时开发。

本仓库的原创代码与文档采用 [MIT](LICENSE) 许可证。第三方技能仍适用各自的许可证，能力摘要不授予其源码或素材的使用权。版本变更见 [CHANGELOG.md](CHANGELOG.md)。
