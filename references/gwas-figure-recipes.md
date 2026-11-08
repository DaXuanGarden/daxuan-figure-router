# GWAS figure recipes for the router

本文件把 `$daxuan-figure-router` 的比较工作流落到已经验收的 GWAS 结果上。它是路由与
图形合同，不重跑 LDSC、GNOVA、HDL、PLACO+、coloc、MR 或基因注释。实际绘图仍由
`gwas-figure` 的对应 recipe/template（或项目已经验收的 R/Python 脚本）完成。

## 先冻结科学合同

每个候选图都要把下面的信息写入 `FigureBrief` 或等价的 JSON manifest：

```json
{
  "figure_id": "lst-cvd-placo-coloc",
  "scientific_question": "Which LST–CVD pairs have shared pleiotropic loci and colocalized signals?",
  "input_state": "accepted_results",
  "ancestry": "European",
  "genome_build": "GRCh37",
  "source_tables": ["placo_plus_clumped.tsv", "coloc_pairwise_PP.H4_gt_0.7.tsv"],
  "thresholds": {
    "placo_plus_p": 5e-8,
    "coloc_pp_h4": 0.7,
    "clump_r2": 0.001,
    "clump_kb": 10000
  },
  "annotation_sources": ["ANNOVAR nearest/refGene"],
  "causal_claim_allowed": false,
  "display_only_operations": ["label_collision_avoidance", "lead_locus_grouping"]
}
```

`source_tables` 必须给出绝对路径或相对于项目根的稳定路径；输入表中保留原始行数、
P 值和注释证据。`ANNOVAR` 的 variant-to-gene 结果写成 annotation，不得在图例中称为
causal gene。布局去重、lead-locus grouping 和标签避让只能作为 display-only 操作记录。

## 四个高频图形单元

| 单元 | 推荐表达 | 最小输入 | 主要统计边界 | 推荐入口 |
|---|---|---|---|---|
| `global_genetic_correlation` | 按性状类别分面的森林图或方法比较图 | `stage, method, estimate, ci_low, ci_high, p` | 保留 LDSC/GNOVA/HDL 原估计和 CI；不把显著性改成相关大小 | `gwas-figure/recipes/global_genetic_correlation`, `templates/render_global_genetic_correlation_forest.py` |
| `shared_loci` | 线性/圆形 Manhattan，或 trait-pair → SNP/locus → gene 的分层图 | `CHR, BP, P`; 可选 `SNP, trait_pair, gene, shared, PP.H4` | PLACO+、coloc、clump 和注释是不同证据层；物理邻近不等于共享 | `gwas-figure/recipes/shared_loci`, `templates/render_shared_loci_manhattan.R` |
| `gene_level` | gene-level Manhattan、条形图或 trait × gene 矩阵 | `gene, CHR, BP, P/FDR` | 使用 MAGMA/其他基因方法提供的 P/FDR；不从 gene name 反推坐标 | `gwas-figure/recipes/magma_gene_level` |
| `mendelian_randomization` | 方法分层森林图、散点图和敏感性面板 | `exposure, outcome, method, nsnp, estimate, ci_low, ci_high, p` | 方向、工具变量数、clumping 参数和敏感性结果必须保留；图不自动证明因果 | `gwas-figure/recipes/mendelian_randomization` |

### Global genetic correlation

适用于已经整理好的 21 个 LST–CVD 结果。方法列应明确 `LDSC`、`GNOVA`、`HDL`，阶段列
可写 `primary`、`validation` 或项目中已登记的阶段。候选图可以比较：

1. 单一森林图：最适合正文报告每个性状对的估计与 CI；
2. 方法 × trait-pair 热图：最适合展示一致性，但必须固定共同色标并另列方法 P 值；
3. 森林图 + 一致性侧栏：主图保留估计和 CI，侧栏仅标记方法是否通过预先登记阈值。

三者使用同一输入快照和同一行顺序。改变显著性阈值、重新排序或只保留显著性行属于新的
科学合同，不能作为“样式候选”静默发生。

### PLACO+ 与 coloc/shared loci

推荐采用三层证据编码：

- 第一层：完整或经过 clump 的 PLACO+ lead SNP/locus；
- 第二层：同一 locus 的 pairwise coloc `PP.H4`，例如预先登记的 `PP.H4 > 0.7`；
- 第三层：ANNOVAR/MAGMA 等 gene annotation，单独使用颜色、点形或外层标签。

适合比较的候选图：

1. trait-pair × locus 点阵：正文首选，易审阅每个 trait pair 的数量和证据层；
2. circular dendrogram：展示 LST → CVD → SNP/locus → gene 层级，适合概览；
3. regional association small multiples：适合补充材料核验单个位点，显示两条 GWAS、
   lead SNP、LD 和 coloc PP.H4。

圆形树状图不能把所有显著 SNP 直接当作独立位点。应使用已完成的 clump 结果，并在
manifest 中记录 `clump_r2`、`clump_kb`、参考 panel、窗口和 lead 规则。若一个 locus
有多个 trait pair，保留 trait-pair 关系而在显示层合并节点；不能把合并后的节点计数当成
新的独立发现。

### Gene-level

基因图需要同时保留 `gene_source`（例如 MAGMA 或 ANNOVAR）与 `annotation_level`。候选
图可比较 gene-level Manhattan、按性状类别的 dot matrix 和只显示重复基因的 network。后者
适合讲故事，不能替代完整 gene-level 表。没有 MAGMA 结果时，ANNOVAR 基因只能作为近邻
注释，图例要明确这一点。

### Mendelian randomization

森林图适合主文；散点图和 leave-one-out/sensitivity panel 适合补充材料。候选图固定：

- exposure → outcome 方向；
- MR 方法和工具变量数；
- beta/OR、95% CI 和 P；
- SNP 筛选、LD clumping 和多重检验规则。

颜色只编码方法或结果阶段，不编码“因果强度”。标题、图例和 caption 需避免把 MR 估计
写成已经证明的因果关系。

## 候选图比较的固定模板

候选图必须围绕表达差异生成，默认最多 4–6 个：

```text
candidate_id | expression | layout | palette | primary_skill | scientific_question
-------------|------------|--------|---------|---------------|-------------------
pair-matrix  | trait-pair × locus evidence | rectangular | neutral + evidence accent | gwas-figure/shared_loci | 哪些性状对共享证据最集中？
circular     | LST → CVD → locus → gene | circular dendrogram | category + annotation | gwas-figure/shared_loci | 共享架构的整体层级是什么？
regional     | two-GWAS regional evidence | small multiples | one trait pair per panel | gwas-figure/shared_loci | 某个位点是否有一致的区域信号？
forest       | estimate/CI by method | horizontal forest | method-safe | gwas-figure/global_genetic_correlation | 方法估计是否一致？
```

每个候选必须保存真实 PNG 预览、PDF/SVG 原文件、caption、audit TSV、manifest 和 QA。候选
之间共享同一输入快照、数值、坐标范围、阈值、trait 顺序和证据语义。仅换色归入样式变体，
不增加候选数量。

比较结果的 `results.json` 建议记录：

```json
{
  "candidate_id": "circular",
  "primary_skill": "gwas-figure",
  "entry_point": "recipes/shared_loci",
  "input_sha256": "...",
  "rows_in": 162,
  "rows_displayed": 162,
  "rows_excluded": 0,
  "display_only_operations": ["label_collision_avoidance"],
  "qa": {"schema": "pass", "counts": "pass", "visual": "unreviewed"},
  "limitations": ["ANNOVAR annotation is not causal-gene evidence"]
}
```

`visual: unreviewed` 要如实保留，不能因为文件成功导出就标为投稿就绪。选择候选后再
进入 `comparison.py select`，并保留未选择候选作为审阅记录。

## 路由规则

```text
已有 R/Python 图脚本 → 先改原脚本，保持语言和统计结果。
已有验收结果、没有图脚本 → gwas-figure 对应 recipe；再由 easyplot/academic-figure 负责版式或 QA。
需要跨 trait-pair、locus、gene 的整体叙事 → 先选择一个 circular/network 主控，不同时启动多个全图主控。
需要解释具体位点 → shared_loci regional entry；不能用圆图替代区域图。
需要方法比较 → global_genetic_correlation forest/matrix；不重跑上游方法。
```

如果输入缺少 build、祖源、阈值、clump 参数或 annotation 来源，路由状态应为
`review_required`，先补齐合同再绘图。路由器不因为缺少数据而伪造候选结果。
