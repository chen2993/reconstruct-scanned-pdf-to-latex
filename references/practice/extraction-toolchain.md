# 可选提取器与证据边界

> **前置条件（阻塞式）**：使用本节任何工具之前，必须先按 [decision-gates.md](../governance/decision-gates.md) 第 1.5 节**询问用户是否允许**，并等用户明确答复。用户没有允许时，本节整节不适用，全部走原生多模态逐页判读。答复与候选范围（A / B1 / B2 / B3）要写进 `progress.md`。

## 1. 定位与推荐用法

用户口中的 “MineU” 通常指 **MinerU**（opendatalab/MinerU，现由 `mineru` 包提供；`magic-pdf` 是已停止维护的旧名，不要调用）。

**获用户允许后的推荐工作方式是"MinerU 出候选 + 原生多模态核对定稿"**：整本教材逐字誊抄既慢又容易走神，先用 MinerU 批量产出正文/公式/表格/阅读顺序候选，人（和模型）只需要核对差异与排版。这是本技能推荐的提速路径；用户选择只走原生多模态（A）时，本节不适用。

先做只读体检，拿到本机真实路径与版本：

```powershell
python <skill>/scripts/setup_mineru.py --status
```

体检会给出下一步该做什么（安装、下载模型，或直接可用）。未安装时的一次性准备：

```powershell
python <skill>/scripts/setup_mineru.py --install           # 需要显式执行；创建独立 venv 并安装
python <skill>/scripts/setup_mineru.py --download-models   # 约 2 GB，全机共用
```

安装位置与模型缓存：MinerU 装在独立虚拟环境（默认 `~/.mineru-venv`），模型默认落在 `~/.mineru/models`。**模型缓存是全机共用的**，所以多本书、多个项目只下载一次；`MINERU_MODEL_SOURCE` 可切换 `huggingface` / `modelscope` / `local`（离线用 `local`）。

解析结果由统一运行器产出，写入 `tmp/tool-probes/`：

```powershell
python -X utf8 scripts/run_optional_extractor.py <project> <source.pdf> --tool mineru --pages 12-14,18 --output tmp/tool-probes/mineru/p012-014-018
```

两个必须记住的参数语义：`mineru parse` **默认只解析前 10 页**，所以 `--pages` 必须显式给出（全书候选用 `--all-pages`）；`--limit` 只限制输出字符数，不是页数上限。

也可以先用 `scripts/probe_optional_tools.py` 检查其余候选工具，记录本机实际可用命令和 Python 包，再决定是否做小样本对照。

候选工具包括：

| 候选 | 适合探查的输出 | 在本技能中的角色 |
|---|---|---|
| MinerU | Markdown、JSON、LaTeX、布局/公式/表格候选 | **首选**：正文/公式/表格/阅读顺序候选，供视觉核对与差异审计 |
| Marker | Markdown、JSON、公式和图片候选 | 阅读顺序与结构候选、局部对照 |
| Docling | 统一文档模型、Markdown/JSON、布局候选 | 页面块、表格和结构候选 |
| Nougat | 偏英文科学文献的结构/公式候选 | 仅实验性对照，不作为中文教材默认工具 |
| Surya | 图片级 OCR/版面/阅读顺序候选 | 只用于定位区域和排序，不承担 PDF 转换或最终正文 |
| PDF-Extract-Kit | 版面、公式和表格区域候选 | 只做 Python 包探针或窄区域实验，不接管正文链路 |
| Pix2Text / Pix2TeX / Texify | 局部公式候选 | 只对窄裁公式区域使用，不处理整页正文 |
| 本技能内置脚本 | PNG、裁剪、预算、页面元数据 | 事实来源和上下文控制 |

这些工具的版本、后端和默认参数会变化；不要把网上介绍或历史命令当作本机契约。每次实测都在项目 `tmp/tool-probes/<tool>/` 留下版本、命令、输入页范围、输出清单和人工结论。

## 2. 硬边界

当前技能处理中文扫描教材，正文、公式、编号、样式和图形语义的**最终事实来源是逐页视觉证据**（原生多模态判读，或人工确认）。解析器是提速工具：它负责把"从零誊抄"变成"对照候选做核对"，但**不得直接生成或覆盖最终 `.tex`**，也不得绕过视觉复核。

外部工具可以做以下事情（默认都以候选证据的形式参与）：

- 批量产出正文、公式、表格、图片与阅读顺序候选，供视觉单元逐项比对；
- 帮助定位 `crop_page.py` 的局部区域，减少大图读入上下文；
- 产生候选公式或结构，供视觉单元逐项比对；
- 对已经完成的页面做差异审计，发现漏项、顺序冲突和疑似长公式；
- 统计工具在代表页上的耗时、显存、失败率和候选质量。

未经视觉复核，不得把工具输出直接当成以下事实：

- 文字、公式、选项顺序、题号、答案或页眉页脚的最终内容；
- 原书是否存在献词、目录、书末页等模块；
- 图形的几何语义、标签、箭头和连线关系；
- 可以直接复制的字体、字号、列宽和分页结果。

工具输出与源页视觉证据冲突时，以源页为准，并在 `reviews/tool-conflicts.md` 记录工具、页标识、冲突字段、最终判断和复核者。

## 3. 统一探针与候选运行器

先检查环境：

```powershell
python -X utf8 scripts/probe_optional_tools.py --output tmp/tool-probes/environment.json
```

如果确实需要对少量代表页做候选对照，使用统一运行器，不要手写一串不可追溯的
shell 命令：

```powershell
python -X utf8 scripts/run_optional_extractor.py <project> <input.pdf> `
  --tool mineru --pages 12-14,18 `
  --output tmp/tool-probes/mineru/p012-014-018
```

运行器有四个硬边界：

1. 页范围从 1 开始，默认必须显式给出 `--pages`；全书运行需要明确的 `--all-pages`；
2. 输出目录必须位于 `tmp/tool-probes/`，源 PDF 只读，`latex/`、`docs/` 和样式卡片不会被写入；
3. stdout/stderr 重定向到日志文件，终端只打印短摘要和 manifest 路径，避免日志本身炸掉上下文；
4. manifest 会标记 `candidate_only=true` 和 `accepted_as_final_source=false`，工具输出必须逐字段与源页视觉证据对照。

运行器默认施加三重输出上限：单个候选文件 32 MiB、候选文件数 256、候选输出总量
128 MiB。可以用 `--max-output-bytes`、`--max-output-files` 和
`--max-output-total-bytes` 调小上限；任一上限触发后仍会留下 manifest，但状态为
`oversize`、退出码非零，不能被当作成功候选。manifest 的 `output_summary` 会同时记录
`max_total_bytes`、`total_bytes_exceeded`、`file_count`、候选文件占用的
`candidate_total_bytes`、日志占用的 `log_bytes` 和 `total_bytes`，不要只看单个文件是否
超限。超大文件明细默认只报告前 64 项，并用 `oversized_file_count` 和
`oversized_report_truncated` 表明是否还有未展开的条目，避免“报告超限”反过来制造
上下文膨胀。

这个限制保护的是候选产物和状态报告，不是把大图压缩后冒充原图；需要读图时仍使用
`crop_page.py` 生成带页号的窄裁图，不要把完整 Markdown、JSON 或大图片直接放进执行
单元上下文。运行器会在进程仍存活时轮询这些上限，提前终止超量候选；总量超限时先
缩小页范围、改用更窄的候选区域或只保留结构摘要，不要把 `oversize` 目录整体上传给模型。

`run_optional_extractor.py` 只支持已经探测到且有页范围参数的候选命令。旧版
**`magic-pdf` 已停止维护**（旧名，命令已并入 `mineru`），不要调用；也不要为了“能跑”而处理整本 PDF。

适配器的入口契约是故意保守的：

- **MinerU**：4.x 有**两个** parse 入口，行为不同，必须分清：
  - `mineru-kit parse` —— **本技能实际使用**的无状态入口，直接把 Markdown/JSON
    写进 `-o` 指定路径，**不需要常驻服务**；
  - `mineru parse` —— 常驻服务客户端，需要先 `mineru server start`；未起服务时
    它会返回 `server_not_running` 而不是解析文件（实测踩过）。

  运行器优先选同目录的 `mineru-kit`，找不到时才回退到 `mineru parse` 并在 manifest
  里记录 `warning`。两者都传 `--pages 12-14`（全书为 `--pages all`）；`mineru parse`
  额外保留 `--limit` 作为候选输出边界（它只限制字符数，不是页数）。旧版 `magic-pdf`
  不作为兼容入口；
- **Marker**：只自动调用 `marker_single`。探针可以记录旧的 `marker` 命令是否存在，
  但运行器不会猜测旧入口的参数；
- **Docling**：运行器使用显式的 `docling convert` 子命令，只接受一个连续的
  1-based 页区间。目录页、公式页和选择题页若不连续，拆成多个小样本运行，
  不把 `1,4,9` 拼成一个未经验证的 `--page-range`；
- **Surya**：只在已经得到的独立页图或窄裁图上做区域、版面和阅读顺序候选。
  它没有接入 PDF 候选运行器；需要使用时先在 `tmp/tool-probes/` 留下命令、输入图
  和版本，再由视觉单元复核坐标，不把候选文字直接吸收为正文；
- **PDF-Extract-Kit**：当前只做包存在性探针，未登记稳定的跨版本 CLI。即使本机装有，
  也只能在局部图片上实验版面或公式候选，不能绕过"候选须经视觉复核"的来源规则；
- **Pix2Text / Pix2TeX / Texify**：当前只做命令和包探针，不接收 PDF 全页输入。
  真要做公式候选，先用 `crop_page.py --region` 产生窄裁图，再由视觉单元决定是否
  手工运行局部公式工具；工具输出须经视觉核对后才能进入正文。

运行器若看见入口存在但无法证明页范围语义，会失败而不是自动回退。这个失败是质量门，
不是安装故障：应改用受支持入口、拆分页范围，或把该工具降级为只读探针。

真实运行还会先执行对应的 `--help` 契约检查，并把检查命令、必需参数、返回码和帮助
文本摘要哈希写入 manifest；`--dry-run` 不执行帮助检查，只生成命令计划。这样“命令
文件存在”不会被误当成“当前版本支持本适配器”。

## 4. 推荐的探查顺序

1. 用内置 `split_pdf.py` 生成独立页图，并完成输入审计；
2. 用 `scripts/probe_optional_tools.py` 检查工具，不读 PDF；
3. 只选 3–8 个代表页做候选解析：目录页、普通正文、公式密集页、选择题页、表格/图形页和疑难页；
4. **优先用 MinerU 做结构候选**（默认路径）；只有它在代表页上明显不适用时，才换 Marker 或 Docling，不要默认三者全部运行；
5. 如果结构工具只能告诉你块边界，再选 Surya 或 PDF-Extract-Kit 做区域定位；不要为了“多一个结果”重复运行同类工具；
6. 对公式密集的窄裁区域可单独用 Pix2Text/Pix2TeX/Texify 做公式候选；整页公式候选同样须经视觉核对后才能进入正文；
7. 工具输出写入 `tmp/tool-probes/`，禁止写入 `latex/`、`docs/class-api.md` 或样式卡片；
8. 调度者把工具结果压缩成“候选区域清单”，再派视觉单元逐页确认；
9. 只把确认后的结论写入样式卡片、类文件和页面源码；
10. 对同一批代表页至少保留一份原生视觉判读与工具候选的差异记录，避免工具错误变成隐性事实。

## 5. 工具选择原则

不要把“能导出 LaTeX”当成唯一指标：

- **MinerU**：**默认首选**。正文、公式、表格和阅读顺序都先取它的候选；先在少量代表页上确认质量，再决定扩大到全书。
- **Marker**：优先作为 Markdown/JSON 结构和阅读顺序的第二意见；长中文教材、复杂图形和跨页对象必须人工复核。
- **Docling**：优先作为统一文档模型和表格结构的候选；它的输出仍是结构提示，不是页面排版事实。
- **Nougat**：更适合科学文献实验，不作为中文教材默认链路；只有当代表页实测明显有帮助时才保留。
- **Surya**：适合先找区域、列顺序和表格/图片候选；不能承担中文正文最终转写、选择题标签或图形几何语义。
- **PDF-Extract-Kit**：适合研究型局部实验；如果没有稳定的当前 CLI 和可回溯输出，就停留在包探针层。
- **Pix2Text/Pix2TeX/Texify**：只处理窄裁公式区域，不能承担中文正文、选择题标签或图形几何语义。

同一批页面最多先选一个结构工具，必要时再加一个公式工具。若第二个工具没有
带来可定位的字段级收益，就停止叠加，避免候选输出互相污染和上下文膨胀。

## 6. 评分维度

不要只看“能否导出 LaTeX”。每个候选工具按下表记录：

| 维度 | 需要记录 |
|---|---|
| 输入适配 | 纯图片 PDF、混合 PDF、旋转页、超大单页、中文竖排 |
| 结构 | 阅读顺序、多栏、标题层级、题目/答案边界、跨页对象 |
| 数学 | 行内/行间、矩阵、长公式、公式编号、上下标和中文夹杂 |
| 选择题 | 选项分组、标签候选、列数、图文选项、跨行选项 |
| 图表 | 图片位置、表格边界、坐标轴、图内文字、矢量/位图提示 |
| 定位 | 是否保留页号、块坐标、输出与原页的可回溯关系 |
| 资源 | CPU/GPU、显存、离线能力、安装复杂度、许可证 |
| 失败模式 | 超时、空输出、错序、乱码、公式崩坏、上下文爆炸 |

“准确率高”不能替代字段级记录；教材重建最重要的是可回溯、可局部复核和失败可见。

## 7. 与大图处理的关系

外部解析器不能成为把整本书一次性塞入模型的理由。对于超大页或复杂页，先用总览确定区域，再用 `crop_page.py --region` 窄裁；工具候选只告诉调度者“哪里值得看”，视觉单元仍按读图预算一次读 1–2 张。若工具输出的是整页 HTML/Markdown，不得原样喂给执行单元；应先压缩成候选区域清单或字段级对照，再交视觉复核。

## 8. 版本与可复现记录

每次启用可选工具都记录：

```text
tool: MinerU | Marker | Docling | Surya | PDF-Extract-Kit | Pix2Text | Pix2TeX | Texify
command: <实际命令>
version: <命令或包版本>
backend: <pipeline/VLM/CPU/GPU 等，如可确认>
pages: <最终页面标识列表>
outputs: <tmp/tool-probes 下的相对路径>
purpose: <定位/候选/差异审计>
accepted: <哪些字段被视觉确认后吸收>
rejected: <哪些字段被视觉证据否定>
```

没有这些记录时，工具输出只能算临时观察，不能成为项目基线或发布证据。

