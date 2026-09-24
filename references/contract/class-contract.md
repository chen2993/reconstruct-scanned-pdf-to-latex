# 类文件契约

`.cls` 与构建入口必须满足的约定：所有权模型、唯一入口、计数器与视图、正交配置。
逐页源码的编写规则见 [page-authoring.md](page-authoring.md)；分页与目录书签见 [pagination-and-navigation.md](../practice/pagination-and-navigation.md)；排版回归陷阱见 [latex-pitfalls.md](../practice/latex-pitfalls.md)。

## 内容

- [1 所有权边界](#1-所有权边界)
- [2 页面入口](#2-页面入口)
- [3 计数器与视图](#3-计数器与视图)
- [4 正交配置](#4-正交配置)

## 1. 所有权边界

项目只维护一套内容事实和一套共享样式：

- `latex/front/*.tex` 与 `latex/back/*.tex` 承载按语义类型命名的前后置逻辑模块（如 `cover.tex`、`toc.tex`、`afterword.tex`）；禁止 `front-xxx.tex`、`back-xxx.tex` 或其他页码式文件名；
- `latex/pages/pages-xxx.tex` 承载正文页；
- 项目 `.cls` 拥有纸张、版心、字体、标题、页眉页脚、颜色、环境、计数器、内容筛选、做题本和图形接口；
- `main.tex` 是唯一目标和编排入口；它接收 driver 提供的 `\BookBuildOptions`，在 `\documentclass` 前通过 `\PassOptionsToClass` 交给项目 `.cls`，不实现第二套样式；
- `latex/pages/figures/*.tex` 只定义可嵌入的矢量主体，页面或语义环境拥有题注、标签、引用和显示条件。

`template/base.cls` 只用于理解接口形状，不是项目模板、父类或视觉值来源。参考类的 `original` profile 不提供默认尺寸；项目类必须在导言区用设置器写入经人工确认的原书尺寸，且**所有目标（含完整书）都使用这个尺寸**。缺少尺寸时类文件在 `\begin{document}` 明确报错，不会悄悄退回引擎默认纸张。`a4`、`pad11`、`pad13` 只属于做题本选项，完整书不能传入这些 profile。

目标配置的应用时机是一个已证实容易出错的点：模式、纸型和主题必须在导言区结束前应用（参考实现用 `\AtEndPreamble`），因为 `geometry` 的纸张尺寸只在导言区生效；放到 `\begin{document}` 之后不报错但会被静默忽略，使所有做题本退回默认纸张。详见 [latex-pitfalls.md](../practice/latex-pitfalls.md) 第 6 节。

自定义环境、命令、计数器、标签键和配置 API 必须使用英文 ASCII 标识符，只允许 ASCII 字母/数字和必要的下划线；不得使用中文、中文词组或连字符。标准 LaTeX 的带星号布局环境（如 `figure*`、`equation*`、`align*`）只作为既有布局环境使用，不能给自定义语义所有者加星号。中文可以作为正文、题注或角色显示文本的值，但不能成为任何 LaTeX 名称。连字符可以出现在文件名和页面标识中，但不能出现在这些 LaTeX 标识符中。

### 页面分型与教材可选结构

样式卡片先把原件分为可观察的页面类型，再把类型映射到语义所有者和版式钩子。常见类型包括封面、版权/出版信息、献词/序言、目录、章节首页、普通正文、图表/公式密集页、参考文献/索引/附录以及封底/书末页；只登记原件实际存在的类型。版权/出版信息页若仅提供印刷规格证据，按 `publication-info` 记录后舍去；与封面相同的黑白内封复刻页按 `cover-facsimile` 记录后舍去。页面类型不是环境名，也不要求每种类型各自对应一个文件。

前置和后置内容按逻辑模块逐条 `\input`，一个模块可以自然扩展为多页；不要为了对齐源扫描页而把目录、序言或参考文献硬拆成固定页数。原书纸型优先读取书内印刷信息中的开本、成品尺寸或纸张规格，再用多张代表页的页面几何交叉验证；印刷信息缺失、模糊、单位不明、与页面几何冲突，或存在尺寸漂移/异常 `MediaBox` 时，只记录为待确认项，不直接写死进 `.cls`。

题目、答案和做题本是可选能力。只有原件存在例题或习题且用户要求时才登记对应所有者、计数器和构建目标；普通教材没有题目时，完整书仍可独立构建，不生成空题目环境或空做题本。

## 2. 页面入口

前置和后置必须逐条原生导入，以便控制自然扩展的模块顺序。完整书和做题本共用同一个 `main.tex`；构建脚本只改变 driver 中的 `\BookBuildOptions`，不复制入口：

```tex
% driver.tex; main.tex 默认可直接编译为 book,print
\def\BookBuildOptions{workbook,examples,pad11,eyecare}
\input{main}
```

`main.tex` 在 `\documentclass` 之前接收该选项并加载同一组内容模块：

```tex
\providecommand{\BookBuildOptions}{book,print}
\edef\BookApplyBuildOptions{%
  \noexpand\PassOptionsToClass{\BookBuildOptions}{projectclass}}
\BookApplyBuildOptions
\let\BookApplyBuildOptions\relax
\documentclass{projectclass}

\begin{document}
\input{front/cover}
\input{front/preface}
\input{front/dedication}
\input{front/toc}
\bookinput{1}{584}
\input{back/afterword}
\end{document}
```

**原书实际存在的**前后置模块，各自在模块文件的实际第一页登记一条书签（显示标题按原书文字；语义键用英文 ASCII 标识符）。
下面是常见模块的参考写法，按原件取舍，不是固定清单：

```tex
% front/cover.tex
\bookbookmarkmodule{封面}{cover}
% front/preface.tex
\bookbookmarkmodule{前言}{preface}
% front/dedication.tex
\bookbookmarkmodule{献词}{dedication}
% back/afterword.tex
\bookbookmarkmodule{书末页}{backmatter}
```

项目 `.cls` 必须实现 `\bookinput{起始}{结束}` 接口，按三位编号依次加载 `pages/pages-001.tex` 起的正文页；不得让入口展开为正文逐条 `\input`。接口必须在缺页、范围倒置或编号非法时明确报错，不能静默跳过。

**范围命令的命名约定**：规范名是 `\bookinput`，项目应优先采用它。参考工具（`orchestrate.py` 推正文范围、`audit_toc.py` 与语义审计读入口）另外也识别 `\bookinputpages` 这个别名，因为兄弟项目用过该名。**不要另造第三种名字**——工具认不出就无法定位正文范围；确需改名时，同时把该名加入工具的识别集合，并保证全书只有一处范围声明。前置和后置仍不得改成批量范围加载器。一个前置或后置模块可以在同一文件中自然生成多页。
若 workbook 需要改变序言或目录的显示，有两种做法，**由用户选择**（见 [workbook-matrix.md](../contract/workbook-matrix.md) 第 2 节）：

- **单入口 + 条件命令**：入口里的模块清单保持静态可审计，在模块内部用英文命名的公共条件命令（参考 `\bookifworkbook`）控制内容；
- **独立做题本入口**：做题本有自己的 driver 与专用前后置模块（例如 `main-workbook.tex` + `front/workbook-cover.tex`），题目内容仍复用 `pages-xxx.tex`。

两条路线的共同底线：**题目与答案内容只能有一份源码，类文件只有一个**。不得为做题本复制题目、另写题号或另存一份正文。

### 目录与 PDF 书签

- `latex/front/toc.tex` 必须只调用一次项目类文件提供的自动目录指令（固定参考接口为 `\bookmaketoc`）；目录条目、页码和缩进由 `.cls` 及 LaTeX 辅助文件生成；禁止在 `toc.tex` 或逐页源码中手写目录条目、页码或逐页 `\addcontentsline`。构建前运行 `scripts/audit_toc.py`。
- `bookpart`、`bookchapter`、`booksection` 等结构命令必须由 `.cls` 自动写入目录并建立对应 PDF 书签；页面源码只提供标题语义，不手工写书签层级或页码。
- 前后置模块在其实际第一页调用 `\bookbookmarkmodule{显示标题}{ascii_key}`（或项目等价接口）。参考接口先结束当前页、建立锚点再写入书签，因此每个模块的目标是其实际第一页；项目类若改写接口也必须保持这一契约。最终 PDF outline 必须覆盖**原书实际存在的每个前后置模块**（有献词就要有献词书签，没有就不该出现），键名只用英文 ASCII 标识符，目标位置由当前排版自动确定。模块清单以原件为准，不套用固定四键。
- **目录内容与书签是两套独立集合**，不要假定“进书签就一定进目录”。每个模块和结构层级都要分别决定是否出现在印出来的目录、是否出现在 PDF 书签树里。常见组合是“只在书签、不进目录”（前言、末页这类）或“进目录但不进书签”（细节层级）。把决策集中记录在 `.cls` 或 API 文档里。排版实现见 [pagination-and-navigation.md](../practice/pagination-and-navigation.md)。
- 每次构建至少运行两遍并检查 `.toc`、PDF outline 和内部链接收敛；书签缺失、重复、层级错误、顺序错误或指向空白页均阻止发布。原件没有对应模块时暂停并请求人工决定，不伪造内容或静默省略。

正文逐页文件只保留一个最终页面标识注释，例如：

```tex
% Source page: pages-023
```

前置/后置模块可以自然扩展为多页，因此可用 `% Source pages:` 列出该模块覆盖的多个最终标识；禁止写入物理页号、逐页成品页码、中间目录或拆分批次。

来源页标记写成注释或一个不产生排版结果的项目空指令都可以（参考接口 `\booksourcepage{pages-023}%`，需在 `semantic-audit.json` 的 `standalone_commands` 中登记）。**标记里必须是最终页面标识，不是原 PDF 物理页号**——物理页号在舍去证据页和重新编号后就不再有效，写进源码会诱导后续单元照错。无论用哪种写法，都要满足 `scripts/audit_provenance.py` 的约束：每页恰好一个、与文件名一致、全书严格递增。

### 优先用层级而非手工排版

原件里靠字体、加粗、缩进“看起来像标题”的文字，应该还原成真正的结构层级（`bookpart`/`bookchapter`/`booksection`/`booksubsection`），由 `.cls` 决定它的外观、是否进目录、是否进书签：

- 结构命令自动处理编号、目录条目、书签层级和页眉页脚标记，比手写样式文本稳定得多；
- 某些层级要出现在 PDF 书签里但**不进**印出来的目录（例如更细的分级或特殊模块），用 `.cls` 的开关控制，不要手写书签；
- 同一种视觉层级在全书必须映射到同一条结构命令；两个章节里看起来一样的标题用了不同命令，是后面目录对不齐和样式漂移的常见根因。

## 3. 计数器与视图

例题、习题和一般题目使用独立计数器及筛选键。隐藏视图仍按类文件契约推进需要保持引用稳定的计数器，但页面源码不得手动 `\setcounter` 或写显示编号。至少支持：

| 视图 | 预期内容 |
|---|---|
| `full` | 全部前后置、正文、知识、题目、答案和媒体 |
| `body` | 正文和结构，隐藏题目与答案 |
| `knowledge` | 知识块、证明和必要媒体 |
| `examples` | 例题及其答案，隐藏习题 |
| `exercises` | 习题及其答案，隐藏例题 |
| `workbook` | 按做题本范围保留题干和必要媒体，隐藏全部答案；原书的各前后置模块（封面、前言、献词、目录、书末页等，以原件为准）仍与完整书一致 |

做题本不是“只打印题目”。它必须复用同一组前置/后置模块，才能保持完整书的书签集合及其非空目标页。把这些模块整体隐藏是曾在真实矩阵构建中复现的缺陷：做题本塌缩成一页并丢掉书末页书签，而完整书目标照常通过，因此只在矩阵目标上暴露。

每个视图切换只改变 `.cls` 的集中显示钩子，不在页面文件中复制内容或写条件分支。分类视图和做题本都必须复用同一份页面源码：不得靠另起一套页面文件、另写一套题号或另存一份内容来区分目标，否则同一道题会出现两份互相漂移的事实。

## 4. 正交配置

把构建目标拆成互不耦合的配置轴，并让同一份页面源码接受这些轴：

- 内容模式：完整书、分类视图或做题本；
- 做题本范围：`examples`、`exercises`、`all`；
- 做题本样式：例如 `simple`、`normal`；
- 纸型：完整书只使用用户确认的原书尺寸，做题本才使用 `original`、`a4`、`pad11`、`pad13`；
- 主题：用户确认的已实现主题，默认矩阵只固定 `print`、护眼黄 `eyecare`；项目实现别的主题时才加入；
- 可选的语义小节分页：`section_break=false|true`，只对做题本开放。

完整书不得注入做题本范围、纸型变体或 `section_break`；类文件的设置器在非做题本模式下应报错，或明确记录为无效并保持完整书基线不变。每个公共设置器都要在 API 文档中记录输入、输出、错误行为和英文命名契约，并在类文件完成后进行常规编译复核；不同目标分别缓存和编译，不能通过页面源码条件分支或复制页面来实现变体。

做题本的答题区由 `.cls` 集中测量和生成：仅对已经验证可收集的完整题干、必要媒体和答题区，将其作为一个分页单元；原书尺寸与 A4 自然向下但不得拆开，Pad11/Pad13 默认一页一题。答题区高度可以参考被隐藏答案的排版高度动态计算；若单页容量不足，优先整题移到下一页，超出单页容量时必须按项目契约报错、回退或请求人工审核，不能静默缩小内容。测量或丢弃答案时必须保留局部分组、计数器、引用和完整 LaTeX 环境栈；语义所有者栈与普通环境栈分别审计，不能为了隐藏答案而删除未登记的 `tikzpicture`、公式或列表。
