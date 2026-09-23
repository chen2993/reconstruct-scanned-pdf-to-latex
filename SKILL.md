---
name: reconstruct-scanned-pdf-to-latex
description: 将扫描版或图片型教材 PDF 重建为可编辑、可编译、可交付的 LaTeX 项目。覆盖输入审计、页面分型、页面拆分、方向修正、前置页/正文/后置页命名、样式卡片、多页纸张确认、项目专用 .cls、语义指令与主题、分批逐页转写、多单元并行协作纪律、矢量图与思维导图、原书与例题/习题/全做题本构建、Git 检查点、多轮视觉复核和成品瘦身。只用原生多模态能力读取内容，禁止 OCR 和 PDF 文本提取。不适用于已有文字层 PDF 的普通阅读、编辑或转换任务。
---

# 联系页禁令（硬规则）

- 严禁生成或保留 contact sheet、联系页、拼接页、缩略图蒙太奇或任何把多张页面合成一张图的中间产物。
- 所有方向判断、样式分析、内容转写和复核必须逐页打开独立的 PNG；不得用联系页替代页面检查，也不得要求子任务读取联系页。
- 代表页只能在样式卡片中记录最终页面标识和文件路径，不复制、拼接或嵌入页面图像。
- 发现已有联系页或有人提出生成联系页时，立即删除该产物并暂停当前批次，改为逐页检查后再继续。

# 扫描教材重建 LaTeX

本 skill 把扫描页当作视觉证据，最终产物必须是重新排版的 LaTeX，而不是整页图片的包装。确定性文件操作使用 `scripts/`；
文字、公式、方向、样式和图形语义只能由运行环境的原生多模态能力判断。

面向**中文教材**：正文多为中文，`template/base.cls` 以 `ctexbook` 为基类，字体、行距、标点挤压和页眉页脚都按中文排版处理。
需要其它语言或引擎时，按项目实际情况替换基类与字体方案，但接口契约和审计规则不变。

## 硬性规则

- 只使用运行环境原生多模态能力读取页面内容、判断方向、分析样式和核对结果；
  严禁调用 Tesseract、PaddleOCR、OCRmyPDF、云端 OCR、PDF 文本提取或其他文字识别工具作为内容来源。
- 不修改源 PDF，不导入整页扫描图，不把参考工程的书名、字体、颜色、尺寸、页数或局部版式直接复制到新项目。
- 页面拆分和旋转产生的中间文件只放临时目录，成功命名后清理；不保留中间页面副本、页面映射表或物理页记录。
- 最终页面标识只有 `front-xxx`、`pages-xxx`、`back-xxx` 三类。需要保留视觉证据时使用同名 PNG；
  源码页面使用 `front/`、`pages/`、`back/` 下的 `.tex` 文件。
- 前后置模块按语义类型命名（`cover.tex`、`toc.tex` 等），正文逐页用 `pages-xxx.tex`；**页码式模块名（`front-001.tex`）一律禁止**。命名契约与例外见 [references/contract/class-contract.md](references/contract/class-contract.md)。
- `.cls` 从空白文件按实际原件实现；`template/base.cls` 只是接口参考，不是父类或视觉模板。
- 自定义环境、命令、计数器、标签键与配置 API **只能用英文 ASCII 标识符**（字母、数字、下划线）；不得用中文或连字符。
  中文只能出现在正文、题注、角色显示文本等**值**里；连字符只允许出现在文件名、页面标识、样式卡片 ID、路径与 Git 提交文本中。
  带星号布局环境（`figure*`、`align*`）按既有用法使用，但不得给自定义语义所有者加星号。完整契约见 [references/contract/class-contract.md](references/contract/class-contract.md)。
- 所有显示编号由 `.cls` 计数器产生，逐页源码不得硬编码例题号、习题号、定义号、公式号、图表号或步骤号。
- 目录和 PDF 书签必须由 `.cls` 集中管理：`latex/front/toc.tex` 只调用一次项目提供的 `\bookmaketoc` 自动目录指令，不得手写目录条目、页码或逐页 `\addcontentsline`；
  结构命令负责自动写入目录。
- 前后置模块的书签以**原书实际拥有的模块**为准，不是固定清单：封面、前言、献词、目录、书末页等只要原件里有，就**必须**提取出来并各自成为顶层书签，指向该模块的实际第一页；
  原件没有的模块不得凭空补书签，也不得为了凑齐某种"标准结构"而伪造空内容。
  每个存在的模块都使用项目提供的书签指令（参考 `\bookbookmarkmodule{显示标题}{ascii_key}`，参考接口会先开始新页），不得手写物理页码或复制页面。
  模块是否存在拿不准时（例如原件缺封面、缺献词、或某一页是否属于前言），暂停请人工决定，不能静默省略。
- 每个可见块有且只有一个直接语义所有者。所有者可以按原件语义受控嵌套，例如题目包含答案、答案包含步骤；父级隐藏时子级不得单独出现。普通正文、列表、引文、脚注、公式、表格和媒体也必须落在已登记所有者内。
- 跨页语义对象只使用一组 `\begin{environment}` 与 `\end{environment}`，可以跨越同一 `\bookinput` 连续加载的 `pages-xxx.tex` 文件；
  禁止将同一对象拆成多个公开片段接口。源文件边界不是 TeX 分组，也不应自动插入分页。编号、标签、锚点和标题只在 `\begin` 初始化；终止行为（包括做题本唯一答题区）只在 `\end` 执行。
  可跨页所有者必须登记在 `cross_page_owner_environments`，并以流式、非捕获正文的 LaTeX 环境实现；
  不得用 `\NewEnviron` 或未经 `\bookinput` 跨页编译验证的正文捕获组件实现。
- 需要保留的图必须有可编译矢量源码。照片、连续色调或无法诚实矢量化的内容先暂停并询问用户，不得塞入截图或位图。
- 纸张尺寸、页面分区、语义归属、跨页关系或样式差异无法从证据可靠判断时，立即暂停当前批次并向用户提问；不要用猜测、近似样式或硬编码继续推进。
- 判断原书纸张尺寸时先读书内印刷信息（“开本”、成品尺寸或其他规格），再用多张页面几何交叉验证；印刷信息缺失、模糊、单位不明或与页面几何冲突时暂停请用户确认，不能凭常见开型猜定。
- `cover-facsimile`（与封面内容相同的黑白内封复刻页）和仅含版权/出版/印刷信息的 `publication-info` 页默认不进入重建结果：先读取其纸张证据，再在页面命名阶段显式舍去，不生成最终 PNG、前置模块或正文源码。
  含独有序言、目录或正文的混合页不能整页舍去，须暂停请用户确认。
- 复核只记录最终页面标识、源文件和目标构建；不记录 PDF 物理页号或逐页页码映射。90% 一致只是进入人工审核的门槛，不是自动通过条件。
- 输入审计可以只读检查页数、页面方向、`MediaBox` 集合、资源类型、扫描边框和尺寸漂移；这些信息只用于判断工作策略，不得把 PDF 文字层或提取结果当作内容来源。
- 内容以原书为准，不臆造：不得添加原书没有的图号、编号、题注或参考文字（例如“见图 2.1”），原书没有的必须删除；新增内容只出现在用户明确要求的补充模块里并标为新增。
- **原书明显印错也照录，不要“顺手改对”**。实测有单元把原书 `（或 x = x(x)）`（显系 `x(y)` 之误）擅自改写成 `x(y)`——这属于篡改底本。一律照录原书字符，存疑只在复核记录里写一句"原书印作 X，疑为 Y 之误，已照录"，是否更正由人工决定。
- 全书只交付带语义的可编译源码：不得用整页位图、截图或整页图像包装内容，也不得把成页内容塞进无类型的原始 HTML 或纯文本块；矢量图和数学排版必须可编译、可检索、可继续精修。
- 引用一律来自 LaTeX 交叉引用：`\label`、`\ref`、`\hyperref` 和集中配置的 hyperref，禁止手写跳转字符串、手工 anchor、裸编号或“见第 X 章”式人工编号。
  主题必须覆盖链接颜色：在每种已实现主题（`print`、护眼，以及项目实现的深色等）下，链接、框、表格和页眉页脚都要有清晰对比，深色等暗底主题不得沿用亮蓝链接。
- 书内二维码、公众号、配套广告等非内容元素一律丢弃，不生成占位源码，也不在正文留下占位文字；同时含唯一题目或正文的页面不能整页丢弃。
- 只转写原书印刷内容。**明显是后来在 PDF 上添加的人类批注**（手写笔记、红笔订正、荧光笔、圈画、勾叉、页边批注）不是原书内容：忽略它们，不转写、不建样式、不因它中断该页。
  判断依据是“是否后期叠加”，不是“是否手写”：笔迹与印刷字明显不同、压住印刷文字、颜色溢出、脱离版心网格、或全书只在个别页孤立出现，都指向后期批注。
  反过来，原书自己印出来的内容即使长得像手写（手写体例题、印刷旁注、影印批注、作者手迹）也必须照原样转写，不得误删。批注遮住必须转写的正文，或与印刷内容无法区分时才暂停确认。

## 读取页面的方式

页面内容只能靠运行环境原生多模态能力读，所以“怎么把页面送到模型眼前”本身就是工作流的一部分。扫描页常见 4000×6000 px 量级，远大于读取的舒适尺寸，而图片读取会**按长边等比例缩小**。由此推出唯一一条关键判据：

> **宽度决定清晰度。** 把页面切成更短的横带不会让公式变清楚——横带仍是整幅宽度，照样被缩小；只有把宽度截窄（`--region` 指定列范围）才能看清公式、角标和表格线。

统一用 `scripts/crop_page.py` 取图，不要另写裁剪脚本：

```powershell
# 总览：定位版面分区、栏数、图形位置（不要用它读公式）
python -X utf8 scripts/crop_page.py <project> pages-013 tmp/over.png --overview

# 横带：保留整行版式，顺序读一页的内容
python -X utf8 scripts/crop_page.py <project> pages-013 tmp/b1.png --band 1/3

# 区域：只截公式、表格或图所在的一块，比例基于整页
python -X utf8 scripts/crop_page.py <project> pages-013 tmp/z.png --region 0.08,0.30,0.55,0.45
```

每次调用都会报告输出尺寸、源 dpi 与等效 dpi；提示“会被缩小”时说明这一块仍太宽，需要再截窄。据此决定看什么：

- **先总览、再定位、后精读**。总览（`--overview`）只用来确定“哪一段有公式/表格/图”，随后只截那一块。不要把整页均分成十几条逐条读完——那是把上下文花在空白和已读内容上。
- **按需取块，块数越少越好**。一页通常只需 1–3 块就能覆盖所有需要细看的内容；正文段落用 `body` 级清晰度就够，只有公式、角标、表格线、图形标注才需要更高清晰度。
- **左右留 0.03 / 0.96**。正文常排到版心边沿，把 x 范围收到 0.09 会切掉行首字（实测「与」「所以」「该」「令」被切走），只能重裁、白烧额度。
- **每页读图有硬预算**：默认 6 次（`--overview` 总览不计入）。裁剪即计数，由 `scripts/crop_page.py` 强制；超标会被拒绝并提示停下报告。实测有单元把一页裁成 20 多张，上下文烧光、任务中途崩溃，前面读的全白费——**超预算不是更仔细，是任务失败**。
- **一轮只看少量图**：默认一次 1–2 张，读完再读下一张。需要扫很多页时先用结构化信号缩小范围（页数、`MediaBox`、墨迹密度、日志警告），只打开命中异常的那几页。
- **不靠放大补清晰度**：`--scale` 大于 1 只是插值放大，会同时放大模糊，占更多上下文却不增加信息。低分辨率页图只能回到拆页阶段用更高 DPI 重出。
- **裁图只写 `tmp/`**，脚本会拒绝写入交付树；裁图是临时视觉证据，用完即弃，不得拼成跨页蒙太奇。
- **多单元并行时文件名必须带页号**，例如 `tmp/crops/p013_b1.png`：多个单元共用 `tmp/`，无前缀的公共名会被别的单元覆盖。

### 防止"图读错了"被当成"原书错了"

并行读图与共用文件名会造成**图文错配**：拿到的附件可能是别页的图。这会诱导出完全错误的结论（例如误判"全书页码偏移了 N 页"）。实测已发生。

- 每张裁图**带页号前缀**，避免被并发单元覆盖；
- **一次只读 1–2 张**，不要在同一条消息里并行读多张；
- 拿到图先**核对自身可验证的锚点**：页眉/页码/章节标题是否与本页标识一致；
- 发现不符时，先怀疑**图文错配**，单张重读并换一个新文件名重裁，**不要**先宣布"原书页码偏移"或改动编号；
- 只有在换了文件名、单张重读后**仍然**不一致，才按"原件与预期不符"报告，并附上重裁文件名与看到的页眉文字。

- 每个单元在开工前**先确认自己这条路径有视觉能力**：裁一张图亲自读，若返回"不支持视觉"之类的占位文本，立刻停下并报告（不要派下二级代理代读——实测下级可能被固定在无视觉路径上，同样读不到；图片必须由本单元亲自裁、亲自读）。

## 项目结构

初始化后项目逐步形成：

```text
project/
  .gitattributes  .gitignore  README.MD  build.ps1（从 template 复制后按项目实现）
  .reconstruct-scanned-pdf-to-latex/
    progress.md  page-corrections.json  semantic-audit.json  style-cards.md  reviews/  extracted/
    answer-sentinels.txt（做题本解答隔离证据；无题目教材可为空）
    front-xxx.png  pages-xxx.png  back-xxx.png
  docs/class-api.md
  latex/<project_class>.cls  latex/main.tex
  latex/front/cover.tex  latex/front/toc.tex  latex/back/afterword.tex
  latex/pages/pages-xxx.tex  latex/pages/figures/figure-xxx-yyy.tex
  latex/assets/  （共享矢量资产：题字、蒙版、校徽、装饰）
  scripts/  （初始化时复制的审计与调度脚本，项目自带）
  template/base.cls  template/build.ps1  tmp/  dist/
```

初始化会把技能的 `scripts/` 与 `template/` 复制进项目，因此**项目自带可运行的审计链**：`build.ps1` 按项目根解析 `scripts/audit_toc.py`、`audit_pdf_outline.py`、`audit_provenance.py`，缺一个就无法验收。
项目自己的校验脚本可以并列放在 `scripts/` 下。后续修改技能脚本后，重新复制到项目（或直接用技能的 `<skill>/scripts/`）即可，不要只改一边。

控制目录只保存进度、修正规则、样式卡片和复核结论。阶段 2 至 4 使用的 `extracted/` 是临时工作区，阶段 4 成功后必须清理；
最终只保留同名的 `front-xxx.png`、`pages-xxx.png`、`back-xxx.png`（若用户需要视觉证据）。
页面 PNG 只作为方向、样式、内容和结果比对的逐页视觉证据，不得拼接；最终交付前可以按用户决定清理。
`template/` 中的 `base.cls` 与 `build.ps1` 是参考模板，与 `latex/assets/`（矢量资产）含义不同；
实际项目的 `.cls` 写入 `latex/`，成品的 `build.ps1` 写入项目根目录。

## 阶段总表

各阶段的关键产物与"能否进下一步"的门槛。细节在各阶段正文与对应参考文档中。

**阶段是跨会话的**：一本几百页的书往往一个阶段一个会话，甚至一个阶段分几次续跑。因此每个会开始都要先读落盘的状态文件（`progress.md`、`reviews/`、`dispatch.json`、`style-cards.md`），并按本表核对该阶段的**进入条件**是否真的满足——不要假定上一会话已经做完。

| 阶段 | 关键产物 | 进入下一阶段的条件 |
|---|---|---|
| 1 文件树 | 项目骨架、`progress.md` 输入审计 | 纸型证据已记录；来源不明时已请用户确认 |
| 2 拆页 | `extracted/` 逐页 PNG + 清单 | 页数、像素、DPI、回退原因已核对 |
| 3 修正 | `page-corrections.json` | 已**逐页看过**方向（即使无旋转也要跑一次） |
| 4 命名 | `front-*.png`/`pages-*.png`、模块 `.tex`、`main.tex` | 证据页已显式舍去；临时工作区已清理 |
| 5 样式卡片 | `style-cards.md`、结构地图 | 四步顺序走完（目录→代表页→汇总→扩样）；页面分型完成；用户已确认纸型 |
| 6 样式实现 | `.cls`、`class-api.md`、`semantic-audit.json` | 每个新接口已编译验证；跨页环境已编译验证 |
| 7 样式复核 | `reviews/style.md` | 达 90%、无语义/编号错误、无未关闭缺口；**人工已确认** |
| 8 内容转写 | `pages-xxx.tex`（分批） | 每批：转写 → 复核 → 编译 → 验收；来源页标记齐全 |
| 9 矢量图 | `pages/figures/figure-*.tex` | 每图独立编译通过 |
| 10 图形复核 | `reviews/figures.md` | 达 90%；原书无的图号/引用已删除 |
| 11 全书复核 | `reviews/book.md` | 抽查覆盖所有实际存在的类型；未用审计替代人工 |
| 12 矩阵构建 | `build.ps1`、`dist/` | 所有目标通过编译、outline、成品审计；原子发布 |
| 13 补充 | 新增模块 | 明确标为新增；未虚构原书书目事实 |
| 13.5 瘦身 | README 文件树契约 | `latex/` 只剩 LaTeX 源码；无废弃文件 |
| 14 最终复核 | `reviews/final.md` | 记录命令/页数/纸张/主题/已知差异；**人工已确认** |
| 15 发布与开源（可选） | `.gitignore`、`LICENSE`、`NOTICE.md`、`README`、发布包 | 泄漏审计通过；**是否开源已由人类明确回答** |

## 工作流

按顺序执行以下阶段。公共接口或样式发生变化时，先更新类文件、API、样式卡片和审计配置，再恢复受影响批次。

**交付优先级：先把完整书做出来。** 完整书是主交付物，分类视图与做题本矩阵是可选扩展。用户没有明确要求做题本、或原件本来就没有例题/习题时，不要为矩阵、主题或范围反复调整样式与脚本；先把全书正文转写完、编译通过、复核过，再按用户确认的范围补做题本。用户说“先不急着处理做题本”时立即停手，把精力放回正文。

### 1. 文件树搭建

```powershell
python <skill>/scripts/init_project.py <project> --git
```

脚本创建目录、控制文件、`docs/class-api.md` 和复核表，并把技能的 `scripts/`（含 `semantics/` 包）与 `template/` 复制进项目，使项目自带可运行的工具链。它**不**创建项目 `.cls`，也**不**在项目根生成成品 `build.ps1`——这两者都要按原书实现。检查 `git status --short` 后提交初始化检查点。

Windows 上路径常含中文、空格和全角括号。这类路径不要塞进 `python -c "..."` 或 `-Command` 的单行字符串：引号与代码页会把参数截断或改写（实测会把中文名变成乱码并报“unrecognized arguments”）。稳妥做法是把命令写成脚本文件再执行，或先 `cd` 到项目目录、用相对路径和简短英文文件名传参。

初始化后先做一次只读输入审计，再拆页。判断原书页面大小时，优先检查书内印刷信息，再用页面几何交叉验证：

- 逐页查看封面、版权页、出版/印刷信息页，查找“开本”、成品/裁切尺寸、规格或类似明确标注；先记录原文、单位和证据页处理结论。印刷信息是纸张尺寸的首选候选证据，但不把其他书目信息当作版式事实；
  保留的证据页在阶段 4 后补记最终标识，舍去的证据页不记录物理页号或临时页映射；
- 统计页数、页面方向和 `MediaBox` 的稳定范围，区分稳定尺寸、轻微扫描漂移和明显异常值；不要用单个页面或异常值直接决定原书纸型；
- 检查页面资源是否以整页图像为主、是否存在少量结构异常页，并确认扫描边框、留白、黑边和裁切风险；这些检查只读 PDF 对象和渲染图像，不读取文字层；
- 先列出封面、版权/出版信息证据页、目录、章节首页、普通正文、图表/公式密集页、参考文献/索引和封底等需要检查的类型；
  拆页后逐页打开独立 PNG，再为实际存在且会输出的类型选择代表页，不存在的类型标记为“不适用”；证据页只用于审计，含序言、目录或正文等独有内容的混合页按保留内容处理；
- 将印刷信息与多张页面的 `MediaBox`、渲染图像比例和裁切边界交叉验证；若印刷信息缺失、模糊、单位无法确定，或与页面几何冲突，暂停并请用户确认，不能凭常见开本猜定；
  审计记录只写证据来源、集合、范围和结论，不写物理页映射。

阶段 1 到 4 的结论要**就地写回** `.reconstruct-scanned-pdf-to-latex/progress.md`：源 PDF 标识与 SHA-256、输入审计状态、书内印刷规格、`MediaBox` 范围、资源类型、页面分型、舍去页规则、拆页策略、命名范围都必须在对应阶段完成时填上，并把阶段清单里的复选框勾掉。进度文件是后续单元恢复上下文的唯一入口，留成模板状态等于没有记录。

### 2. 页面拆分

```powershell
python <skill>/scripts/split_pdf.py <project> <source.pdf> --image-source auto --dpi 300
```

若扫描 PDF 每页是完整嵌入页图，优先直接提取原始像素，不统一渲染、不重采样；复杂页才回退到指定 DPI 渲染。这里的“保留原像素”只针对临时视觉证据，避免为方向判断和样式分析额外损坏扫描质量；
它不表示最终 LaTeX 要导入整页图片。后续内容、公式、版式和图形仍必须由原生多模态能力分析后重新写成 LaTeX。脚本只检查图像对象和几何，不读取文字层。
核对页数、像素尺寸、有效 DPI 和回退原因；这些信息只供当前阶段使用，最终不写入交付树。

### 3. 页面修正

按原件顺序逐页打开独立 PNG，逐页检查方向和页边界；不得拼接、缩略或跳过页面。忽略不影响阅读的小倾斜，不自动裁切或重采样：

```powershell
python <skill>/scripts/correct_pages.py <project>
```

在 `page-corrections.json` 只登记 `0/90/180/270` 度旋转。
脚本可以在临时目录原子更新页图，但成功后只把结果交给阶段 4 命名，不制造或保留额外副本、裁切版本或重采样版本。即使没有旋转，也运行一次以完成人工方向检查。

### 4. 页面命名与入口骨架

先根据逐页视觉检查标出要舍去的 `cover-facsimile` 和 `publication-info` 页；这些页只用于输入审计，不参与最终编号。

```powershell
python <skill>/scripts/renumber_pages.py <project> --front 1-6 --front-modules cover=1,dedication=2,toc=3-4,preface=5 --body 7-586 --back 587-590 --back-modules afterword=1-3,references=4
```

使用重编号脚本的 `--discard START-END[,START-END...]` 显式传入临时页序号，脚本会在分配 front/body/back 前过滤它们；
`--front`、`--body`、`--back` 仍引用过滤前的临时页序号，而 `--front-modules`、`--back-modules` 的范围改用过滤后各分区内从 1 开始的连续序号。
成功后临时页和舍去页一并清理。不得手动删除单页后再猜测范围，也不得为舍去页生成占位源码。

将保留页按原件顺序直接命名为 `front-001`、`pages-001`、`back-001`。不生成页面映射或物理页表。

- 前置和后置按语义类型写入 `latex/front/`、`latex/back/`，例如 `cover.tex`、`dedication.tex`、`toc.tex`、`preface.tex`、`afterword.tex`、`references.tex`；
  严禁使用 `front-xxx.tex`、`back-xxx.tex` 或其他页码式文件名，一个类型模块可以自然扩展到多页。
- 正文逐页写入 `latex/pages/pages-001.tex`、`pages-002.tex` 等。
- `main.tex` 是唯一编排入口：在 `\documentclass` 前用 `\providecommand{\BookBuildOptions}{...}` 接收构建 driver 的目标选项，并通过 `\PassOptionsToClass` 交给项目 `.cls`；
  正文和所有前后置目标共用这一入口。
- `main.tex` 对前置和后置使用多条原生 `\input{front/cover}`、`\input{front/toc}`、`\input{back/afterword}`，保留人工可调整的顺序；
  入口中的模块清单保持静态并可被审计，不在条件分支中选择另一套文件。需要按 workbook 改变目录或序言时，在同一模块内使用类文件提供的公共条件命令，不复制第二个入口。
  目录模块只能通过自动目录指令生成内容，不能手工重写页码。
- 项目 `.cls` 必须提供 `\bookinput{起始编号}{结束编号}`，`main.tex` 必须以一条 `\bookinput{1}{N}` 连续导入全部正文 `pages/pages-xxx.tex`；
  不得在 `main.tex` 中逐条 `\input` 正文，也不得为前置和后置增加批量加载器。`\bookinput` 必须按三位编号、按序加载，缺页或范围非法时明确报错，不得静默跳过。

正文逐页文件只记录自己的最终页面标识，例如 `% Source page: pages-023`。
一个前置或后置语义模块可以自然扩展为多页，允许用 `% Source pages:` 列出其覆盖的多个最终标识；仍不记录物理页、拆分批次或中间路径。

### 4.5 协作与并行纪律（跨阶段）

本技能的形态是**一个调度者管多个执行单元**（不是多个调度者并行推同一本书）；不同阶段各开一个会话属于正常做法，阶段之间靠落盘状态交接。

并发只有建立在对齐基线上才可靠。角色边界、任务包要素、图片读取纪律、并发节奏与收敛门见
[references/governance/subagent-orchestration.md](references/governance/subagent-orchestration.md)；批次基线与不可逆操作保护见
[references/governance/collaboration-and-baseline.md](references/governance/collaboration-and-baseline.md)。

调度节奏用 `scripts/orchestrate.py` 固定下来：`plan` 切批 → `next` 生成任务包 → 单元转写 → `verify` 校验 → `checkpoint` 提交检查点 → 再 `next`。
任务包自带样式摘要版本、文件白名单、逐页分型、跨页交接和停工反馈格式；在飞批次数达到并发上限时 `next` 会排队而不是继续派发（`plan --concurrency` 设定上限），`checkpoint` 只提交通过校验的批次。

原始需求、差异清单、发现的问题和结论写进 `progress.md` 和 `reviews/`，不写进页面源码；源码不保留“待提取”“承接上页”“续见 PDF 第 N 页”之类的转写笔记。

### 4.6 能力预检（开工前）

开始转写前必须先确认运行环境具备**原生多模态读取**与**任务分派**两项能力，并把结论写进 `progress.md`。两件事都要分别确认：**我自己**能不能读图，**我要派的子代理**能不能读图。

实测出现过**能力倒置**：主执行者调 `read_image` 返回「不支持视觉」，而派出的子代理能正常读图。此时**所有视觉工作（方向检查、页面分型、样式提取、转写、复核）都必须委托出去**，主执行者只做调度与验收。另外，派出的**下二级**代理可能被固定在无视觉路径上——不要让二级代理代读图片，那只会浪费往返。

**先探针、再派发**：用 `tools/make_vision_probe.py` 生成一张内容已知的合成图（3 圆 / 2 三角 / 4 方 / 左上角 `V7K`），让待测方只回答一行可自动核对的结果；看不到就回「看不到」。这样能区分"看不到"与"看错"两种失败，比直接派真任务便宜得多——实测 528 次派发里有 441 次带探针。

任一层都读不了图时，立即停下来告知用户（缺哪一项、卡在哪一页），请用户切换模型；禁止改用 OCR 或 PDF 文本层替代。判据、探针写法与单元提示词结构见 [subagent-orchestration.md](references/governance/subagent-orchestration.md) 第 0 节与 [dispatch-prompts.md](references/governance/dispatch-prompts.md) 第 0–0.7 节。

### 5. 样式总结与样式卡片

只在 `.reconstruct-scanned-pdf-to-latex/style-cards.md` 记录代表页面标识和源文件路径，不复制页面。代表页必须分别打开独立 PNG 检查；
不得创建联系页、拼接页或缩略图蒙太奇。样式分析时可从多张不同页面共同推断纸张比例、版心、奇偶页和分页规律，但不另建“页面几何摘要”交付文件；这些判断直接落实到项目 `.cls` 并由多页校样验证。
样式卡片本身不得嵌入或复制页面图。
样式卡片要覆盖实际存在的纸张/版心、奇偶页、章首页、各级标题、正文、列表/引文、页眉页脚、脚注/边注、公式、知识块、例题、习题、答案、图表、目录和特殊页，并说明辨识条件、环境/命令、视觉特征、显示视图及源页标识。
用户先确认纸张尺寸；未知时标记待确认，不悄悄猜定。

**样式提取适合并行，但顺序不能颠倒**：先看目录了解页面分布 → 按类型派发代表页并行判读 → 汇总成卡片 → 对存疑类型补充扩样（额外连看前几页）。第 4 步最容易被省掉，而它正是发现"同类型不同变体"的唯一机会。完整流程与派发模板见 [style-extraction.md](references/practice/style-extraction.md)；可直接套用的单元提示词见 [dispatch-prompts.md](references/governance/dispatch-prompts.md)。

先完成页面分型，再补充语义样式卡：封面、版权/出版信息证据页、献词/序言、目录、章节首页、普通正文、图表或公式密集页、参考文献/索引/附录、封底或其他书末页。仅含证据的页面不创建输出样式卡；
含序言、目录或正文等独有内容的混合页按保留内容建卡。教材不一定包含例题或习题；没有对应内容时标记“不适用”，不要为了填满卡片而虚构题目环境或生成空做题本目标。
页面分型只描述可观察的版面类别，不替代 `.cls` 中的语义所有者。

### 6. 样式实现

阅读 [style-cards.md](references/practice/style-cards.md)、[class-contract.md](references/contract/class-contract.md)、
[latex-pitfalls.md](references/practice/latex-pitfalls.md) 和 [template/base.cls](template/base.cls)，
在 `latex/` 从零实现项目 `.cls`，并同步填写 `docs/class-api.md` 与 `semantic-audit.json`。
集中管理纸张、版心、字体、间距、页眉页脚、颜色、环境、计数器、内容视图、题目归属、跨页接口和媒体接口。
每新增一个公共接口，先在 API 文档中锁定输入、输出、错误行为和命名契约，再实现并进行常规编译复核；环境、命令、计数器和标签键先通过英文 ASCII 标识检查。
每个登记为可跨页的环境都要以单条 `\bookinput` 连续加载两个或更多页面的夹具验证单一 `\begin`/`\end`，并在完整书与隐藏视图各编译一次。

需要复刻又反复出现的版式单元（章节横幅、知识框、标题前后距、页眉页脚、题号、表格、链接、目录与思维导图层级）集中在 `.cls` 里做成命名贴合数学内容的语义指令，不按颜色或视觉外观命名，也不要在逐页源码里重复原始排版代码；
同语义内容始终复用同一条指令，避免同类标题在不同章节样式不一致。
按 `docs/class-api.md` 为字体、字号、主题色、链接色、页眉页脚、水印和背景提供集中配置项，并随接口同步维护该文档，方便后续一键调整。

### 7. 样式复核

先冻结完整书的回归基线（源类文件版本、PDF SHA-256、页数、MediaBox、书签和代表页渲染）。对代表页反复执行“编译 -> 渲染 -> 多模态比对 -> 修改”，并确认只影响预期视图；
首章首个正文页、奇偶页页眉标记、跨页对象和隐藏模式必须单独检查。达到 90% 且无语义错误、编号错误、未关闭样式缺口、未分类盒警告后，向用户展示校样并等待人工确认。未确认前不能进入批量内容填充。

细节对齐是迭代循环而非一次通过：逐类列出“原书特征 vs 当前产物”的差异清单（标题对齐与字号、公式行内/行间、页码位置与大小、表格与框线、知识点框、字体与斜体/楷体场景、图注、页眉页脚），逐项修改后重编译再比对，重复多轮直到差异收敛；
表、跨页表格、思维导图等整类问题统一处理，不在单页打补丁。发现的问题清单和收敛过程记入 `reviews/`。

目录与页眉页脚是这一阶段单独收敛的一类：目录的页码字号要统一、页码盒宽要给够、章级条目要有足够左缩进、点引线间距统一、续页带页眉页码且条目可点击跳转；页眉页脚全书几何一致。
实现细节见 [references/practice/pagination-and-navigation.md](references/practice/pagination-and-navigation.md)。

### 8. 内容按页实现

每个并行单元通常负责连续 10 页，内部三轮：原生多模态转写、逐行内容复核、编译与版式复核。
任务必须附当前样式摘要版本、每个可用样式卡片、该批页面分型（例如章节首页、普通正文、图表/公式页）及 `front-xxx`、`pages-xxx` 或 `back-xxx` 源页标识；
不得复制代表页或发明局部样式。模型必须打开本页独立 PNG 读取内容，并同时查看上一页和下一页判断跨页承接关系；不用 OCR、不臆造原书没有的题号、结论或参考文字。
批次边界落在开放的可跨页所有者内时，主执行者向下一单元交接该环境名、起始页面标识、样式卡片版本和嵌套层级；这是瞬时协作上下文，不写入物理页映射，也不得补造新的环境边界。
发现缺样式、样式变体或无法表达的版式，立即在 `reviews/style-gaps.md` 报告并暂停该块；主执行者更新 `.cls` 后，通知所有相关单元重新读取新版本再继续。
图形只登记稳定 ID 和占位，不在本阶段实现。批次按“转写—复核—验收”逐批推进，前一批未经主执行者确认不派下一批。

### 9. 矢量图实现

每个单元一次只实现一张图，写入 `latex/pages/figures/figure-pages-023-001.tex`（`pages` 固定为源页所在分区，`023` 为源页标识，`001` 为本页第几张图；
前后置图用 `figure-front-001-001.tex` 或 `figure-back-001-001.tex`）。
图形模块的文件名可以含连字符，但其中定义的宏名必须只含 ASCII 字母和数字。模块注释记录源页标识、图形 ID 和页面源码；不在图形模块内写题注、编号、页码或位图，文件名里的三位页号只是源码元数据。

页面通过类文件提供的集中接口嵌入图形主体（参考 `\bookfiguremodule{figure-pages-023-001}`），不在页面源码里写 `\input{...}` 路径；
缺失或重复的主体由类文件报错。

先分清图的两类，再选手段，详见 [references/practice/figures-and-assets.md](references/practice/figures-and-assets.md)：结构图（思维导图、知识结构网络图、流程图、框图、数轴、阴影区域、花括号分层）用可编译的 TikZ 重建并保留原书层级；
书法题字、校名、印章、手写签名这类**字形本身即内容**的元素，从原件最高分辨率页描摹成矢量轮廓，保留字形骨架与字距，不要用相近字体代替。资产放独立目录，尺寸/颜色/位置由 `.cls` 宏集中管理；
描摹脚本属于可复现源码，必须保留。

### 10. 矢量图复核

逐图检查结构、标签、公式、连接关系、大小、基线、题注、环绕和分页；独立编译图形后再检查嵌入正文。达到 90% 后仍需人工复核，结果写入 `reviews/figures.md`。
反查正文时核对原书是否真的引用该图：原书没有的图号、题注和“见图 x.y”式引用必须删除，不得由转写补造。

矢量描摹的书法字和标志还要做像素级复核：量原字与矢量外接框的宽高和位置，多轮逼近到 1–2 px 量级。

### 11. 全书复核

运行语义审计，确认每个 `pages-xxx.tex` 恰好被加载一次，并让审计器以完整导入顺序维护全局环境栈；只有显式登记的流式所有者可在文件边界保持开放，普通布局环境仍必须在本文件闭合。
抽查封面、目录、章节边界、普通正文、公式密集页、树/流程/框图/时序图、表格、参考文献/索引、封底或其他书末页、奇偶页、前后置页和批次边界；
出版/印刷信息页只核对已记录的纸张证据，不作为输出页抽样，除非它是含独有内容的混合页。只抽查原件实际存在的类型。记录最终页面标识与成品目标名的对应关系，不能用审计替代人工视觉检查。

页数与原书有明显差异时按 [references/practice/pagination-and-navigation.md](references/practice/pagination-and-navigation.md) 诊断：先建章节锚点定位到章，再用 `scripts/audit_page_density.py` 缩小到少数稀疏候选页，逐页归因（不可分页的语义块、浮动体阈值、环境边界额外垂直胶、行内公式被写成行间公式）后只改机制，不做全局压缩。
空白多的页不等于错误，必须与同印刷页比对；用户已说明不必追求页数一致时，按可读性和分页结构一致性验收。

### 12. 编译测试与做题本矩阵

按 [references/contract/workbook-matrix.md](references/contract/workbook-matrix.md) 和 [template/build.ps1](template/build.ps1) 实现根目录 `build.ps1`。
每个目标生成独立 driver，只定义 `\BookBuildOptions` 并输入同一个 `latex/main.tex`，不得再创建 `main-workbook.tex`。
完整书只构建用户确认的原书尺寸；仅当原件和用户选择都包含相应题型时，才构建例题、习题或全做题本，不为没有题目的教材生成空目标。
题目目标可分别构建 `original`、`a4`、`pad11`、`pad13`，主题集合由用户确认：默认矩阵只固定 `print` 与护眼黄 `eyecare`，不要把额外主题（例如深色）当成默认交付；
项目确实实现了其它主题时，才把它加入用户确认的集合并同步矩阵。主题是整组配色，链接、框、表格和页眉页脚都要随主题走，不是只换页面底色。
若项目 `.cls` 实现了语义小节强制分页，再把 `section_break=false/true` 作为仅做题本的可选轴；普通全书不得注入该参数。完整书中的跨页对象自然流动；
做题本仅在题目、必要媒体和答题区可安全收集且能同页容纳时将其作为一个分页单元，否则明确报错、按项目约定回退或请求人工复核，不能静默缩小内容。Pad11/Pad13 一页一题。
封面、献词、目录和末页在各目标复用同一内容模块，横向纸型只做响应式重排。每个目标独立缓存，至少两遍并在引用/目录收敛后再通过；
编译退出码之外还要用 `scripts/audit_pdf_build.py` 审计所有 PDF 页的存在、页数/MediaBox、空文字页、整页位图包装和做题本答案泄漏，并检查书签/链接与日志收敛、分类处理盒警告。做题本目标必须随构建提供答案哨兵清单（`-AnswerSentinels`），缺清单即构建失败。所有目标通过后才原子发布到 `dist/`。
参考构建脚本的 `matrix` 目标为用户确认的主题集合生成完整书目标（默认 `print`/`eyecare`，项目实现了其它主题时用 `-Themes` 传入完整集合并必须保留 `print`），做题本范围必须通过 `-Scope` 显式传入实际存在的 `examples`、`exercises` 或 `all`；
省略时不生成做题本。单目标 `workbook` 只接受一个范围，不能靠脚本猜测原件是否有题目。
构建验收还必须检查 PDF outline：**原件实际存在的每个前后置模块都要有一条顶层书签**（有献词就必须有献词书签，没有献词就不该出现），并按原件顺序排列、指向非空目标页；目录通过 `\bookmaketoc` 自动生成；
目录页码和书签目标只能由 LaTeX 在收敛构建中计算，不能硬编码。
参考构建脚本先调用 `scripts/audit_toc.py`，强制 `toc.tex` 恰好一次 `\bookmaketoc`、禁止手写目录命令且要求入口恰好导入一次目录模块；
再调用 `scripts/audit_pdf_outline.py` 检查 outline 层级、已登记模块的书签顺序与非空目标页，以及辅助文件。
这些脚本只读取源码、书签层级、目标页、页面渲染和辅助文件，不读取 PDF 正文文字。
前后置模块清单通过 `-RequiredBookmarks` 传入，格式为 `key=显示标题`、按原件顺序排列（例如原件有封面、前言、目录、书末页时传 `cover=封面,preface=前言,toc=目录,backmatter=书末页`）。
  它是**项目自己的模块清单**，不是固定四键：原件有的模块必须登记（漏登记等于漏提取），原件没有的不要登记。
  原件**完全没有前后置模块**（纯正文扫描件）时留空，只做 outline 结构检查，不强制任何模块书签。
  双语或定制显示文本只改等号右侧标题，不改左侧语义键。

### 13. 补充

按用户决定补充编者序、开源声明、版本说明或勘误入口。新增内容必须明确标为新增，不虚构原书书目信息或授权事实。

### 13.5 交付物与瘦身

主执行者在发布前完成：优化文件树，让 `latex/` 只保留 LaTeX 源码（脚本、缓存和产物移出）；删除废弃的旧目录、快照、临时合并目录、未使用宏包与无效代码；删除全部无关文件和中间产物；
在 README 或维护手册记录文件树契约，并随接口变更同步维护 `docs/`、样式卡片、进度与各复核文件。
交付只保留能按一条命令重建成品的最小源码集合，不把某个原书的固定页数、书名或书目事实写进通用脚本。

### 14. 最终复核

重新运行所需矩阵，抽查首尾页、章节、公式、图形、随机页面和三类做题本；更新 `reviews/final.md`，记录命令、页数、纸张尺寸、主题、已知差异和人工结论。
未获人工确认不得称为完成或创建发布标签。

### 15. 发布与开源（可选）

**用户没提出就不要做。** 重建成品是他人著作的衍生，这一步涉及著作权，因此规则与其它阶段不同：**agent 不做权利判断，只准备产物与检查泄漏**。

两条硬规则：

1. **是否开源必须由人类回答**。可以准备产物、可以推送到用户指定的远端，但"仓库是否公开"必须用户明确表态后才执行；不得自行设为 public，也不得自行选择许可证。
2. **扫描件与页图绝不能进入版本控制**。它们是本地 QA 输入，不是项目源码。一旦提交，事后删除仍能从 Git 历史恢复，属于既成事实的再分发。

向用户确认三件事后再动手：发布范围（只发布工具链，还是连同重建正文）、权利状态（含正文时是否已获权利人许可）、可见性（私有 / 公开 / 仅本地提交）。

四件产物与六个检查项见 [release-and-open-source.md](references/governance/release-and-open-source.md)。摘要：

- `.gitignore` 必须在**首次提交之前**就位（重点是 `.reconstruct-scanned-pdf-to-latex/*.png` 与 `/reference/`、`/sources/`）；
- `LICENSE` 必须是**带范围声明**的许可证，不能是裸 MIT —— 它只覆盖项目自有的脚本与基础设施；
- `NOTICE.md` 列出被排除材料（重建正文、插图、版式、扫描、第三方字体）与依赖边界；
- `README.md` 让陌生人能一条命令构建；
- 源码包与发布包**分开打包**（法律地位不同），各带清单与 SHA-256；
- 提交或推送前运行 `scripts/audit_release.py`，确认没有图片/PDF 进入版本控制。

## 参考资料

`references/` 分三层：**契约层**是动手前必须知道的约定，**手法层**是做的时候查的操作规则，**治理层**是协作与验收。按当前阶段取用即可，不必全读。

### 阶段 → 文档

| 阶段 | 该读的文档 |
|---|---|
| 1-4 输入审计、拆页、修正、命名 | [practice/page-reading.md](references/practice/page-reading.md)、[contract/workbook-matrix.md](references/contract/workbook-matrix.md) |
| 5 样式卡片 | [practice/style-extraction.md](references/practice/style-extraction.md)、[practice/style-cards.md](references/practice/style-cards.md) |
| 6 样式实现 | [contract/class-contract.md](references/contract/class-contract.md)、[practice/latex-pitfalls.md](references/practice/latex-pitfalls.md)、[template/base.cls](template/base.cls) |
| 7 样式复核 | [practice/latex-pitfalls.md](references/practice/latex-pitfalls.md)、[governance/review-checklist.md](references/governance/review-checklist.md) |
| 8 逐页转写 | [practice/page-reading.md](references/practice/page-reading.md)、[contract/page-authoring.md](references/contract/page-authoring.md) |
| 9-10 矢量图 | [practice/figures-and-assets.md](references/practice/figures-and-assets.md) |
| 11 全书复核 | [practice/pagination-and-navigation.md](references/practice/pagination-and-navigation.md)、[governance/review-checklist.md](references/governance/review-checklist.md) |
| 12 矩阵构建 | [contract/workbook-matrix.md](references/contract/workbook-matrix.md) |
| 并行协作（跨阶段） | [governance/subagent-orchestration.md](references/governance/subagent-orchestration.md)、[governance/collaboration-and-baseline.md](references/governance/collaboration-and-baseline.md)、[governance/dispatch-prompts.md](references/governance/dispatch-prompts.md) |
| Git 检查点 | [governance/git-workflow.md](references/governance/git-workflow.md) |
| 15 发布与开源（可选） | [governance/release-and-open-source.md](references/governance/release-and-open-source.md) |

### 契约层 `references/contract/`

- [class-contract.md](references/contract/class-contract.md)：`.cls`、唯一入口、所有者树、计数器与视图、正交配置。
- [page-authoring.md](references/contract/page-authoring.md)：逐页源码的环境覆盖、合法嵌套、交叉引用、跨页对象、照录原书。
- [workbook-matrix.md](references/contract/workbook-matrix.md)：原书与做题本的纸张/主题/范围矩阵、纸型单一事实源。

### 手法层 `references/practice/`

- [page-reading.md](references/practice/page-reading.md)：读页面的方式——宽度决定清晰度、读图预算、图文错配防护、视觉能力自检。
- [style-extraction.md](references/practice/style-extraction.md)：并行样式提取的四步顺序（目录 → 代表页 → 汇总 → 扩样）、派发纪律、结构地图。
- [style-cards.md](references/practice/style-cards.md)：样式卡片字段和代表页选择规则。
- [figures-and-assets.md](references/practice/figures-and-assets.md)：矢量图重建策略（含函数图、3D 图、树图）、书法题字描摹、资产组织与逐图收敛。
- [pagination-and-navigation.md](references/practice/pagination-and-navigation.md)：页数漂移的定位与归因、目录排版约定、PDF 书签规则。
- [latex-pitfalls.md](references/practice/latex-pitfalls.md)：字体字距、分页节奏、页眉页脚、图形绘制、公式编号、警告分类等回归陷阱。

### 治理层 `references/governance/`

- [subagent-orchestration.md](references/governance/subagent-orchestration.md)：能力预检、调度者与执行单元的职责边界、任务包、车道、并发节奏。
- [collaboration-and-baseline.md](references/governance/collaboration-and-baseline.md)：基线冻结、批次纪律、收敛门与不可逆操作保护。
- [dispatch-prompts.md](references/governance/dispatch-prompts.md)：样式提取、结构地图、逐页转写、复核四类单元的派发提示词模板。
- [review-checklist.md](references/governance/review-checklist.md)：结构、编译、视觉和人工复核门槛。
- [git-workflow.md](references/governance/git-workflow.md)：检查点、提交消息格式。
- [release-and-open-source.md](references/governance/release-and-open-source.md)：发布与开源的产物、权利边界、双通道打包、泄漏审计。

### 脚本

**输入审计与页面处理**

- `scripts/init_project.py`：创建项目骨架，并把技能的 `scripts/`、`template/` 复制进项目。
- `scripts/split_pdf.py`：按页拆出 PNG，优先直取整页嵌入图，不重采样。
- `scripts/correct_pages.py`：按 `page-corrections.json` 应用 0/90/180/270 旋转。
- `scripts/renumber_pages.py`：舍去证据页、命名最终页面、生成入口骨架与语义模块。
- `scripts/crop_page.py`：单页取图（`--overview` 总览 / `--band` 横带 / `--region` 区域），报告输出尺寸与等效 dpi，裁剪即计入读图预算，只允许写 `tmp/`。
- `scripts/read_budget.py`：每页读图预算的账本与只读报告（`check`/`report`）。
- `scripts/page_workspace.py`：拆页临时工作区（`extracted/`）路径解析。
- `scripts/pdf_backend.py`：PyMuPDF 的单一导入入口（所有脚本共用，避免各自写 fallback）。

**质量门**

- `scripts/audit_toc.py`：目录模块与自动目录指令的静态审计。
- `scripts/audit_provenance.py`：正文来源页标记与前后置模块覆盖的静态审计。
- `scripts/audit_semantics.py`：语义所有权、跨页环境结构与集中职责归属的静态审计。
- `scripts/audit_pdf_outline.py`：按项目登记的前后置模块清单审计 PDF 顶层书签、顺序与非空目标页。
- `scripts/audit_pdf_build.py`：成品 PDF 对象层审计；整页位图、答案哨兵泄漏与逐页纸型核对。
- `scripts/audit_page_density.py`：按墨迹密度筛查异常稀疏页，帮助定位分页漂移；只做诊断。
- `scripts/build_profiles.py`：纸型尺寸的单一事实源，`.cls` 与成品审计共用。
- `scripts/audit_release.py`：发布前泄漏审计；确认扫描件/页图未进入版本控制，法律文件齐备。

**调度**

- `scripts/orchestrate.py`：调度批次、生成单元任务包、校验批次产出并提交 Git 检查点（`plan`/`next`/`verify`/`checkpoint`/`status`）。

开发期工具（不属于重建流程，仅维护本技能时使用）：

- `tools/deploy_skill.py`：把本仓库以目录联接部署到本机运行时的技能目录，默认覆盖 4 个主用运行时（Codex `~/.codex/skills`、Claude Code `~/.claude/skills`、DSH `~/.dsh/skills`、Kimi Code `~/.kimi-code/skills`）。`--status` 查看现状，`--force` 把过期实体副本归档后改为联接，`--all` 或 `--only` 处理其它已安装工具，`--remove` 只移除联接。联接保证"改仓库即改技能"，不会出现副本漂移。
- `tools/make_fixture_pdf.py`：生成无文字层的演练用图片型 PDF。
- `tools/make_vision_probe.py`：生成内容已知的视觉能力探针图，用于在派发前确认某条路线能否读图。

回归测试在 `tests/`，其中 `tests/mutation_check.py` 会临时注入已知缺陷以确认测试确实能捕获它们。
