# 同事安装与依赖来源

分享本仓库即可分享路由规则、检索器、多方案管理器和来源锁表。第三方 Skill 文件依其各自许可证下载，不打包成路由器的原创代码。标准 Skill 安装器不会执行任意依赖 hook；因此采用明确的一次 bootstrap，然后按任务补齐的机制。

## 安装流程

```bash
git clone https://github.com/DaXuanGarden/daxuan-figure-router.git "${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
ROUTER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/daxuan-figure-router"
python "$ROUTER_SKILL/scripts/skill_bundle.py" plan --profile python_starter
python "$ROUTER_SKILL/scripts/skill_bundle.py" install --profile python_starter
```

需要 R 时改用 `r_starter`。`minimal` 和无参数默认 profile 只保留路由器，不下载额外技能。`all_public` 是所有已核实公开来源的可选集合，不是推荐的新手默认项。可以 `--skill easyplot` 精确补齐，而不安装整个集合。

已有路由器时，先识别目录是 git 克隆还是独立副本；不要重复 clone/覆盖。独立副本可安装到另一个明确目录核验后再更新。已有第三方技能通过真实 `SKILL.md` 的 name 识别，不单靠文件夹名；匹配到任一扫描根会跳过且不升级。已有版本的哈希不同只表示需要复读其入口，不能因此重装覆盖。

在 Codex 中也可明确请求：

> 用 $daxuan-figure-router 为我安装 python_starter 的缺失绘图技能，已有的跳过，然后检查这份数据的绘图入口。

该请求授权本次 allowlist 内的技能文件安装；代理先读取 plan 诊断再继续。用户只让检索/画图，并不等于授权下载任意新技能。已明确要求安装的任务无需逐项重复询问。

## 安装器的行为

`plan`、`status` 不联网、不创建目录。`install` 才从 `skill-sources.json` 的 GitHub 仓库固定 commit 取完整技能目录，验证 name、SKILL SHA-256 和文件内容，保留许可证与声明文件，暂存完整后发布新目录。来源锁表不接受浮动 main/标签、臆测 URL 或同名替代。

```bash
python "$ROUTER_SKILL/scripts/skill_bundle.py" status --profile python_starter
python "$ROUTER_SKILL/scripts/skill_bundle.py" install --skill sci-color-palettes --target /tmp/my-figure-skills --scan-root /tmp/my-figure-skills
```

默认发现 Codex、Agent、最近项目和插件技能；自定义 `--scan-root` 可隔离演练。目标目录始终检查，存在冲突则报告，不替换。依赖通过锁表 `requires` 解析。重复安装已满足的集合不再联网或改写文件。下载失败、目标冲突和不可获取来源均有明确状态与非零退出码；不会把半套暂存当作已安装。

## 来源与运行时是两件事

`verified_public` 表示固定公开来源、身份、文件哈希与许可证得到核验；不是实际绘图能力已验证。`system` 使用宿主提供的技能；`unavailable` 保留不能自动获取的原因。本机定制版本与公开版本的不同在 `local_contract_review_required` 中明示；路由器对新路径继续给出待复读状态。

锁表覆盖当前全部 39 张能力卡，也可包含明确命名的可选新身份。不能把公开的 `scientific-visualization` 当成本机定制的 `auto-inspire-scientific-visualization`。没有核实来源、没有许可证、身份不匹配的项不自动下载；已有本机副本仍可发现并按原文使用。

安装器不执行第三方脚本、不安装 Python/R/系统包，不配置 API key、字体或服务。每行 `runtime_requirements` 给出这些独立要求。`agent-figure-gallery` 等 wrapper 安装成功仍需外部应用；`figure-spec` 文件存在也不保证实际渲染器存在。需要绘图时再按选中 Skill 原文核对真实入口与环境。

固定源的第三方许可证位于原目录或 `.skill-bundle/repository/`，安装回执位于 `.skill-bundle/receipt.json`。回执记录来源和文件哈希，用于追溯，不是完整软件供应链签名或运行时认证。更新第三方版本应另行审阅来源锁表，不在 bootstrap 中暗中升级。
