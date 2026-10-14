# 解析器实测记录（2026-10，本机 Windows / RTX 4070 Laptop 8 GB / 32 逻辑核）

本文件是**本机实测**，不是网上评分。目的是让后续项目知道"哪个工具在这台机器上真的能用、代价多少、错在哪"。源页取自《2027 数据结构考研复习指导》第 230 页（Dijkstra 表格 + 公式 + 图），是典型的"表格 + 行内公式 + 中文正文"混合页。

## 1. 测试条件

- 输入：图片型扫描 PDF（该页 `text_chars=0`，整页一张位图），2× 渲染后裁页。
- 机器：同一台，未开 GPU 加速（Paddle 走 CPU；MinerU 走自带 llama.cpp/ONNX）。
- 判据：**同页对照**——同一页让不同工具各跑一遍，看差异；不比"谁分高"。

## 2. 结果

| 工具 | 单页耗时 | 产物 | 关键观察 |
|---|---|---|---|
| **MinerU**（现有默认） | **约 7 秒/页**（6 页 0.7 分钟） | Markdown，109K 字符 | 5 个 Markdown 表格、226 个行内公式、14 个行间公式；表格以 **base64 图片**混入（3 处），正文与公式质量好 |
| **PaddleOCR PP-StructureV3**（server 模型） | **约 40 分钟/页**（CPU） | JSON：82 版面块、155 行文本、1 表、66 公式 | 表格输出为 **HTML + 内嵌 LaTeX**（可直接转 LaTeX 表）；公式单独成列；质量高 |
| **PaddleOCR PP-StructureV3**（mobile 模型） | **约 11 分钟/页**（CPU） | 同上：162 行、1 表、66 公式 | 速度约 3.6×，质量基本持平；表格 HTML 更完整（806 vs 798 字符） |
| **Pix2Text**（MFD 公式检测 + 识别） | **约 17 秒/张裁图** | 文本 + `$...$` 公式 | 中文正文转写可用，公式用 `$O(|V|^2)$` 形式；整页中文识别有明显错字（见下） |

## 3. 关键差异（这才是多源比对的用处）

**同一页同一张表，两家读出了不同的值：**

- 表 6.2 第 3 行第 1 轮，**原书真值是 5**；PaddleOCR 的 `pred_html` 读成 `8`，MinerU 的 Markdown 表读对。
- 说明"表格里的小号数字"是两家的共同薄弱点，但**错误位置不同**——这正是"两个工具各跑一遍再比对"的价值：不一致处自动成为人工核对点。

**各家的失败模式不同：**

- MinerU：把表格渲染成 base64 图片塞进 Markdown（不方便直接转 LaTeX 表），需要额外取结构化输出。
- PaddleOCR：公式识别偶发插空格，例如 `\operatorname{d i s t}[4]=7`（应为 `\mathrm{dist}`）；表格值偶发错读。
- Pix2Text：整页中文正文有明显错字（"石改用市权邻按衣"这类），**不能用于正文**；但公式本身识别正确，证明它应该**只用于窄裁公式区域**，与本技能文档里的定位一致。

## 4. 结论

1. **MinerU 仍是默认主力**：速度快两个数量级（7 秒 vs 11 分钟/页），正文与公式可用。
2. **PaddleOCR 值得作为"表格与公式的第二意见"**，但要接受 CPU 上的代价：要么慢（server 模型），要么用 mobile 模型换速度。它最大的独有价值是**表格直接给 HTML + LaTeX**。
3. **Pix2Text 只用在裁好的公式小图上**，不要拿它读整页中文。
4. **不要指望单一工具全对**：本次实测直接抓到两家在同一单元格上的分歧，这就是必须逐页视觉复核的实证理由。

## 5. 环境备注（踩过的坑）

- PaddleOCR 需要额外依赖：只装 `paddleocr` 不够，`PP-StructureV3` 会报缺依赖，要装 `paddlex[ocr]==<对应版本>`。
- 本机 `paddlepaddle 3.3.1` 在默认 MKLDNN/oneDNN 路径上抛 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute`；必须在构建 pipeline 时传 `enable_mkldnn=False`（该参数由 `parse_common_args` 白名单接受，`enable_new_ir` 等不在白名单里，传了会报 Unknown argument）。
- `paddleocr` CLI 只暴露 `doc2md` 与 **`api`（云端）**；**本地解析必须走 Python API**（`PPStructureV3` / `PaddleOCRVL`），不要用 `api` 子命令。
- Pix2Text 会被传递依赖 `rapidocr`，其 3.10 版移除了 `cnstd` 需要的 `resolve_model_key`；**必须钉 `rapidocr==3.9.2`**，否则 `import pix2text` 直接失败。
- 本机可达性：`huggingface.co` 不通，`hf-mirror.com` 与 `www.modelscope.cn` 通。Pix2Text 的模型走镜像，PaddleOCR 的模型走官方源，均实测能下载。
