# Skill 打磨报告：共享性状关系可追踪

日期：2026-11-10。目标：daxuan-figure-router。范围只有一个打磨面：已认可的多性状共定位图，如何把位点—性状—证据关系准确交接、画清楚并核对。版本 0.3.1。

## 1. 验料结果（Skill 前提挑战）

值得小修。Router 的职责是发现、选择与交接已有绘图能力，不应变成新的共定位分析工具。通用美化并不能防止成员关系、PP 字段或基因证据被错误连在一起。此次保留用户认可的 R/ggplot2 图，只补专题交接合同与独立校验工具；不重拟合、筛选、改变阈值或全局主题。

## 2. 访行记录（同类 Skill 横向对标）

访问 GitHub、官方文档与 skills.sh，核对六个真实对象：K-Dense scientific-visualization（直接 skill）；HyPrColoc、ComplexHeatmap、ComplexUpset（相邻方法/编码）；PlotNeuralNet、Rougier scientific-visualization-book（可复现 showcase 手艺）。没有推测 stars 或安装量。准确链接、取舍与官方语义证据见 [完整访行记录](multitrait-colocalization-peers-20261110.md)。

可学：输入语义与缺失状态先定义；矩阵与侧注释按同一行键对齐；示例成图与生成代码一起交付。不能照搬：UpSet 聚合不能代替真实 cluster；Python 通用流程不能覆盖已有 R 脚本；精美图库不提供统计证据。

## 3. 生态位判断

通用技能继续负责绘图。Router 的差异化是把“谁共享什么”写成可核对的交接：真实区域/簇、候选 SNP、精确性状集合及证据来源。cluster PP、候选 SNP fine-mapping 支持、基因支持分别保存。PASS 只涉及所声明的检查层级，不是因果结论或发表保证。

## 4. 过尺结果（活体检查 + 质量评分）

以最新远程基线 `dd02352` 为准，单独解包执行：**99 tests PASS**；加入本轮后：**117 tests PASS**，其中新增 **18** 个语义、CLI、成图映射及可选事件逻辑测试。本地较旧基线曾通过 88 个测试；远程已有的 11 个测试不计为本轮贡献。结构尺为 10 PASS、3 WARN、0 FAIL；WARN 是 marketplace、GIF 和 skills.sh 徽章，不是本轮阻断。

| 维度 | 权重 | 前→后（评审估计） | 本轮证据及剩余边界 |
|---|---:|---:|---|
| Frontmatter 与触发 | 7 | 6→6 | 沿用既有触发，不扩为分析工具 |
| 工作流清晰度 | 12 | 10→11 | 已认可样式优先，交接/数据/映射/成品分层 |
| 失败模式编码 | 12 | 8→11 | 防漏成员、重复键、整列遗漏、跨空白连接 |
| 检查点设计 | 6 | 4→6 | 独立 manifest、实际 SVG、人工点读 |
| 可执行具体性 | 17 | 13→16 | 标准库 CLI 与完整合成 demo |
| 资源整合度 | 4 | 3→4 | 官方 PP 定义与相邻可视化来源 |
| 整体架构 | 12 | 11→11 | 专题引用按需加载，renderer 不换语言 |
| 实测表现 | 23 | 18→21 | 基线 99/99、候选 117/117、真实成品回放；没有 LLM 随机多次 benchmark |
| 反例与黑名单 | 7 | 5→7 | 直接执行反例，不把缺失/注释/共定位写成因果证实 |
| **合计** | **100** | **78→93** | **主观、有证据的审阅估计；不是测量的成功率或美学分数** |

活体：实际项目原生 PDF/SVG 打开审阅，并从 SVG 圆点坐标反解成员与原始记录逐个比对。真实结果只保存本地；公开仓库仅交付明确合成输入。隔行带是阅读引导，不承载统计意义。交互用实际 JS 的 DOM 替身执行鼠标/键盘状态验证；未配置完整浏览器，不宣称浏览器或无障碍兼容性实测。

## 5. 差距清单

已关闭 P0：cluster PP 与 SNP fraction 可能混淆；横线穿越空白暗示成员；只看正成员不能发现整列缺失；完整来源集合与 compact 显示顺序混用。
已关闭 P1：漂亮散点难顺行追踪，缺可复现示例，hover/focus/selected 可同时高亮多行。
保留 P2：自动真实浏览器/屏幕阅读器回归、其它多性状方法 adapter。不能用当前测试推断这些能力已存在。

最缺三件事：关系行键、独立来源集合、实际成品对账。可形成优势的三件事：保留作者已选样式、统计语义可执行检查、公开最小可复现示例。

## 6. 三个打磨方向

A 细修：保留点阵、加入极淡同行阅读带和可查的精确成员集合。B 精雕：新增完整交互工作台。C 套件：开发统一多方法分析/绘图后端。
本轮选 A，加一个可选静态 HTML 阅读副本；用户已明确授权同步改图、改 Skill 和推送，无需重复询问。B/C 会引入不必要的后端范围，未实施。

## 7. 候选改写方案

- `SKILL.md` 增加按需专题入口；不改其它技能的全局行为。
- `references/multitrait-colocalization.md` 写入科学对象、原始字段绑定、源/显示 universe、视觉和验收合同。
- `scripts/check_cluster_membership.py`：严格 `>` 阈值仅核验、不过滤；支持独立 `--source-traits`、实际绘制标记与可选连接段检查。
- `scripts/cluster_reading.js`：唯一 active 行；hover/focus 覆盖 selection，离开恢复，Escape 清除。
- `tests/test_cluster_membership.py`：18 个正反例；Node 缺失时仅可选事件逻辑测试明确 skip。

数据层 PASS 不假装审阅 SVG；映射层 PASS 不替代人工点读。未声明独立 source universe 时，报告明确为 `observed_in_input_only`。同一个候选 SNP 出现在不同真实簇中允许保留，不擅自合并为独立因果位点。

## 8. README 与 Showcase 升级

README 首部增加 [合成示例](../examples/cluster-membership/README.md)，展示成员矩阵、单独 PP 侧栏和无统计意义的淡行带。示例有三份 TSV、生成脚本、SVG、可选交互 HTML；Python 标准库即可复现，完全不含真实研究记录。R 项目继续沿用其 R renderer。

## 9. 执行计划

本轮完成：冻结基线、六同行调研、小范围改写、18 个反例/正例、远程基线/候选完整测试、真实 SVG 回放、独立审阅、installed 有选择同步、提交和 GitHub 核对。
后续仅在具体反馈出现时补浏览器跨平台测试；不为本轮新增通用图形框架、不重跑 GWAS，也不接入外部生成服务。

## 10. 出师证书

[结果卡](multitrait-colocalization-result-card-20261110.svg)。核验数字与评分口径分别注明；它是本轮完成记录，不是期刊认证。

## 11. 回炉清单

继续观察 HyPrColoc 官方输出字段、ComplexHeatmap/ComplexUpset 的成员编码与版本变化。下一轮收集作者实际阅读错误，若行带不能解决再提出候选；不自动重选样式、改 PP、增加人为筛选、拼不同性状对的基因证据。

安装副本存在同仓库远程基线外的局部架构合同；本轮保留它，未整体覆盖或上传。发布只含本次共定位关系合同与其直接验证资产。远程已有三个提交先行快进整合，避免覆盖他人的已发布更新。

## 12. 需要用户确认的问题

无阻断问题。本轮沿用作者已认可图型、统计阈值和色板；用户已明确授权改图、改 Skill 与 GitHub 推送。若之后要改变模型或阈值，应作为新的分析任务审阅，而非借可视化默改。

## 13. 附录：参考来源

- [K-Dense scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-visualization/SKILL.md)；[skills.sh](https://skills.sh/k-dense-ai/scientific-agent-skills/scientific-visualization)
- [HyPrColoc 官方仓库](https://github.com/jrs95/hyprcoloc)；[官方 vignette](https://jrs95.github.io/hyprcoloc/articles/hyprcoloc.html)
- [ComplexHeatmap](https://github.com/jokergoo/ComplexHeatmap)；[UpSet 文档](https://jokergoo.github.io/ComplexHeatmap-reference/book/upset-plot.html)
- [ComplexUpset](https://github.com/krassowski/complex-upset)；[R examples](https://krassowski.github.io/complex-upset/articles/Examples_R.html)
- [PlotNeuralNet](https://github.com/HarisIqbal88/PlotNeuralNet)
- [Rougier Scientific Visualization Book](https://github.com/rougier/scientific-visualization-book)
