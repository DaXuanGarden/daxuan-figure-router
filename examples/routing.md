# 路由示例

以下展示请求如何分配职责，是路由预期，不是已完成的绘图记录。实际任务还需读取所选技能及用户文件。

| 用户请求 | 合适的安排 |
|---|---|
| 已有 R 森林图，只改字号和两个组的颜色 | 保留原脚本；需要 R 字体/导出指引时读取 `ggplot2-pub`，不重新运行统计或启动全图设计 |
| 12 个受试者前后测，不知道该画什么 | 选一个有科学选图能力的主技能，例如 `easyplot`；保留受试者配对身份，再确定表达 |
| 已完成 MAGMA，明确用 R 画 gene-level Manhattan | 查 `gwas-figure` 的具体 unit 和 R 模板，不因历史 Python adapter 换语言或重跑 MAGMA |
| 已完成 LDSC/GNOVA/HDL，想比较 21 个 trait pairs | 选 `gwas-figure/recipes/global_genetic_correlation`；固定 method、estimate、CI、P 和行顺序，不重新估计遗传相关性 |
| 已完成 PLACO+ 和 coloc，想画共享位点全景 | 选 `gwas-figure/recipes/shared_loci`；先显示 clumped lead loci，再用 PP.H4 和 ANNOVAR 作为独立证据层，不把所有显著 SNP 当作独立发现 |
| 想检查某个位点的两条 GWAS 与 PP.H4 | 用 `shared_loci` 的 regional entry，输入同一窗口的两份 summary statistics；圆形总览图不能替代区域图 |
| 已完成 MR 结果，想画方法比较森林图 | 选 `gwas-figure/recipes/mendelian_randomization`；保留方向、方法、nsnp、CI、P 和敏感性信息，不把布局标签写成因果证明 |
| 已有 HR/CI 和 R 代码，想借 Lancet 样式 | 保留已完成结果和原代码，读取样式参考；不运行会重新拟合 Cox 的原项目模板 |
| 中国各站点按类别上色 | 查 `easyplot` 的真实地图函数、经纬度和依赖；缺 `ggmapcn` 时说明缺项，不能声称已成功成图 |
| 只要五个 HEX 与可辨性检查 | 直接让本机可用的配色技能处理，不增加一套通用绘图主控 |
| 指定的技能没有出现在固定清单里 | 无语言/角色过滤地 `show` 查真实入口，读取后判断兼容性；不能用名字相近的技能冒充 |
| 想把参考图、作者选择和失败原因沉淀成自己的审美 | 为项目初始化 `evolution.py` memory；记录参考与候选选择，规则只进入待人工审阅队列，不自动改 Skill |

更多边界见 [test-prompts.json](../test-prompts.json)。

只读查询示例，在用户项目目录运行：

```bash
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/skill_index.py" show easyplot
python "$ROUTER_SKILL/scripts/skill_index.py" search "forest 森林图" --intent create --role primary --language R --limit 4
python "$ROUTER_SKILL/scripts/skill_index.py" search "配色 palette" --intent palette
python "$ROUTER_SKILL/scripts/skill_index.py" vocabulary
python "$ROUTER_SKILL/scripts/skill_index.py" doctor
python "$ROUTER_SKILL/scripts/evolution.py" summary --memory ./figure-memory
```

如果只想使用自定义安装目录，传入 `--root /path/to/skills`；此时扫描范围仅为明确给出的根。带过滤的未知能力进入 `review_candidates`，需要复读；已核验的明确不兼容项不会混入。用户点名技能时先无过滤 `show` 找准确入口。
