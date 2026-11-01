# daxuan-figure-router 打磨报告

## 1. 验料结果

用户目标是把既有科研绘图 Skills 路由起来，并在同一数据与科学含义下生成少量有理由的候选图供作者比较，最后记录选择；同事安装路由器时能按固定公开来源补齐缺失 Skill，已有版本跳过。原版检索和单图交接基础成立，但只读路由器没有比较合同、真实候选 gallery、选择证据或可审计安装来源。

本轮保留单图/改图快捷路径；比较模式只在作者请求替代方案时进入。路由器继续协调，不新建通用统计或绘图后端。

## 2. 访行记录

已核验 easyplot、nature-figure、academic-figure-skill、AgentFigureGallery、sci-color-palettes、make-sci-data-figures、polish-sci-figures、StatsVisual-Skill、SSCI-Plots、ARIS 相关入口及公开市场页面。可复用的模式是图集与选择语义、入口合同、色板审计、完整来源锁和离线 HTML。边界是公开同名版本可能与本机定制不同，wrapper 可能还需要外部应用，Skill 文件存在不等于运行时完整。

来源与固定 commit 见 [skill-sources.json](../references/skill-sources.json)；它覆盖39张现有能力卡，另有两个明确命名的新身份。未核实许可证或来源的项目保留为 unavailable，不猜 URL。

## 3. 生态位判断

它是“科研图路由 + 同数据候选比较 + 可追溯 Skill bootstrap”，而不是绘图库、统计分析服务或参考图片数据库。差异化可见产物是每个候选的真实 preview、科学/输入 hash、实际 analysis JSON、SVG/PDF/代码、离线 gallery、作者选择 history 和来源 receipt。

## 4. 过尺结果

| 维度 | 打磨前 | 打磨后 | 证据 |
|---|---:|---:|---|
| Frontmatter/触发 | 6/7 | 7/7 | SKILL 明确单图与比较/安装触发 |
| 工作流 | 8/12 | 11/12 | comparison-workflow 冻结→渲染→gallery→选择 |
| 失败模式 | 7/12 | 11/12 | blocked/invalid/QA、退出码、repair-latest |
| 检查点 | 4/6 | 6/6 | plan/check、hash、analysis一致、PNG实样本 |
| 可执行具体性 | 12/17 | 16/17 | 两个stdlib CLI、profiles、可重现示例 |
| 资源整合 | 2/4 | 4/4 | 41条来源、license、runtime分离 |
| 架构 | 8/12 | 11/12 | 协调层与现有主技能清晰分工 |
| 实测表现 | 6/23 | 18/23 | 88项测试、四张真实候选、browser桌面/移动、选择；公开 bootstrap 受网络阻塞 |
| 反例黑名单 | 5/7 | 7/7 | 不覆盖、不猜来源、不把候选/计划当成完成 |
| **总分** | **58/100** | **91/100** | 后分受公开网络活体验证限制 |

后分不是投稿质量或统计正确性评分；真实科研数据、模型合同和期刊指南仍由具体任务审阅。

## 5. 差距清单

- P0 已补：比较候选的输入/科学合同、实际结果证据、来源固定和不覆盖安装。
- P1：在网络可用的公开环境完成一次完整 `python_starter` bootstrap，再从 pinned receipt 运行 showcase；当前网络实测 raw/blob 请求均超时，失败记录已保留且未伪装成功。
- P1：为更多科学问题增加独立的真实示例；当前 live showcase 证明的是 accepted-results forest 的一个 bounded route。
- P2：增加作者偏好问卷、更多期刊版式和可选浏览器批注；不应先于数据/语义合同。

## 6. 三个打磨方向

A 细修：继续维护检索卡和常见误路由回归。

B 精雕（本轮执行）：多方案真实 gallery、科学不变证据、可恢复选择记录、固定来源 bootstrap。

C 开套件：未来将比较器、运行时环境检查、期刊模板和领域适配器拆成互相独立的 Skill；需更多真实反馈后再做。

## 7. 候选改写方案

本轮采用 B。`scripts/comparison.py` 只管理合同和证据，不执行 brief 中任意命令；`scripts/skill_bundle.py` 只在显式 install 时联网和写文件。PNG去重规范化到 RGBA16 实际样本，选择 journal 是权威、latest 是可修复缓存。

固定候选预算4–6，最大12；form/style 分轴，颜色变化单独标注。每个候选仍由一个具体 renderer 负责。安装 profile 默认空，python/R profile 明确列 Skill；已有真实 identity 跳过，同名不同源只标 review_required。

## 8. README 与 Showcase

README 新增同事 bootstrap 命令、profile、运行时边界；SKILL 新增显式安装规则；[comparison-workflow](../references/comparison-workflow.md) 记录选型和科学冻结；[skill-bootstrap](../references/skill-bootstrap.md) 记录来源、许可证和去重；[showcase](../showcase/README.md) 链接四候选和选择记录。

## 9. 执行计划

已完成：来源研究、冻结 brief、comparison/installer 实现、stdlib 回归、真实本机四候选、gallery browser 1440px/390px、选择记录、独立 QA、来源/third-party 保护快照。

下一轮：在网络稳定环境运行 `skill_bundle.py install --profile python_starter`；复读新安装 SKILL 后运行同一 showcase；补一个 R 真实入口；将公开 bootstrap 的 CI 作为手动、可审计 smoke，而不是每次单元测试下载。

## 10. 出师证书

```text
┌────────────────────────────────────────────┐
│ 出师证书 · 鲁班工坊                       │
│ 作品：daxuan-figure-router                 │
│ 过尺：58 分 → 91 分（实测；网络门单列）     │
│ 定位：同一数据的可解释候选图路由器           │
│ 绝活：冻结科学含义 + 实图 gallery + 可恢复选择 │
│ 下一步：在稳定网络完成 pinned bootstrap      │
│ 验收：鲁班 + 独立集成 QA                    │
└────────────────────────────────────────────┘
```

## 11. 回炉清单

每次新增公开来源须固定 commit、SKILL hash、许可证和入口复读；每次候选渲染须保留 data/science/analysis hash 和实际输出；每次选择只追加，不删除候选。持续观察错误路由、候选重复、运行时缺口和作者最终采用率。本轮不做文献图片抓取、收费图像生成、全自动统计、全期刊合规认证或任意远程安装脚本。

## 12. 需要用户确认的问题

本轮没有阻塞问题，用户已授权批量开发与推送。后续若要扩大范围，只需在具体任务中指定：目标期刊/版面、数据是原始观测还是已接受结果、以及是否允许补齐相应 profile。

## 13. 参考来源

- [Rimagination/easyplot](https://github.com/Rimagination/easyplot)
- [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)
- [TingxiYu/academic-figure-skill](https://github.com/TingxiYu/academic-figure-skill)
- [Dsadd4/AgentFigureGallery](https://github.com/Dsadd4/AgentFigureGallery)
- [WeiLab4Research/StatsVisual-Skill](https://github.com/WeiLab4Research/StatsVisual-Skill)
- [zhoy0409-debug/polish-sci-figures](https://github.com/zhoy0409-debug/polish-sci-figures)
- [Xiong-ding-kan/sci-color-palettes](https://github.com/Xiong-ding-kan/sci-color-palettes)
- [O0000-code/SSCI-Plots](https://github.com/O0000-code/SSCI-Plots)

## 验证记录

- `python3 -B scripts/verify.py`: 88 tests pass.
- `tests/test_comparison.py`: 33 tests pass, including RGB/RGBA duplicate normalization and recoverable selection interruption.
- `tests/test_skill_bundle.py`: 27 tests pass, including retry/fallback, source integrity, no-overwrite, dependency and zero-write repeat cases.
- `git diff --check`: pass.
- 本机 renderer showcase: 4 real drafts, 2 forms × 2 styles, identical supplied values/CI/axes/canvas, gallery `check` pass, selection recorded.
- Browser: static gallery opened at 1440×900 and 390×900; 4 articles and 4 images in both layouts.
- Public bootstrap: attempted twice in isolated roots; raw/blob network timeout, no completed skill published. This is a limitation, not a pass.
