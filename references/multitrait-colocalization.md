# 多性状共定位：让同一行的共享关系看得见、查得到

适用：已有 HyPrColoc 或等价多性状共定位结果，作者认为“散点漂亮，但看不出哪个位点共享哪些性状”。
沿用已认可的 R/Python 脚本、颜色、行列顺序和统计结果；这里只规定交接与验收，不拟合模型。

## 1. 先固定科学对象

- 一行是一个**区域中的真实性状簇记录**，保存 `cluster_id`、`window_id`、`candidate_snp`、原始性状集合和 `cluster_pp`。
  同一 SNP 可对应不同区域或不同性状集合；不得仅按 SNP、重叠窗口或基因名自动合并。
- cluster PP 支持簇内性状共享一个因果变异的模型；它不是性状之间的因果效应、每个成员各自的 PP、pairwise coloc PP.H4，或候选 SNP 已被确认的概率。
- `candidate_snp_posterior_fraction` 若有来源就单独保留，缺失不以 cluster PP 填充。高 cluster PP 也可能伴随较弱的单个 SNP 精细定位证据。
- 基因斜体是命名规范。ANNOVAR 定位注释、MAGMA/TWAS/SMR 支持与因果基因结论分开；多个方法共用 MTAG 输入时称为跨方法支持。
  “三方法”必须同一基因、同一组成性状对，不能从不同性状对拼交集。

## 2. 优先改善阅读路径，不重做已认可风格

主问题是“这一行共享哪些性状”：先采用 cluster × trait 点阵，右侧独立 PP 棒棒糖。

1. rsID/基因、所有成员点、基因证据和 PP 用同一行中心坐标；固定列顺序。
2. 作者已认可点阵但不易横向追踪时，优先试**极淡中性隔行带**，从标签横跨至 PP；按固定显示行号交替，不能按显著性或优先基因选择。
   行带不表示置信区间或证据强弱；无描边，所有文字与点在其上方。正文不要塞一列很长的性状字符串来挤压已认可版式。
3. 不默认恢复跨空白单元格的长成员线。若明确需要连接线，只连接连续的真实成员 run，跨非成员/未输入格必须断开。
4. 分类条紧靠性状标签，分类颜色与同篇文章固定；成员、簇 PP、基因支持的符号语义分离。
5. 静态图需独立可读。可另给 hover/键盘 focus 高亮整行和精确性状列表，交互不能替代可发表的静态表达。

## 3. 最小、可移植的来源合同

`clusters.tsv`：`cluster_id, window_id, candidate_snp, cluster_pp, trait_set`；性状集合用 `|` 分隔。
可选独立列 `candidate_snp_posterior_fraction`。

`memberships.tsv`：`cluster_id, trait, in_input, in_cluster`，明确记录完整行×性状状态。
布尔只接受 true/false/1/0（大小写可变）。实心点只表示 `in_cluster=true`。
空白可包含“评估但未入簇”及“区域未纳入”，均不意味着单性状无关联。
绘图可只显示有成员的列，完整来源不能因此删除其余列。

```bash
python scripts/check_cluster_membership.py \
  --clusters examples/cluster-membership/clusters.tsv \
  --memberships examples/cluster-membership/memberships.tsv \
  --rendered-memberships examples/cluster-membership/plotted-members.tsv \
  --source-traits 'Exposure|Trait_A|Trait_B|Trait_C|Trait_D' \
  --pp-threshold 0.70 --out local-reports/cluster-audit.json
```

`--pp-threshold` 声明已采用的严格 `>` 阈值，**不筛选数据**。不满足时报告冲突，不能为了布局改 PP 或丢行。
`--source-traits` 来自独立输入 manifest，核对完整来源中的性状集合，能发现整列零成员性状被删除。未给出时报告仅为 `observed_in_input_only`，不能声称原始来源列已全部保留。显示列顺序与完整来源集合分开，允许省略全为非成员的显示列。

可选 `--connectors` 指向 `cluster_id,left_trait,right_trait` 表，并给出 `--trait-order 'A|B|C'`。
校验器拒绝跨空白格连线；它不自动插线，不重排性状，不运行 HyPrColoc。

## 4. 验收三把尺

| 尺 | 必查内容 | 不能据此声称 |
|---|---|---|
| 数据 | 每行性状集合完全相等；PP/区域/候选 SNP 同行；重复键和未知状态报错；完整输入状态保留 | 上游模型或因果结论已验证 |
| 映射 | 实际绘图标记 `(cluster_id, trait)` 集合与源表完全一致；连接线不跨 blank | SVG 已真实逐点审阅（仍需导出检查） |
| 图形 | 实际成品尺寸打开；随机点读密集、稀疏、跨类别三行，能准确写出其 rsID、性状集合和 PP；无裁切/错误行对齐 | 自动审美得分、期刊保证 |

图注至少定义：一行是什么、点是什么、blank 是什么、PP 是什么、候选 SNP 与基因注释的边界。
阴影行只作阅读引导；新增标记须有真实来源。保存源文件哈希与最终导出审阅记录。

## 官方依据与设计借鉴

- [HyPrColoc 官方 vignette](https://jrs95.github.io/hyprcoloc/articles/hyprcoloc.html)：区分性状簇后验与候选 SNP fine-mapping 支持，并展示高簇后验但单 SNP 不确定的情况。
- [ComplexHeatmap UpSet](https://jokergoo.github.io/ComplexHeatmap-reference/book/upset-plot.html)：借鉴离散成员矩阵和同行侧注释；不把集合聚合当作原始簇。
- [ComplexUpset](https://krassowski.github.io/complex-upset/articles/Examples_R.html)：借鉴集合成员和查询高亮；不改变原始 cluster ID 与成员定义。

该合同是路由器的专题交接要求，实际静态渲染继续交给现有科研绘图库。
