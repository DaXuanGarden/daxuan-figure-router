---
name: daxuan-figure-router
description: 为科研绘图和改图选择、协调本机已安装的技能。当不知道该用哪个绘图 skill、需要选图型、改已有图、处理领域图或组合多个绘图能力时使用；保留用户指定技能、现有代码和语言。明确工具的简单修改可直接执行，无需重新选型。
---

# Daxuan Figure Router

作者与维护者：Daxuan（DaXuanGarden）。

把绘图任务交给合适的已有技能，并继续完成用户要求的绘图或修改。只要求推荐时，交付推荐即可。本技能负责选择和交接，实际绘图规则来自选中的技能。

## 先定这次要做什么

从请求和已有文件提取：新图/改图/选图/配色/终检/示意图；科学问题、比较或关系；输入是现有代码、原始观测、已完成结果还是参考图片；源代码语言、用户点名的技能；输出格式或可编辑要求。已知信息直接继承，只追问会影响正确性的缺项。不能仅凭列名推断实验单位、配对关系或不确定性的定义。

优先级：用户明确要求 → 现有项目代码与本次已确认选择 → 领域和图型匹配 → 通用绘图能力 → 可选配色、模板、终检。用户指定技能与语言不兼容时先说明具体冲突，保留能满足硬条件的选择；不要偷偷换语言。

| 当前任务 | 首选处理 | 何时再看别的技能 |
|---|---|---|
| 已有代码，只改颜色、字号、标注、布局或导出 | 直接修改原脚本，保留数据、模型、数值和语言 | 遇到具体问题才读 `ggplot2-pub`（R）、Python 绘图能力或配色/终检技能 |
| 不知道画什么图 | 按科学问题、数据结构和实验单位选表达；R 可优先看 `easyplot`，Python 可优先看 `make-sci-data-figures` | 主技能不能覆盖该图型时再找模板或领域技能；不能仅凭列名推断配对/独立样本 |
| 已知图型的新数据图 | 专题适配明确时选领域技能，否则选一个语言匹配的通用主技能 | 仅为缺少的能力加助手；不要同时加载多个通用全流程主控 |
| GWAS/MAGMA/TWAS/SMR/MR 等已有结果出图 | 先查 `gwas-figure` 的具体 unit/模板和语言 | 总技能支持 R/Python 不代表每个 unit 都支持两者；只绘图不触发全套 GWAS/MR 分析 |
| 多面板、全图组织 | `nature-figure` 或 `easyplot` 之一负责全图；有专题面板再委派该面板 | 保持一个组图负责人、一个已确认样式来源，不让两套主控互相重启流程 |
| 只配色/统一样式 | 保留原绘图者；`daxuan-journal-palette` 或 `sci-color-palettes` 负责当前缺口 | 已有色板就继承；只取色值不重置全图主题；个人风格包仅在用户或项目选用时加入 |
| 只查成图质量/科学影像 | `polish-sci-figures` / `standardize-sci-images` 对应当前对象 | 前者不要求把 R 图改写成 Python；后者的比例尺需要真实校准 |
| 流程、机制、插画、截图重建 | 检索对应示意/重建能力，先核对运行入口与输出格式 | `figure-spec` 本机可能只有说明；生成服务、PPT 重建需另查实际工具，不能凭已安装就声称可用 |

图型、领域和样式分别判断：forest/heatmap/map 是图的形式，不足以认定 GWAS、MR 或其他领域；期刊名与配色只决定样式，不能覆盖输入和分析范围。领域证据来自用户说明或项目文件。

## 找到候选，再读原文

使用本技能 `scripts/skill_index.py` 做只读检索，以下命令中的 `<本技能目录>` 为本文件所在目录；在用户项目目录运行，以发现项目技能：

```text
python <本技能目录>/scripts/skill_index.py search "森林图 forest" --intent create --role primary --language R --limit 4
python <本技能目录>/scripts/skill_index.py show gwas-figure
python <本技能目录>/scripts/skill_index.py search "配色 palette" --intent palette
python <本技能目录>/scripts/skill_index.py vocabulary
python <本技能目录>/scripts/skill_index.py doctor
```

脚本只找候选、核对文件，不替代任务判断，也不执行被选技能。优先提取图型、领域和当前缺口的短关键词；常见中文图词可归一化，但不能假定脚本理解整句请求。`search` 默认返回少量摘要和命中依据，`show` 或 `--details` 展开。先看摘要；只完整读取选中技能的 `SKILL.md` 和它明确要求的 `PORTABLE.md`、unit 配方或模板。候选不能满足条件时再读备选，不把所有绘图技能加载一遍。得分不是正确率，也不能代替语言、输入和输出核验。

检索覆盖用户技能、Agent 技能、当前项目技能和本机插件技能。精读过的能力见 [references/capabilities.json](references/capabilities.json)。带过滤的 `candidates` 使用当前已核验摘要；新装、迁移或源变更后命中的未知能力在有界 `review_candidates` 中等待复读，不能当成已兼容。旧卡片不再证明当前语言或能力。点名技能时先无过滤 `show` 找真实入口，再读原文判断。同名条目或同家族变体按项目上下文选定准确路径；不要仅凭同名套用卡片或互换不同包。

找新数据图的主执行者时可加 `--role primary`；配色、QA等独立任务按其职责检索，不强制这个角色。`--language` 约束本次继续编辑/生成的数据图源代码。取色、QA、PPT重建或参考检索使用对应 `--intent`，不把源图的R/Python语言强加给这些助手。SVG/PPTX是输出形式，不能当执行后端。`--domain`/`--tag` 使用 `vocabulary` 给出的词；`generic`→`general`、`clinical`→`medical` 会明确归一化。未提供检索词时，未知候选只显示待核验数量；补充具体词后再检索，不按名字任意推荐。

没有命中时，先看过滤诊断与待核验候选，核对扫描根和合法词值，再用图型英文、领域词、已知包/函数名或技能名做一次扩展检索。按需无过滤复检；卡片遗漏不等于原技能没有能力。仍无合适能力则明确缺口，可用现有绘图库直接完成，不编造 skill/API。安装缺失技能走下述明确的 bootstrap 流程。

## 选到技能后，核对具体入口

读取当前 unit/模板/函数，确认路径、后端、必需输入、是否拟合或检验、来源与输出。部分高频入口记录在卡片的 `entry_points`；存在性与内容hash只提供导航证据，依赖和实际运行仍需检查。不要给整套技能或每个unit统一贴一个语言标签。

把输入区分为原始观测、已完成结果、现有代码或图片。用户只要绘图/改图时，选渲染已有结果的入口；`analysis_effect` 为 `refit_or_test` 或 `unknown` 的模板先精读确认，不能直接运行来重做分析。历史文章adapter只有在数据与来源合同匹配时才可执行，否则只作参考。模板中的默认P/FDR列、阈值、过滤和分组必须与本次已确认表达一致。

### GWAS 图形的 FigureBrief 与 recipe

已完成 GWAS/post-GWAS 结果进入比较流程前，可用本技能提供的
`scripts/figure_brief.py` 校验项目级 `FigureBrief`。它记录研究问题、结果来源、
图形候选、证据边界和输出要求；校验器只检查结构和路径标签，不计算统计量，
也不会执行绘图代码。GWAS 图形的最小输入字段和“只显示、不重跑上游分析”的边界
见 [GWAS figure recipes](references/gwas-figure-recipes.json)。

```text
python <本技能目录>/scripts/figure_brief.py validate --brief path/to/brief.json
python <本技能目录>/scripts/figure_brief.py validate --brief path/to/brief.json --check-paths
python <本技能目录>/scripts/figure_brief.py list-recipes
```

当 `FigureBrief.data_status` 为 `accepted-results` 时，路由器应选择能读取已验收结果
的 renderer；`--check-paths` 仅在项目本地审计时使用。项目级 brief 可用
`project_root` 指定稳定的项目根目录，避免把 brief 所在的结果目录误当作路径根。recipe 的
`analysis_effect` 固定为 `none`，因此不能以画图为理由重新运行 LDSC、PLACO+、coloc、
MR 或基因分析。ANNOVAR 候选映射、MAGMA 结果和因果结论必须在 FigureBrief 中分开描述。

例如：已有HR/CI表想借Lancet样式，不能直接运行会从生存数据拟合Cox的模板；MAGMA使用R时，应继续找通用R模板，不能因历史adapter标Python就换语言。样式参考与实际执行可以由不同能力承担。

### 有边界的灵感与自进化

当作者希望“参考更多论文图、比较多种表达，并逐渐形成自己的审美”时，使用
`scripts/evolution.py` 建立独立的 Figure evolution memory。它只追加记录四类事件：
参考图、作者选择、失败原因和待审阅的规则提议。它不下载参考素材，不改写 Skill 或
绘图脚本，不改变统计结果，也不自动推送 GitHub。

```text
python <本技能目录>/scripts/evolution.py init --memory ./figure-memory
python <本技能目录>/scripts/evolution.py add-reference --memory ./figure-memory \
  --id circular-01 --title "Trait-locus-gene circular figure" \
  --kind reference-image --source-url https://example.org/figure \
  --tag circular --tag trait-locus-gene
python <本技能目录>/scripts/evolution.py record-choice --memory ./figure-memory \
  --variant-id circular-gene --reason "层级关系更容易追踪" \
  --prefer compact-legend --avoid dense-labels
python <本技能目录>/scripts/evolution.py record-failure --memory ./figure-memory \
  --area legend --reason "双栏尺寸下图例裁切" \
  --action "采用图下独立图例带" \
  --tag crop
python <本技能目录>/scripts/evolution.py gallery --memory ./figure-memory \
  --out ./figure-memory/gallery.html
python <本技能目录>/scripts/evolution.py check --memory ./figure-memory
```

参考图的 `claim_scope` 默认是 `style-only`；它不能提供数据、阈值、因果关系或基因注释
证据。候选图仍需经过 `comparison.py select`，然后再记录 `record-choice`。重复失败只能
形成 `propose-rule` 待审阅事件；只有作者明确确认、维护者修改代码并通过测试后，规则才
能进入下一版。若使用 `agent-figure-gallery`，导出的选择只作为参考证据，仍需人工审阅
后写入 memory；图库预览不能当作可执行模板。FigureBrief 的 `evolution_policy` 必须保留
`automatic_skill_self_edit: false`、`automatic_github_push: false` 和
`human_confirmation_required: true`。

## 决策后直接交接

通常选择一个主执行技能；按当前缺口加入助手。已有脚本足以完成小修改时，执行目标就是原代码，允许没有额外主技能；只配色或QA时，对应助手可承担这次主任务。向用户用一两句说明“沿用什么/选谁、负责什么、为什么”，然后继续任务，勿把路由建议当成绘图任务的终点。用户要求选方案或缺少关键数据时才停在相应节点。

向所选技能传入：科学问题、已有数据/脚本、语言、已确认图型和样式、输出要求、它负责的范围。它们是上下文，不是假定各技能都接受同一种 JSON 参数。继承已回答问题与已有授权；不能重复开启选型访谈，也不能因子技能的默认流程扩展任务。

内部保留精简依据：任务/输入状态 → 原代码或准确技能路径及入口 → 语言与结果边界 → 助手职责 → 下一步。只在需要审阅或评测时展开记录，不强制用户填写表格。记录格式和验证方法见 [references/routing-records.md](references/routing-records.md)。

发生冲突时，以用户要求和项目约定裁决，使用原生后端配置适配。`sci-color-palettes` 与主技能的编码/主题默认可能不同；先确定需要的颜色、形状、线型，再应用。不要混用多个风格包的全局主题。用户要求全矢量/可编辑时，排除把整个数据面板栅格化的组图方式。

以下情况要改变选择，而不是硬套：必需模板缺失、运行工具未暴露、语言不兼容、输出形式不符、外部服务尚不可用。文件存在仅表示资源存在，依赖和实际运行仍需按所选技能检查。

特别注意：`StatsVisual-Skill-Extension` 用于维护/扩展模板，不是常规画图主技能；`r-topjournal-plotting` 的缺失资产不应被当成现成模板；`agent-figure-gallery` 是参考检索，预览可见不代表源代码可运行。不要让被选技能再递归调用本路由器。

绘图后沿用主技能的验证要求，检查实际输出；只有路由/检索被测过时，只报告路由验证，不声称完成了科研图的真实渲染验证。


## 同事安装与缺失技能

检索、doctor、依赖 `plan`/`status` 保持只读。用户明确要求安装/初始化某个 profile 或缺失技能时，可执行本技能 `scripts/skill_bundle.py install --profile python_starter`（R 可用 `r_starter`），已有匹配身份的技能自动跳过。未明确请求下载时，先报告当前任务的缺项；不要为扩大覆盖而擅自装全部技能。

先看 `plan`，只用 [skill-sources.json](references/skill-sources.json) 中固定公开来源；不能把同名或相似的公开包替换成本机定制技能。安装器不覆盖已有目录，不执行下载代码，不安装 Python/R/服务依赖。新装版本继续由检索器列为待复读，读实际 SKILL 和入口后再路由。完整安装命令、来源状态和运行时边界见 [skill-bootstrap.md](references/skill-bootstrap.md)。
