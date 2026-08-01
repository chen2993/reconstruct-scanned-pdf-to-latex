---
name: reconstruct-scanned-pdf-to-latex
description: 将扫描版或图片型教材 PDF 重建为可编辑、可编译的 LaTeX 项目。覆盖输入审计、页面分型、页面拆分、方向修正、前置页/正文/后置页命名、样式卡片、多页纸张确认、项目专用 .cls、分批逐页转写、矢量图、原书与例题/习题/全做题本构建、Git 检查点和多轮视觉复核。只用原生多模态能力读取内容，禁止 OCR 和 PDF 文本提取。
---

# 扫描教材重建 LaTeX

本 skill 把扫描页当作视觉证据，最终产物必须是重新排版的 LaTeX，而不是整页图片的包装。确定性文件操作使用 `scripts/`；文字、公式、方向、样式和图形语义只能由运行环境的原生多模态能力判断。

## 硬性规则

- 只使用运行环境原生多模态能力读取页面内容、判断方向、分析样式和核对结果；严禁调用 Tesseract、PaddleOCR、OCRmyPDF、云端 OCR、PDF 文本提取或其他文字识别工具作为内容来源。
- 不修改源 PDF，不导入整页扫描图，不把参考工程的书名、字体、颜色、尺寸、页数或局部版式直接复制到新项目。
- 页面拆分和旋转产生的中间文件只放临时目录，成功命名后清理；不保留中间页面副本、页面映射表或物理页记录。
- 最终页面标识只有 `front-xxx`、`pages-xxx`、`back-xxx` 三类。需要保留视觉证据时使用同名 PNG；源码页面使用 `front/`、`pages/`、`back/` 下的 `.tex` 文件。
- `.cls` 从空白文件按实际原件实现；`asserts/base.cls` 只是接口参考，不是父类或视觉模板。
- LaTeX 环境、命令、计数器、标签键和内部 API 的命名必须使用英文 ASCII 标识符，只允许字母、数字和必要的下划线，不得使用中文或连字符。中文只能出现在正文、题注、角色显示文本等值中；连字符只允许出现在文件名、页面标识、样式卡片 ID、路径和 Git 提交文本中。
- 所有显示编号由 `.cls` 计数器产生，逐页源码不得硬编码例题号、习题号、定义号、公式号、图表号或步骤号。
- 每个可见块有且只有一个直接语义所有者。所有者可以按原件语义受控嵌套，例如题目包含答案、答案包含步骤；父级隐藏时子级不得单独出现。普通正文、列表、引文、脚注、公式、表格和媒体也必须落在已登记所有者内。
- 跨页语义对象只使用一组 `\begin{environment}` 与 `\end{environment}`，可以跨越连续 `\input` 的 `pages-xxx.tex` 文件；禁止将同一对象拆成多个公开片段接口。源文件边界不是 TeX 分组，也不应自动插入分页。编号、标签、锚点和标题只在 `\begin` 初始化；终止行为（包括做题本唯一答题区）只在 `\end` 执行。可跨页所有者必须登记在 `cross_page_owner_environments`，并以流式、非捕获正文的 LaTeX 环境实现；不得用 `\NewEnviron` 或未经跨 `\input` 编译验证的正文捕获组件实现。
- 需要保留的图必须有可编译矢量源码。照片、连续色调或无法诚实矢量化的内容先暂停并询问用户，不得塞入截图或位图。
- 纸张尺寸、页面分区、语义归属、跨页关系或样式差异无法从证据可靠判断时，立即暂停当前批次并向用户提问；不要用猜测、近似样式或硬编码继续推进。
- 复核只记录最终页面标识、源文件和目标构建；不记录 PDF 物理页号或逐页页码映射。90% 一致只是进入人工审核的门槛，不是自动通过条件。
- 输入审计可以只读检查页数、页面方向、`MediaBox` 集合、资源类型、扫描边框和尺寸漂移；这些信息只用于判断工作策略，不得把 PDF 文字层或提取结果当作内容来源。

## 项目结构

初始化后项目逐步形成：

```text
project/
  .gitattributes  .gitignore  README.MD  build.ps1
  .reconstruct-scanned-pdf-to-latex/
    progress.md  page-corrections.json  semantic-audit.json  style-cards.md  reviews/
    front-xxx.png  pages-xxx.png  back-xxx.png
  docs/class-api.md
  latex/<project_class>.cls  latex/main.tex
  latex/front/cover.tex  latex/front/toc.tex  latex/back/afterword.tex
  latex/pages/pages-xxx.tex  latex/pages/figures/figure-xxx-yyy.tex
  asserts/base.cls  asserts/build.ps1  scripts/  tmp/  dist/
```

控制目录只保存进度、修正规则、样式卡片和复核结论。阶段 2 至 4 使用的 `pdf_pages/` 与联系表目录是临时工作区，阶段 4 成功后必须清理；最终只保留同名的 `front-xxx.png`、`pages-xxx.png`、`back-xxx.png`（若用户需要视觉证据）。页面 PNG 不是 LaTeX 内容来源，只是方向、样式和结果比对证据；最终交付前可以按用户决定清理。`asserts/` 中的 `base.cls` 与 `build.ps1` 是参考模板；实际项目的 `.cls` 和构建脚本写入 `latex/` 与根目录。

## 工作流

按顺序执行以下阶段。公共接口或样式发生变化时，先更新类文件、API、样式卡片和审计配置，再恢复受影响批次。

### 1. 文件树搭建

```powershell
python <skill>/scripts/init_project.py <project> --git
```

脚本只创建目录、控制文件、`docs/class-api.md` 和复核表，不创建项目 `.cls`、构建脚本或模板内容。检查 `git status --short` 后提交初始化检查点。

初始化后先做一次只读输入审计，再拆页：

- 统计页数、页面方向和 `MediaBox` 的稳定范围，区分稳定尺寸、轻微扫描漂移和明显异常值；不要用单个页面或异常值直接决定原书纸型；
- 检查页面资源是否以整页图像为主、是否存在少量结构异常页，并确认扫描边框、留白、黑边和裁切风险；这些检查只读 PDF 对象和渲染图像，不读取文字层；
- 先列出封面、版权/出版信息、目录、章节首页、普通正文、图表/公式密集页、参考文献/索引和封底等需要检查的类型；拆页并渲染联系表后再为实际存在的类型选择代表页，不存在的类型标记为“不适用”；
- 若 `MediaBox` 异常、尺寸漂移无法归因或纸张规格影响 `.cls`，暂停并请用户确认；审计记录只写集合、范围和结论，不写物理页映射。

### 2. 页面拆分

```powershell
python <skill>/scripts/split_pdf.py <project> <source.pdf> --image-source auto --dpi 300
```

若扫描 PDF 每页是完整嵌入页图，优先直接提取原始像素，不统一渲染、不重采样；复杂页才回退到指定 DPI 渲染。这里的“保留原像素”只针对临时视觉证据，避免为方向判断和样式分析额外损坏扫描质量；它不表示最终 LaTeX 要导入整页图片。后续内容、公式、版式和图形仍必须由原生多模态能力分析后重新写成 LaTeX。脚本只检查图像对象和几何，不读取文字层。核对页数、像素尺寸、有效 DPI 和回退原因；这些信息只供当前阶段使用，最终不写入交付树。

### 3. 页面修正

用联系表检查方向和页边界，忽略不影响阅读的小倾斜，不自动裁切或重采样：

```powershell
python <skill>/scripts/build_contact_sheets.py <project> --source pdf_pages
python <skill>/scripts/correct_pages.py <project>
```

在 `page-corrections.json` 只登记 `0/90/180/270` 度旋转。脚本可以在临时目录原子更新页图，但成功后只把结果交给阶段 4 命名，不制造或保留额外副本、裁切版本或重采样版本。即使没有旋转，也运行一次以完成人工方向检查。

### 4. 页面命名与入口骨架

将修正后的页按原件顺序直接命名为 `front-001`、`pages-001`、`back-001`。不生成页面映射或物理页表。

- 前置和后置按逻辑模块写入 `latex/front/`、`latex/back/`，例如 `cover.tex`、`dedication.tex`、`toc.tex`、`afterword.tex`；一个模块可以自然扩展到多页。
- 正文逐页写入 `latex/pages/pages-001.tex`、`pages-002.tex` 等。
- `main.tex` 是唯一编排入口：在 `\documentclass` 前用 `\providecommand{\BookBuildOptions}{...}` 接收构建 driver 的目标选项，并通过 `\PassOptionsToClass` 交给项目 `.cls`；正文和所有前后置目标共用这一入口。
- `main.tex` 对前置和后置使用多条原生 `\input{front/cover}`、`\input{front/toc}`、`\input{back/afterword}`，保留人工可调整的顺序；需要按 workbook 改变目录或序言时，使用类文件提供的公共条件命令，不复制第二个入口。
- 正文可以使用项目 `.cls` 提供的 `\bookinput{起始编号}{结束编号}` 批量导入 `pages/pages-xxx.tex`。若项目类文件不提供该命令，再逐条 `\input`；不得为前置和后置增加批量加载器。

每个源文件只记录自己的最终页面标识，例如 `% Source page: pages-023`；不记录物理页、拆分批次或中间路径。

### 5. 样式总结与样式卡片

```powershell
python <skill>/scripts/build_contact_sheets.py <project> --source final
```

只在 `.reconstruct-scanned-pdf-to-latex/style-cards.md` 记录代表页面标识和源文件路径，不复制页面。样式分析时可从多张不同页面共同推断纸张比例、版心、奇偶页和分页规律，但不另建“页面几何摘要”交付文件；这些判断直接落实到项目 `.cls` 并由多页校样验证。阶段 3 的方向联系表和本阶段的最终页面联系表都只是临时观察工具，样式卡片完成后可清理；样式卡片本身不得嵌入或复制页面图。样式卡片要覆盖实际存在的纸张/版心、奇偶页、章首页、各级标题、正文、列表/引文、页眉页脚、脚注/边注、公式、知识块、例题、习题、答案、图表、目录和特殊页，并说明辨识条件、环境/命令、视觉特征、显示视图及源页标识。用户先确认纸张尺寸；未知时标记待确认，不悄悄猜定。

先完成页面分型，再补充语义样式卡：封面、版权/出版信息、献词/序言、目录、章节首页、普通正文、图表或公式密集页、参考文献/索引/附录、封底或其他书末页。教材不一定包含例题或习题；没有对应内容时标记“不适用”，不要为了填满卡片而虚构题目环境或生成空做题本目标。页面分型只描述可观察的版面类别，不替代 `.cls` 中的语义所有者。

### 6. 样式实现

阅读 [references/style-cards.md](references/style-cards.md)、[references/class-and-content.md](references/class-and-content.md) 和 [asserts/base.cls](asserts/base.cls)，在 `latex/` 从零实现项目 `.cls`，并同步填写 `docs/class-api.md` 与 `semantic-audit.json`。集中管理纸张、版心、字体、间距、页眉页脚、颜色、环境、计数器、内容视图、题目归属、跨页接口和媒体接口。每新增一个公共接口，先在 API 文档中锁定输入、输出、错误行为和命名契约，再实现并进行常规编译复核；环境、命令、计数器和标签键先通过英文 ASCII 标识检查。每个登记为可跨页的环境都要以连续 `\input` 夹具验证单一 `\begin`/`\end`，并在完整书与隐藏视图各编译一次。

### 7. 样式复核

先冻结完整书的回归基线（源类文件版本、PDF SHA-256、页数、MediaBox、书签和代表页渲染）。对代表页反复执行“编译 -> 渲染 -> 多模态比对 -> 修改”，并确认只影响预期视图；首章首个正文页、奇偶页页眉标记、跨页对象和隐藏模式必须单独检查。达到 90% 且无语义错误、编号错误、未关闭样式缺口、未分类盒警告后，向用户展示校样并等待人工确认。未确认前不能进入批量内容填充。

### 8. 内容按页实现

每个并行单元通常负责连续 10 页，内部三轮：原生多模态转写、逐行内容复核、编译与版式复核。任务必须附当前样式摘要版本、每个可用样式卡片、该批页面分型（例如章节首页、普通正文、图表/公式页）及 `front-xxx`、`pages-xxx` 或 `back-xxx` 源页标识；不得复制代表页或发明局部样式。批次边界落在开放的可跨页所有者内时，主执行者向下一单元交接该环境名、起始页面标识、样式卡片版本和嵌套层级；这是瞬时协作上下文，不写入物理页映射，也不得补造新的环境边界。发现缺样式、样式变体或无法表达的版式，立即在 `reviews/style-gaps.md` 报告并暂停该块；主执行者更新 `.cls` 后，通知所有相关单元重新读取新版本再继续。图形只登记稳定 ID 和占位，不在本阶段实现。

### 9. 矢量图实现

每个单元一次只实现一张图，写入 `latex/pages/figures/figure-pages-023-001.tex`（前后置图使用 `figure-front-001-001.tex` 或 `figure-back-001-001.tex`）。图形模块的文件名可以含连字符，但其中定义的宏名必须只含 ASCII 字母和数字。模块注释记录源页标识、图形 ID和页面源码；不在图形模块内写题注、编号、页码或位图。

### 10. 矢量图复核

逐图检查结构、标签、公式、连接关系、大小、基线、题注、环绕和分页；独立编译图形后再检查嵌入正文。达到 90% 后仍需人工复核，结果写入 `reviews/figures.md`。

### 11. 全书复核

运行语义审计，确认每个 `pages-xxx.tex` 恰好被加载一次，并让审计器以完整导入顺序维护全局环境栈；只有显式登记的流式所有者可在文件边界保持开放，普通布局环境仍必须在本文件闭合。抽查封面、版权/出版信息、目录、章节边界、普通正文、公式密集页、树/流程/框图/时序图、表格、参考文献/索引、封底或其他书末页、奇偶页、前后置页和批次边界；只抽查原件实际存在的类型。记录最终页面标识与成品目标名的对应关系，不能用审计替代人工视觉检查。

### 12. 编译测试与做题本矩阵

按 [references/workbook-matrix.md](references/workbook-matrix.md) 和 [asserts/build.ps1](asserts/build.ps1) 实现根目录 `build.ps1`。每个目标生成独立 driver，只定义 `\BookBuildOptions` 并输入同一个 `latex/main.tex`，不得再创建 `main-workbook.tex`。完整书只构建用户确认的原书尺寸；仅当原件和用户选择都包含相应题型时，才构建例题、习题或全做题本，不为没有题目的教材生成空目标。题目目标可分别构建 `original`、`a4`、`pad11`、`pad13`，并支持 `print` 与护眼黄 `eyecare`。若项目 `.cls` 实现了语义小节强制分页，再把 `section-break=false/true` 作为仅做题本的可选轴；普通全书不得注入该参数。完整书中的跨页对象自然流动；做题本仅在题目、必要媒体和答题区可安全收集且能同页容纳时将其作为一个分页单元，否则明确报错、按项目约定回退或请求人工复核，不能静默缩小内容。Pad11/Pad13 一页一题。封面、献词、目录和末页在各目标复用同一内容模块，横向纸型只做响应式重排。每个目标独立缓存，至少两遍并在引用/目录收敛后再通过；编译退出码之外还要审计所有 PDF 页的存在、页数/MediaBox、空文字页、位图对象、答案泄漏、书签/链接和日志收敛，并分类处理盒警告。所有目标通过后才原子发布到 `dist/`。

### 13. 补充

按用户决定补充编者序、开源声明、版本说明或勘误入口。新增内容必须明确标为新增，不虚构原书书目信息或授权事实。

### 14. 最终复核

重新运行所需矩阵，抽查首尾页、章节、公式、图形、随机页面和三类做题本；更新 `reviews/final.md`，记录命令、页数、纸张尺寸、主题、已知差异和人工结论。未获人工确认不得称为完成或创建发布标签。

## 参考资料

- [references/style-cards.md](references/style-cards.md)：样式卡片字段和代表页选择规则。
- [references/class-and-content.md](references/class-and-content.md)：`.cls`、所有者树、计数器、视图和跨页内容约定。
- [references/workbook-matrix.md](references/workbook-matrix.md)：原书、做题本纸张/主题/范围矩阵及版面约束。
- [references/review-checklist.md](references/review-checklist.md)：结构、编译、视觉和人工复核门槛。
- [references/git-workflow.md](references/git-workflow.md)：检查点、并行协作和提交消息格式。
