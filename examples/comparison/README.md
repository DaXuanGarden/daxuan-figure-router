# 真实多方案示例

输入 [accepted-results.csv](accepted-results.csv) 是五行**模拟的已接受结果**。调用已有 `make-sci-data-figures` 的 forest 入口和 `sci-color-palettes` 的真实取色函数，生成 **2 种森林图表达 × 2 套样式 = 4 张真实图**。这证明一个绘图主技能与一个配色助手协作，不代表运行了四种独立后端。

Glacier 保留白底圆点；Burgundy 使用暖色、方点和浅行引导。所有版本固定数值/CI、行顺序、线性坐标范围、参考值、画布和绘图区几何。示例适配器在导出前观测实际 Matplotlib artists，验证数值/区间/类别配色和坐标范围，再由第三方原有保存函数导出 PNG/SVG/PDF；不修改第三方代码，不拟合模型。

## 从公开源重现

在仓库根目录执行，使用全新项目环境与隔离技能目录：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r examples/comparison/requirements.txt
python3 scripts/skill_bundle.py install --skill make-sci-data-figures --skill sci-color-palettes --target ./local-reports/demo-skills --scan-root ./local-reports/demo-skills
.venv/bin/python examples/comparison/render_demo.py --skills-root ./local-reports/demo-skills --outdir ./local-reports/comparison-demo
python3 scripts/comparison.py check --run ./local-reports/comparison-demo/run
```

先读安装后的 SKILL 及森林图具体入口。示例要求锁表中的固定公开版本和安装回执；本机同名定制版本需要另行审阅/适配，不能直接替换来源证据。脚本不安装包或访问网络，实际 runtime 依赖见 [requirements.txt](requirements.txt)。字体用 Matplotlib 通常提供的 DejaVu Sans；缺失时明确失败，不悄悄换字体。

打开 `local-reports/comparison-demo/run/gallery.html` 看真实全尺寸图、原生导出及证据。可在浏览器导出选择请求，再由 CLI 验证：

```bash
python3 scripts/comparison.py select --run ./local-reports/comparison-demo/run --id intervals-glacier --reason "作者选择：正文中优先突出区间"
python3 scripts/comparison.py check --run ./local-reports/comparison-demo/run
```

全部候选仍保留。生成器不猜测作者偏好，默认没有选中项。`qa: unreviewed` 如实表示数值观测通过而尚未完成视觉及投稿终检；不能将生成成功误作科学或审美认证。实际运行的展示与人工检查记录见 [showcase](../../showcase/README.md)。
