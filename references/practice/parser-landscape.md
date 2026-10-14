# 解析器选型：同类工具对比

本文件回答"除了 MinerU 还有什么、什么时候该换"。**使用任何工具前都必须先拿到用户的 OCR 授权**（见 [decision-gates.md](../governance/decision-gates.md) 第 1.5 节）。

## 1. 一条决定性约束：先看网络能不能下载到模型

模型权重决定工具能不能真正跑起来，而下载源常常是瓶颈。**开工前先实测**，不要看文档假设：

```powershell
# 三个源分别能不能连（中国大陆网络下这是最常见的头号阻塞）
python -X utf8 -c "import socket;[print(h, end=' ') or socket.create_connection((h,443),timeout=5).close() or print('OK') for h in ('huggingface.co','hf-mirror.com','www.modelscope.cn')]"
```

实测结论（本机，2026-10）：**`huggingface.co` 不可达，`hf-mirror.com` 与 `www.modelscope.cn` 可达。** 这条直接改变了推荐排序——默认走 HuggingFace 的模型（Docling 的部分权重、olmOCR、Chandra 权重）会卡在下载，而模型托管在 ModelScope / 镜像上的工具（MinerU、PaddleOCR 系、Pix2Text）反而顺畅。

`MINERU_MODEL_SOURCE` 对应的三个取值正是这个原因：`huggingface` / `modelscope` / `local`。

## 2. 四类工具，各解决不同问题

不要把它们当成互相替代的"另一个 MinerU"。真实价值来自**错误不相关**：同一页让两条不同技术路线的实现各跑一遍，差异处就是该人工核对的地方。

| 类别 | 代表 | 真正的用处 |
|---|---|---|
| 端到端文档解析 | **MinerU**、MonkeyOCR | 一份 PDF → 正文/公式/表格/阅读顺序候选；本技能默认路线 |
| VLM 型整页识别 | **PaddleOCR-VL**、dots.mocr、Chandra、olmOCR、DeepSeek-OCR | 版面复杂、手写、扫描质量差时的**第二意见**；错误模式与 MinerU 不同 |
| 版面/结构专用 | **Surya**、PP-StructureV3、Docling | 页块边界、阅读顺序、表格结构；可反哺 `crop_page.py --region` 的取块位置 |
| 公式专用 | **Pix2Text（含 MFDetection）**、pix2tex | 窄裁公式区域的 LaTeX 候选；只处理小图，不接整页 |

## 3. 候选清单（按"是否值得加"排序）

### 值得优先考虑的四个

| 工具 | 体量 | 许可证 | 页范围参数 | 中文 | 主要卖点 / 代价 |
|---|---|---|---|---|---|
| **MinerU**（现有默认） | 0.8–2.3 GB | 自定义（基于 Apache-2.0） | `--pages`（1-based） | 好 | 已集成、无状态 `mineru-kit`、CPU 可跑。基线 |
| **PaddleOCR-VL** | **约 1.9 GB（0.9B）** | **Apache-2.0**（代码与权重） | **无**——须先切小 PDF | **原生最强** | 最小体量 + 中文原生 + `--device cpu`。缺点：无页范围参数 |
| **Chandra OCR 2** | 约 10.6 GB | 代码 Apache-2.0 / **权重改版 OpenRAIL-M** | **有** `--page-range` | 自带中数示例 | 唯一自带页范围参数的高分 VLM；`--method hf` 可纯本地。代价：权重许可有商业限制、默认 vllm 需起服务 |
| **Pix2Text** | 小（ONNX、CPU 友好） | MIT | 不适用（吃小图） | 好 | **唯一天然带"公式检测"（MFD）** 的组件，正好补本技能的窄裁公式通道；模型托管在国内源 |

### 有明确位置但收益重叠的

- **Docling**（MIT，pip 装，1-based `--page-range`，本技能运行器**已适配**）：真正的差异化是 TableFormer（另一套表格模型）与 `--show-layout`（输出带边框标注的页面图，可直接喂 `crop_page.py --region`）。中文正文质量偏弱，与 MinerU 重叠较多。
- **Surya**（Apache-2.0 代码 / 改版 OpenRAIL-M 权重）：逐块的 `reading_order`、`bbox`、`polygon`、`label`（含 `Equation`）很有用，但 **Marker 2.x 内部就是 Surya**，两者只需其一；GPU 路径要 Docker。
- **PP-StructureV3**（Apache-2.0）：中文版面 + 表格 + 公式识别，还有**印章识别**（本组里唯一）。无页范围参数，须 pre-split。与 PaddleOCR-VL 同源，不必同时上。
- **MonkeyOCR**（Apache-2.0）：自述在 OmniDocBench 中英文都超过若干大模型，中文声明最激进；但它 `import magic_pdf.*`，本质是 MinerU 血统 + flash-attn，复现风险高。

### 明确不要加

| 工具 | 原因 |
|---|---|
| **GOT-OCR 2.0** | 2025-02 后停更；无 LICENSE 文件，数据是 CC BY-NC；无 PDF/批处理 CLI；要源码编译 flash-attn |
| **DeepSeek-OCR / -2** | 官方安装直接钉 `manylinux1` 的 vLLM wheel + `flash-attn --no-build-isolation`（CUDA 11.8）；Windows 上等同只能走 WSL2；无 CLI |
| **Nanonets-OCR2** | 只是 19 star 的 notebook，无 pip 包、无 CLI，页眉页脚项得分 32.1 极差，权重未声明许可 |
| **olmOCR** | 质量高但**英文优先**（自带过滤器就写 "English pdfs"），找不到任何中文证据；还要 Linux 的 poppler/字体。中文教材不适用 |
| **pdfplumber / PyMuPDF4LLM** | 对**图片型** PDF 基本无用：正文全在页码对象里，`chars=0` → 空输出 |
| **Unstructured / LayoutParser / DocLayout-YOLO / PDF-Extract-Kit** | 分别是被 MinerU 覆盖、2022 年停更、AGPL、已停滞（且 PyPI 上的 `pdf-extract-kit` 有蹭名风险） |
| **GLM-OCR（默认安装）** | `pip install glmocr` **默认把文档发到智谱云**；只有 `glmocr[selfhosted]` 才是本地。属于云端服务，按本技能规则禁止 |

## 4. 组合建议

按"边际收益 / 接入成本"排序，**不必全上**：

1. **只加一个** → 加 **PaddleOCR-VL**：体量最小、许可最干净、中文最强、与 MinerU 错误不相关。代价是要先切小 PDF（`scripts/extract_page_range.py` 已提供）。
2. **需要页范围直读且能接受许可限制** → 加 **Chandra**（`--page-range` 是真的）。
3. **公式密集的教材** → 加 **Pix2Text**，只用于 `--region` 窄裁图。
4. **想少装东西** → Docling 适配器**已经写好**，装个包就能用，顺带得到 `--show-layout` 的区域图。

> 实践建议：先只上 1 个第二意见工具，在 3–8 张代表页上和 MinerU 对跑，**比较差异而不是比较分数**。若差异不能给你新的定位信息，就不要保留第二个工具——多个候选互相污染比单一候选更贵。

## 5. 无页范围参数的工具怎么办

PaddleOCR-VL、PP-StructureV3、MonkeyOCR、dots.mocr 都没有页范围参数，只有文件/目录输入。**不要因此直接喂整本书**——先用本技能的切页脚本：

```powershell
python -X utf8 scripts/extract_page_range.py <project> <source.pdf> --pages 12-14 --output tmp/tool-probes/ppstructurev3/p012-014.pdf
```

它按页对象搬运（不读文字层、不做 OCR），只写 `tmp/`，保持"只处理明确页范围"的候选边界。

## 6. 结论怎么用

选型结论写进 `.reconstruct-scanned-pdf-to-latex/progress.md`：装了哪个、为什么、在哪几页验证过、差异结论是什么。**工具只是候选来源**：任何输出都必须经逐页视觉复核后才能进入 `.tex`，冲突时以源页为准并记进 `reviews/tool-conflicts.md`。
