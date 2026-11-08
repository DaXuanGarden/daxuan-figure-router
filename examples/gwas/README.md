# GWAS figure recipe dry-run

本示例演示如何将已经验收的 GWAS 结果交给 `gwas-figure` 的图形单元，再交由 router
比较不同表达方式。文件中的数值全部为合成值，不能用于真实研究结论。

## 可比较的候选

同一份 `accepted-results.csv` 可生成三组候选：

1. `global-forest`：LDSC/GNOVA/HDL 的遗传相关性和 95% CI；
2. `shared-pair-matrix`：trait pair × locus 的 PLACO+、PP.H4 与 annotation evidence；
3. `shared-circular`：LST → CVD → locus → gene 的概览图。

这三个候选回答不同问题，不能只通过换颜色制造“新图”。regional plot 适合作为补充
材料的第四类候选，但应输入同一位点的两个完整 summary-statistics 区域表。

## 合成输入

`accepted-results.csv` 至少包含：

```text
trait_a,trait_b,stage,method,estimate,ci_low,ci_high,p,
chr,bp,snp,placo_p,pp_h4,gene,annotation_source
```

实际项目中请拆成按图形单元的 tidy 表，避免把估计值表和位点表混成一个分析表；这里合并
仅用于路由和 schema 演练。

## FigureBrief

`figure-brief.json` 固定了 GRCh37、European ancestry、PLACO+ 与 coloc 的阈值、clumping
参数和 ANNOVAR 注释边界。真实项目应将 `source_tables` 替换为稳定的绝对路径或项目相对路径，
并保存输入快照的 SHA-256。

## 执行边界

本示例不调用 R/Python 绘图后端，不安装第三方包，也不重跑 GWAS 或 colocalization。它
只展示 router 如何选择图形单元和比较候选；真实渲染时需先阅读目标技能的 `SKILL.md`、
recipe README 和具体模板，再按项目 runtime 进行 schema 检查和视觉审阅。
