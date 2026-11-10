# daxuan-figure-router：HyPrColoc 关系矩阵同行访行证据

检索日期：2026-11-10。范围只读；未安装或运行外部项目，未改动工作区。渠道覆盖 GitHub API、原始仓库文件、项目官方文档，以及 skills.sh。未使用或推测 star 数。原始 HyPrColoc vignette 的一次 curl 在 30 秒超时后，改用 GitHub contents API 成功取得原文。

## 1. 结论

这轮最值得补的是“关系与证据分层合同”：一行绑定一个真实 cluster 记录；性状成员关系独立编码；簇 PP、候选 SNP 精细定位支持、基因支持独立列出。公开同行已经很好地解决通用美化、矩阵拼装和集合编码，router 的可形成差异之处是把这些表达与源表逐行对账。

## 2. 访行记录：6 个真实候选，覆盖三类

| 同行与准确链接 | 类型 | 可核对内容 | 本轮可学手艺 | 不能照搬 |
|---|---|---|---|---|
| [K-Dense scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-visualization/SKILL.md)；[skills.sh 页面](https://skills.sh/k-dense-ai/scientific-agent-skills/scientific-visualization) | 直接绘图 skill | 工作流先记录变量语义、估计量、不确定性、变换和来源；明确区分 missing/zero/excluded；颜色须搭配符号或直接标签；导出可写 provenance manifest。市场页给出 `npx skills add ... --skill scientific-visualization`。旧 claude-scientific-skills URL 当前重定向至 scientific-agent-skills。 | 将科学语义与缺失值定义写入 brief；静态图必须自足；审查实际导出文件。 | 不把其 Python 后端和固定环境版本强加给已有 R 代码；它没有 HyPrColoc 专属关系模型。 |
| [HyPrColoc 官方仓库](https://github.com/jrs95/hyprcoloc)；[官方 vignette](https://github.com/jrs95/hyprcoloc/blob/master/vignettes/hyprcoloc.Rmd) | 相邻：本领域方法与诊断图 | README 提供 `hyprcoloc`、`sensitivity_plot`、`cred.sets`；vignette 明确每一行是性状簇，输出 cluster posterior、regional probability、candidate SNP 和 SNP 解释比例；敏感性图展示对先验和阈值的稳定性。 | 每行保留真实簇成员；在正文或图注明确 PP 是什么；将“稳定性”与单次 PP 分开。 | 其 trait×trait 稳定性热图不是 cluster×trait 成员矩阵；只绘图任务不能擅自重跑敏感性分析。 |
| [ComplexHeatmap](https://github.com/jokergoo/ComplexHeatmap)；[官方 UpSet 章](https://jokergoo.github.io/ComplexHeatmap-reference/book/upset-plot.html) | 相邻：矩阵与多证据注释 | README 给出 `Heatmap(mat1)+Heatmap(mat2)+row annotation`；官方章节说明二值 combination matrix，并区分 distinct/intersect/union；UpSet 主体可用点与线段实现，旁边独立放统计注释。 | cluster×trait 二值成员矩阵与 PP/SNP/gene 侧注释分面，对齐同一行；借其分组与注释接口。 | UpSet 聚合后的“集合组合数”不能冒充每个真实 HyPrColoc 簇；0 的含义必须自行定义。 |
| [ComplexUpset](https://github.com/krassowski/complex-upset)；[官方 R examples](https://krassowski.github.io/complex-upset/articles/Examples_R.html) | 相邻：集合成员关系 | README 的 showcase 同时给成图、可展开完整源代码、`upset_query`；R examples 区分 exclusive/inclusive 交集与并集，允许 `intersection_matrix()` 自定义点形和 query 高亮。仓库有由文档示例生成的 visual tests。 | 活跃成员点加连接线、固定性状顺序、单行高亮；把成员矩阵与连续证据注释分开；示例图和生成代码一起交付。 | 不能把“该簇未包含此性状”写成“该性状无遗传关联”；不能因默认聚合/排序丢失 cluster ID。 |
| [PlotNeuralNet](https://github.com/HarisIqbal88/PlotNeuralNet) | 手艺：源代码紧邻 showcase | README 首屏展示 FCN-8、FCN-32 等命名结果，并链接可编辑 Overleaf；提供 examples、Python 定义和单命令构建示例。 | router 的示例应展示“输入关系表→最终矩阵→可追踪行”的最小成品，图片旁给生成脚本和行键。 | 3D 神经网络外观不适用于共定位矩阵；连接形状只是展示手艺，不能迁移其科学含义。 |
| [Rougier Scientific Visualization: Python + Matplotlib](https://github.com/rougier/scientific-visualization-book) | 手艺：图例图库与可复现资源 | README 有整页 gallery、开放 PDF、图书源文件和代码示例，并明确章节覆盖布局、字体、颜色和 showcase。 | 给同一真实数据做成员点阵/矩阵侧注释两种候选，记录作者选择原因；用最终尺寸检查字体与层级。 | 图库仅提供版式和工艺启发，不提供本项目 PP、阈值、gene 映射或因果关系证据。 |

## 3. HyPrColoc 的 PP 必须怎样解释

首要来源：[官方 vignette](https://github.com/jrs95/hyprcoloc/blob/master/vignettes/hyprcoloc.Rmd)，本次读取的相关行 69–77、117–138、196–242；[官方 R 实现](https://github.com/jrs95/hyprcoloc/blob/master/R/hyprcoloc.R)，相关行 1271–1277、1317–1335、1525–1532；[原始方法论文](https://www.nature.com/articles/s41467-020-20885-8)。行号是检索时 master 的快照，之后可能变化。

- `posterior_prob`：该簇内全部性状共享一个因果变异假设的后验概率近似。官方 vignette 说明算法以 regional association probability `P_R` 与 alignment probability `P_A` 的乘积估计它。它属于“簇共定位证据”。
- `regional_prob`：区域内一个或多个变异为这些性状提供共享关联的证据，不能直接当作单一共享 SNP 的 PP。
- `candidate_snp`：模型优先排序的候选共享 SNP。
- `posterior_explained_by_snp`：该候选 SNP 解释的共定位 posterior 比例，是多性状 fine-mapping 支持。源码用最大完整共定位配置权重除以完整共定位配置权重总和，与 cluster posterior 分开输出；不能将两列互换或合并称为一个 PP。

官方反例最有用：vignette 中 traits 9–10 的共定位 posterior 约 0.9，但对具体 rs7524677 的支持弱；另一例中两个完全 LD 的 SNP 平分证据，无法仅靠 HyPrColoc 优先一个。这直接证明高 cluster PP 不等于候选 SNP 已被确认。

`PP > 0.7` 可陈述为“达到本分析预先声明阈值的共定位支持”。不能写“已证实因果效应”，因为：

1. 被比较的是共享变异的统计假设，模型没有估计“性状 A 导致性状 B”的方向或介导效应。原始论文的定义就是共享变异与性状簇；从共享机制到定向效应需要额外证据。
2. 后验依赖先验、阈值和输入数据。官方要求评估 sensitivity，并举例说明默认参数下较大性状集可能含假阳性；0.7 不是免除这些条件的证实标准。
3. 方法假设每个区域每个性状至多一个因果变异，并依赖变异覆盖、适当的样本相关性处理；原论文专门分析了假设违背时的性能下降。
4. 簇 PP 与具体 SNP 的精细定位支持不同；LD 可导致多个 SNP 难分。
5. 变异到基因的命名需要独立注释、QTL 或功能证据。HyPrColoc 的共享变异 posterior 本身不是邻近基因的因果 posterior，也不是 MAGMA 的支持概率。

推荐图例成文：“点表示该性状属于相应 HyPrColoc 簇；PP 表示簇内性状共享一个遗传变异的模型后验支持，保留 PP>0.7 的记录。候选 SNP 的 posterior 解释比例及基因注释来源分别列示。该结果支持共享遗传信号，不能单独确定性状间因果方向或因果基因。”

## 4. 适合 router 本轮落地的三项要求（由上述来源推导）

1. **关系键**：brief/recipe 应要求 `cluster_record_id`、`window_id`（或输入区域）、`candidate_snp`、原始 `traits` 列及来源文件。不要仅凭同一个 SNP、重叠窗口或同名基因将多行簇自动合并。随图输出 cluster×trait 长表；逐行检查绘制成员集合等于源表成员集合。若 LST/主性状只放在标题或前置固定列，必须明示每行是否真的包含它。
2. **单行可读**：固定列顺序；成员用实心点等离散编码，PP 单独作窄侧栏；行侧可写成员数和精简性状列表。未入簇、未输入/未分析、缺失应分开定义，不能都默认为零。保持同一行键同步 PP、候选 SNP 和基因注释，不用基因色彩承担成员关系。
3. **证据分层**：至少保留 `cluster_pp`、`candidate_snp_posterior_fraction`、`gene_support_type/source` 三类字段和图例。基因支持明确标识 candidate SNP 的精确注释、窗口注释、MAGMA 等实际来源；窗口支持不能渲染成 candidate SNP 精确命中，也不能由高 PP 升格为因果基因。

适合的定位：“把已验收的共定位结果画成可逐行追回来源、能区分共享成员与证据强度的科研关系图。”通用美化工具可以作为 renderer；router 负责选择与交接上述合同。
