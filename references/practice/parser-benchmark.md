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
| **PaddleOCR PP-StructureV3**（server 模型，**CPU**） | **约 40 分钟/页** | JSON：82 版面块、155 行文本、1 表、66 公式 | 表格输出为 **HTML + 内嵌 LaTeX**（可直接转 LaTeX 表）；公式单独成列；质量高 |
| **PaddleOCR PP-StructureV3**（server 模型，**GPU**） | **约 31 秒/页** | 同上（82/155/66/1） | **比 CPU 快约 77×**；显存峰值约 2.7 GB / 8 GB。表格 HTML 与 CPU 版逐字节一致 |
| **PaddleOCR PP-StructureV3**（mobile 模型） | **约 11 分钟/页**（CPU） | 同上：162 行、1 表、66 公式 | 速度约 3.6×，质量基本持平；表格 HTML 更完整（806 vs 798 字符） |
| **Pix2Text**（MFD 公式检测 + 识别） | **约 17 秒/张裁图** | 文本 + `$...$` 公式 | 中文正文转写可用，公式用 `$O(|V|^2)$` 形式；整页中文识别有明显错字（见下） |

## 3. 关键差异（这才是多源比对的用处）

**同一页同一张表，两家读出了不同的值：**

- 表 6.2「顶点 3 / 第 1 轮」这一格，**原书印的是 `∞`**（已放大原页逐字确认）；PaddleOCR 的 `pred_html` 把它读成 `8`（第 4 行同一列也读成 `8`），而 MinerU 的 Markdown 表读成 `∞`，**是对的**。
- 两点结论：一是两家的**错误位置不同**，这正是"两个工具各跑一遍再比对"的价值——不一致处自动成为人工核对点；二是 `∞`、空单元格这类**非字符符号**是经典陷阱，必须人工核对（本次 MinerU 对、PaddleOCR 错，但反过来也可能发生）。

**各家的失败模式不同：**

- MinerU：把表格渲染成 base64 图片塞进 Markdown（不方便直接转 LaTeX 表），需要额外取结构化输出。
- PaddleOCR：公式识别偶发插空格，例如 `\operatorname{d i s t}[4]=7`（应为 `\mathrm{dist}`）；表格值偶发错读。
- Pix2Text：整页中文正文有明显错字（"石改用市权邻按衣"这类），**不能用于正文**；但公式本身识别正确，证明它应该**只用于窄裁公式区域**，与本技能文档里的定位一致。

## 4. 结论

1. **MinerU 仍是默认主力**：CPU 上即约 7 秒/页，正文与公式可用，且本页表格比 PaddleOCR 更准。
2. **PaddleOCR 上了 GPU 才实用**：31 秒/页（CPU 要 40 分钟，**快约 77×**），显存只要 2.7 GB。它最大的独有价值是**表格直接给 HTML + LaTeX**；适合当"表格/公式第二意见"按页抽查。即便上 GPU 仍比 MinerU 慢约 4×，**整本批跑仍不划算**。
3. **Pix2Text 只用在裁好的公式小图上**，不要拿它读整页中文。
4. **不要指望单一工具全对**：本次实测直接抓到两家在同一单元格上的分歧，这就是必须逐页视觉复核的实证理由。

## 5. 环境备注（踩过的坑）

- PaddleOCR 需要额外依赖：只装 `paddleocr` 不够，`PP-StructureV3` 会报缺依赖，要装 `paddlex[ocr]==<对应版本>`。
- 本机 `paddlepaddle 3.3.1` 在默认 MKLDNN/oneDNN 路径上抛 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute`；必须在构建 pipeline 时传 `enable_mkldnn=False`（该参数由 `parse_common_args` 白名单接受，`enable_new_ir` 等不在白名单里，传了会报 Unknown argument）。
- `paddleocr` CLI 只暴露 `doc2md` 与 **`api`（云端）**；**本地解析必须走 Python API**（`PPStructureV3` / `PaddleOCRVL`），不要用 `api` 子命令。
- Pix2Text 会被传递依赖 `rapidocr`，其 3.10 版移除了 `cnstd` 需要的 `resolve_model_key`；**必须钉 `rapidocr==3.9.2`**，否则 `import pix2text` 直接失败。
- 本机可达性：`huggingface.co` 不通，`hf-mirror.com` 与 `www.modelscope.cn` 通。Pix2Text 的模型走镜像，PaddleOCR 的模型走官方源，均实测能下载。

## 6. GPU 版装法（实测可用：Windows + RTX 4070 Laptop + Python 3.12）

```powershell
python -m venv $env:USERPROFILE\.paddleocr-gpu-venv
& $env:USERPROFILE\.paddleocr-gpu-venv\Scripts\python.exe -m pip install `
    "paddlepaddle-gpu==3.3.1" -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
& $env:USERPROFILE\.paddleocr-gpu-venv\Scripts\python.exe -m pip install paddleocr "paddlex[ocr]==3.7.2"
```

- **不需要预装 CUDA Toolkit**：cu129 wheel 自带 CUDA 12.9 / cuDNN 9 运行时（会拉 `nvidia-*` 依赖，下载约 3.7 GB）。
- 驱动只需够新即可向下兼容：本机驱动 596.08（标称 CUDA 13.2）跑 cu129 运行时正常。
- `paddlepaddle-gpu` 在 PyPI 上只有到 2.6.2 的旧版；当前版本**必须**用上面的官方索引。
- 验证（三条都要过）：

  ```powershell
  & $env:USERPROFILE\.paddleocr-gpu-venv\Scripts\python.exe -c "import paddle; print(paddle.device.is_compiled_with_cuda(), paddle.device.cuda.device_count()); paddle.utils.run_check()"
  ```

- 构建 pipeline 时传 `device="gpu"`；**不要**再传 `enable_mkldnn=False`——那是 CPU 路径的 workaround，GPU 不需要。
- 建议**与 CPU 环境分开放**（两个 venv）：GPU 版会拉一整套 CUDA 运行时，混装容易把原本能用的 CPU 环境弄坏。
