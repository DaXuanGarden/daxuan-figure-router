# 路由示例

以下展示请求如何分配职责，是路由预期，不是已完成的绘图记录。实际任务还需读取所选技能及用户文件。

| 用户请求 | 合适的安排 |
|---|---|
| 已有 R 森林图，只改字号和两个组的颜色 | 保留原脚本；需要 R 字体/导出指引时读取 `ggplot2-pub`，不重新运行统计或启动全图设计 |
| 12 个受试者前后测，不知道该画什么 | 选一个有科学选图能力的主技能，例如 `easyplot`；保留受试者配对身份，再确定表达 |
| 已完成 MAGMA，明确用 R 画 gene-level Manhattan | 查 `gwas-figure` 的具体 unit 和 R 模板，不因历史 Python adapter 换语言或重跑 MAGMA |
| 只要五个 HEX 与可辨性检查 | 直接让本机可用的配色技能处理，不增加一套通用绘图主控 |
| 指定的技能没有出现在固定清单里 | 无语言/角色过滤地 `show` 查真实入口，读取后判断兼容性；不能用名字相近的技能冒充 |

更多边界见 [test-prompts.json](../test-prompts.json)。

只读查询示例，在用户项目目录运行：

```bash
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/skill_index.py" show easyplot
python "$ROUTER_SKILL/scripts/skill_index.py" search "forest 森林图" --language R --limit 4
python "$ROUTER_SKILL/scripts/skill_index.py" doctor
```

如果只想使用自定义安装目录，传入 `--root /path/to/skills`；此时扫描范围仅为明确给出的根。未登记技能的语言和角色未知，先使用无过滤 `show` 或 `search` 查看。
