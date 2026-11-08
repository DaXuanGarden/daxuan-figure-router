# 有边界的灵感与自进化

`daxuan-figure-router` 的 C 版把“自进化”限定为可审计的经验积累，不让技能自行改写代码、统计规则或远程仓库。

## 记录什么

使用 `scripts/evolution.py` 保存四类追加式事件：

- `reference`：论文图、布局或配色参考；只记录结构和风格用途，不把参考图当作用户数据或可复用素材。
- `choice`：作者从候选图中选择了什么，以及喜欢/避免的视觉特征。
- `failure`：渲染失败、图例裁切、标签遮挡、语义混淆等原因和后续修正动作。
- `promotion_request`：由历史证据提出的规则建议；它永远保持 `pending-human-review`，不会自动应用。

事件写入一个 SHA-256 哈希链，追加已有事件不会被覆盖。`check` 会核对链、事件顺序、字段和安全边界。

## 初始化和记录

```bash
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/evolution.py" init \
  --memory ./figure-memory

python "$ROUTER_SKILL/scripts/evolution.py" add-reference \
  --memory ./figure-memory --id sleep-cmd-circular-01 \
  --title "Trait-locus-gene circular dendrogram" \
  --kind reference-image --source-url https://example.org/figure \
  --tag circular --tag trait-locus-gene --notes "只借鉴层级和留白"

python "$ROUTER_SKILL/scripts/evolution.py" record-choice \
  --memory ./figure-memory --variant-id circular-gene \
  --reason "基因重复出现时的连线更容易追踪" \
  --prefer arc-links --prefer compact-legend --avoid dense-labels

python "$ROUTER_SKILL/scripts/evolution.py" record-failure \
  --memory ./figure-memory --area legend \
  --reason "图例在双栏尺寸下被裁切" \
  --action "改为图下独立图例带，并在灰度预览中复核" \
  --tag crop
```

`--source-url` 只保存 HTTPS 来源，不下载内容；`--path` 只保存本地路径标签，使用 `gallery --include-local-previews` 时才尝试显示本地图片。任何参考都默认是 `style-only`，不能推导统计结论。

## 生成图库和提议规则

```bash
python "$ROUTER_SKILL/scripts/evolution.py" gallery \
  --memory ./figure-memory --out ./figure-memory/gallery.html \
  --include-local-previews

python "$ROUTER_SKILL/scripts/evolution.py" propose-rule \
  --memory ./figure-memory \
  --proposal "环形图使用独立图例带" \
  --reason "三个连续候选均出现图例裁切" \
  --evidence failure-000003 --evidence choice-000004

python "$ROUTER_SKILL/scripts/evolution.py" check --memory ./figure-memory
python "$ROUTER_SKILL/scripts/evolution.py" summary --memory ./figure-memory
```

规则提议必须引用现有事件。代理可以汇总提议并交给作者，但不应直接修改 `SKILL.md`、绘图脚本、阈值、色彩语义或 GitHub 内容。作者明确确认后，才由维护者在正常代码审阅流程中实现，并补充测试和变更记录。

## 选择与科学边界

偏好只影响版式、字体、留白、颜色候选和参考图排序；不会改变数据行、统计量、P 值、FDR、PP.H4、clumping、样本量、效应方向或基因注释结论。失败记录也不能自动把一个失败候选标为可用。

