# 逐页内容编写规则

编写 `pages-xxx.tex` 与前后置模块时必须满足的约定：环境覆盖、合法嵌套、交叉引用、跨页对象与分批转写。
`.cls` 与构建契约见 [class-contract.md](class-contract.md)；排版回归陷阱见 [latex-pitfalls.md](../practice/latex-pitfalls.md)。

## 内容

- [1 环境全覆盖](#1-环境全覆盖)
- [1.5 编号类内容](#15-编号类内容一律用语义机制生成)
- [2 合法嵌套](#2-合法嵌套)
- [3 交叉引用](#3-交叉引用)
- [4 跨页与媒体](#4-跨页与媒体)
- [5 分批转写](#5-分批转写)

## 1. 环境全覆盖

页面中的普通正文也必须由正文所有者管理；顶层只允许结构命令和根所有者环境。列表、引文、脚注、边注、`align`、`tabular`、`tikzpicture` 等是内部布局组件，必须继承最近的语义所有者；独立成块且需要题注、编号或单独筛选的图、表、公式和算法，改由登记过的媒体环境拥有。

参考接口可以按原件改名或增删，但实际接口必须记录在 `docs/class-api.md`：

| 所有者域 | 参考环境或命令 | 覆盖内容 |
|---|---|---|
| 结构 | `bookpart`、`bookchapter`、`booksection`、`booksubsection` | 篇、章、节、小节及其目录、书签和页眉页脚 |
| 前后置 | `bookfrontmatterblock`、`bookbackmatterblock`、`booksupplement` | 封面、献词、序言、目录说明、后记和补充说明 |
| 正文 | `bookbody`、`booktext`、`bookexposition` | 普通段落、连接语、列表、引文、脚注和边注 |
| 知识 | `bookdefinition`、`booktheorem`、`booklemma`、`bookproof` | 定义、定理、引理、证明和知识块 |
| 题目 | `bookexample`、`bookexercise`、`bookquestion` | 例题、习题、一般题目及跨页题干 |
| 答案 | `bookanswer`、`booksolution`、`bookanalysis`、`bookhint` | 答案、解析、解法和提示 |
| 评注 | `bookremark`、`booknote`、`booktip`、`bookwarning` | 注释、说明、技巧、注意和小结 |
| 媒体 | `bookfigure`、`booktable`、`bookalgorithm`、`bookequation` | 矢量图、表格、算法和展示公式 |

### 什么算原书内容

只转写原书印刷内容。**明显是后来在 PDF 上添加的人类批注**——手写笔记、红笔订正、荧光笔、圈画、勾叉、页边批注——不属于原书内容：忽略它们，不为它们建环境或样式，也不因为它们而暂停该页；被标注的印刷文字照常转写。

判断依据是“后期叠加”而不是“手写”：

- 指向批注的证据：笔迹与印刷字明显不同、压住印刷文字、颜色溢出笔画、脱离版心网格、不参与原书编号、或全书只在个别页孤立出现；
- 反向要求：原书自己印出来的内容即使长得像手写（手写体例题、印刷旁注、影印批注、作者手迹）也必须照原样转写，不得误删。

只有当批注遮住了必须转写的正文，或批注与印刷内容确实无法区分时，才暂停并向用户确认。

### 照录原书，不"顺手改对"

发现原书本身印错（错字、漏字、公式符号写反、编号跳号）时，**照录原书的字符**，不要改正。底本是证据，转写者的职责是搬运而不是校勘；擅自"改对"会让重建版与原书出现无法追溯的差异，也掩盖了真实的排版问题。

- 存疑只在复核记录（`reviews/`）里写一句"原书印作 X，疑为 Y 之误，已照录"；
- 需要更正说明时，只能放在**新增模块**里并标明新增，不得直接改动正文；
- 实测反例：某单元把原书 `（或 x = x(x)）`（显系 `x(y)` 之误）直接改写成 `x(y)`——这是篡改底本，属于必须避免的错误。

## 1.5 编号类内容一律用语义机制生成

**凡是有编号或标签的成组内容，标签都必须由 `.cls` 的计数机制产生，源码只提供内容。** 这是本技能被实测违反最多的一条：agent 遇到小问和选择题时容易直接手打 `(1)`、`（1）`、`A.`，结果编号样式与原书不一致、跨页续写时重号、也无法交叉引用。

判断规则很简单：**如果你在源码里敲出了编号字符本身，就是错的。**

| 内容 | 错误写法 | 正确写法 |
|---|---|---|
| 小问 / 分步 | `(1) 求……` `（2）证明……` | 语义列表环境，标签由 `.cls` 生成 |
| 选择题选项 | `A. ……` `（B）……` | 选项命令/环境，标签由 `.cls` 生成 |
| 例题、习题、定义、定理 | `例 1.2 ……` | 题目环境，编号由计数器产生 |
| 步骤、圈码序号 | `① ……` `步骤 1：` | 对应计数器 + 生成的序号命令 |
| 公式编号 | 手打 `(3.1)` | `\tag` 或计数器 |
| 图、表、算法编号 | 手写「图 3.1」 | 媒体环境 + `\ref` |

### 小问与分步

用**语义列表**，不要用裸 `enumerate` 手写标签，也不要用纯文本：

```tex
% .cls：定义一次，全书复用
\newlist{booksubitems}{enumerate}{2}
\setlist[booksubitems,1]{label=(\arabic*), leftmargin=2.2em, itemsep=0.3ex}
\setlist[booksubitems,2]{label=(\roman*), leftmargin=2.0em, itemsep=0.3ex}

% 页面源码：只写内容，标签自动生成（1）（2）…
\begin{booksubitems}
  \item 求函数的定义域；
  \item 判断 $f(x)$ 在 $x=0$ 处的连续性。
\end{booksubitems}
```

要点：

- **标签格式在 `.cls` 里定一次**（`label=`、缩进、间距），页面源码不出现编号字符；
- 原书用 `（1）` 还是 `(1)`、用阿拉伯数字还是罗马数字，属于**逐本量取的事实**——按代表页确认后写进 `.cls`，不要默认一种；
- 需要编号稳定以支持交叉引用时，用 `ref=` 指定 `\ref` 的输出形式；
- 层级最多两层（`（1）` 下再有 `(a)`），更深就该考虑换语义环境。

### 选择题选项

**选项标签由类文件生成**，源码连 `A`/`B` 都不写。原书的选项排布有单行多列、二二网格、竖排等多种，**同一套内容需要按原书版式提供若干变体**——变体是 `.cls` 的命令，不是页面里的手排表格：

```tex
% .cls：定义一组版式变体，标签统一由计数器生成
\newcounter{bookchoice}
% 标签样式只在这一处切换：\bookchoiceentry 始终调用 \bookchoiceletter，
% 想换成括号版只需 \let\bookchoiceletter\bookchoiceparenletter。
\newcommand{\bookchoiceletter}{\stepcounter{bookchoice}\Alph{bookchoice}.\nobreak\hspace{.35em}}
\newcommand{\bookchoiceparenletter}{\stepcounter{bookchoice}(\Alph{bookchoice})\nobreak\hspace{.35em}}
\newcommand{\bookchoiceentry}[1]{\textup{\bookchoiceletter}#1}

% 单行四列（常见）
\newcommand{\bookchoicesfour}[4]{%
  \par\begingroup\setcounter{bookchoice}{0}%
  \noindent\begin{tabular}{@{}*4{>{\raggedright\arraybackslash}p{40mm}@{}}}
    \bookchoiceentry{#1}&\bookchoiceentry{#2}&\bookchoiceentry{#3}&\bookchoiceentry{#4}%
  \end{tabular}\par\endgroup}

% 二二网格（选项较长或含公式）
\newcommand{\bookchoicestwobytwo}[4]{%
  \par\begingroup\setcounter{bookchoice}{0}%
  \noindent\begin{tabular}{@{}>{\raggedright\arraybackslash}p{76mm}@{}>{\raggedright\arraybackslash}p{76mm}@{}}
    \bookchoiceentry{#1}&\bookchoiceentry{#2}\\[1.4pt]
    \bookchoiceentry{#3}&\bookchoiceentry{#4}%
  \end{tabular}\par\endgroup}
```

```tex
% 页面源码：只给内容，不给标签
\bookchoicesfour{$0$}{$-\infty$}{$+\infty$}{不存在但也不是 $\infty$}
```

要点：

- **每次进入选项组要重置选项计数器**（`\setcounter{bookchoice}{0}`），否则第二题会从 E 开始；
- 标签形式（`A.` / `(A)` / `（A）`）由 `.cls` 定，可用一条 `\let` 切换风格，不必为每种风格复制命令；
- **选项排布是原书事实**：单行四列、二二网格、竖排、含公式的显示式选项，都要按代表页量取列宽与间距，命名成变体；
- 列宽用固定 `p{...}` 而不是内容驱动的 `X`／`\extracolsep`——后者会随公式宽度变化把后续选项整体推移，跨页时更明显；
- 选项若含展示公式，用 `\displaystyle` 包裹（原书选项里的分式与求和通常是显示尺寸）；
- **不要**用 `itemize` 加 `\item[A.]` 冒充选项：标签仍是手写的，且缩进/换行行为不受控。

### 圈码与步骤

圈码 `①` 和小标题式的「步骤 1」同样是成组编号，不手打：

```tex
% .cls
\newcommand{\bookcircled}[1]{\textcircled{\scriptsize #1}}
\newlist{bookcircleditems}{enumerate}{1}
\setlist[bookcircleditems,1]{label=\bookcircled{\arabic*}, labelsep=0.5em, leftmargin=2.4em}
```

页面源码用列表环境：

```tex
\begin{bookcircleditems}
  \item 当 $x\to0$ 时；
  \item 当 $x\to\infty$ 时。
\end{bookcircleditems}
```

需要单独插入一个序号时（例如正文中间接一个 `①`），用 `.cls` 提供的命令，而不要手打字符。分步说明用 `bookmethodstep`、`bookproofstep` 这类**带计数器**的步骤环境，标签由环境生成。

### 为什么必须这样

- **跨页续写不会重号**：同一题的续写段重新进入环境时，计数器保持连续；手打编号必然重号；
- **样式一致**：全书编号格式只在一处定义，改一次全改；
- **可引用**：计数器配合 `\label`／`\ref` 才能做交叉引用，手打编号无法被引用；
- **可筛选**：做题本按题目/答案环境筛选，裸文本无法被筛选开关识别。

### 复核时的检查方式

逐页转写完成后，运行机械审计：

```powershell
python <skill>/scripts/audit_hardcoded_numbers.py <project>
```

它按"**连续递进序列**"判定：`（1）→（2）`、`A. → B.`、`① → ②` 这种成组出现才报，单点的 `由（1）式得`、`(38.20,182.0)` 坐标、`rank(A)`、`方法 1` 都不报；行首的 `例 10`、`步骤 1` 另行单点报告。命中的每一组都要改成语义环境或选项命令。原书正文里确实成组的字面编号，在同一行加 `% allow-number` 豁免。

审计只能证明"没有成组手打编号"，不能证明"用对了环境"。因此同时确认每种成组内容都有对应的语义环境或命令，并登记在 `docs/class-api.md`。

## 2. 合法嵌套

所有者可以形成受控树，而不是强制拍平成同级：

- 题目可以包含答案、解析、提示、步骤、评注和必要媒体；
- 答案可以包含步骤、评注和答案专属媒体；
- 知识块可以包含证明、评注和媒体；
- 题目不能嵌入另一个题目，答案不能成为另一个答案的任意容器；跨页对象保留同一个语义环境，可以跨越同一 `\bookinput` 连续加载的多个源码文件，不能拆成公开的分段接口。

父级隐藏时子级不得单独出现；父级显示但答案开关关闭时只隐藏答案子树。每个子所有者的直接父级白名单写入 `semantic-audit.json` 的 `owner_parent_environments`，`$root` 表示根所有者。

## 3. 交叉引用

题目、公式、图表和章节之间的指向全部来自 LaTeX 交叉引用：语义环境在 `\begin` 处 `\label`，引用处用 `\ref`、`\eqref` 或 `\hyperref`，由 `.cls` 集中配置 hyperref 与链接颜色。页面源码不得写手工跳转、裸编号或“见第 X 章”式人工指向；原书没有引用的图号和“见图 x.y”不因结构重建而补出。

## 4. 跨页与媒体

跨页知识块和题目使用**单一、连续、可断页**的 LaTeX 环境：在一个源码文件写 `\begin{...}`，在后续源码文件写匹配的 `\end{...}`，由环境自身在成品里断页。禁止“上一页关框、下一页再开一个续框”——那会在成品里留下两个框，或在框头重复一次标题。

同一 `\bookinput` 的连续页面加载在词法上形成一个 TeX token stream，因此跨文件的 `\begin`/`\end` 在语法上成立。但这条路径有真实陷阱：**只要任一页面文件混用了会开启分组的版式宏（`\begingroup`、`\setbox`、某些定位宏、`\afterpage` 等），跨文件的环境就可能被静默提前关闭，XeLaTeX 依然返回成功**，问题只在视觉复核时才暴露。因此：

- 跨页环境在 `.cls` 里就用**可断页**的盒子实现（例如启用 `breakable` 的 `tcolorbox`，或流式 `\newenvironment` 加成对的开合样式钩子），并为一个跨文件的实例**显式编译验证**，确认断页后框线与框头连续、无重复标题、无内容丢失；
- 页面文件**不要**在开放环境内部引入会开启分组的宏；需要成组排版时，把分组也一并在 `.cls` 里做，或把该对象整段并回同一个文件；
- 若无法可靠跨文件，就把该逻辑对象**并回一个文件**（内容仍按来源页标识注释划分），靠环境的自然断页跨越成品页；宁可文件边界不对齐原书页，也不要制造两个框；
- 审计器只能静态发现“未登记环境跨文件”和“未闭合环境”，**发现不了静默的作用域泄漏**；所以这条契约必须靠一次真实编译 + 跨页视觉复核来兜底，不能只靠审计通过就放行。

- 只有 `\begin` 初始化计数器、标签、锚点和首段标题；只有 `\end` 执行终止行为，包括做题本的唯一答题区。中间源码文件不得重复标题、编号、题注或答题区；
- 可跨页所有者必须在 `semantic-audit.json` 的 `cross_page_owner_environments` 显式登记，同时存在于 `owner_environments`。审计器按前置、正文、后置的完整导入顺序维护全局环境栈；未登记的布局环境不得跨文件，整本输入结束时所有环境都必须闭合；
- 这类环境必须是流式、非捕获正文的实现，例如经验证的 `\newenvironment`。`\NewEnviron` 和其他读取完整正文的装饰器不能用于它们，除非有专门的跨 `\bookinput` 编译用例证明安全；
- **捕获正文的环境也会破坏其内部命令**：例如把 `\@starttoc` 这类含 `@` 的命令放进一个捕获正文（`+b`）的环境里，正文会先被分词，导致编译错误。前置模块要调用目录输出时，`.cls` 应暴露一个不含 `@` 的公共宏，由模块调用，不要把内部实现直接写进模块；
- `template/base.cls` 仅示范以 `bookstyle...begin`/`bookstyle...end` 成对钩子排版流式环境；项目 `.cls` 可以完全替换这些视觉钩子，但不能把跨页正文重新变成捕获参数；
- 视图筛选、隐藏答案和做题本测量不得通过跳过后续 `\input` 来隐藏跨页内容。需要收集题目时，只对已验证的内容类型使用跨文件可用的盒子；无法安全收集或单页容纳时由类文件明确报错、执行文档化回退或请求人工复核。

图形模块每次只负责一张图，文件名可以使用连字符，例如 `figure-pages-023-001.tex`；模块内部定义的宏名仍只能使用 ASCII 字母/数字，文件名中的三位页号和序号属于源码元数据，不写进成品。图形模块不得包含浮动体、题注、标签、手工图号、页码、位图或截图。图形位置和题注由页面所有者及 `.cls` 管理。

页面所有者通过 `.cls` 的集中接口嵌入图形主体（参考 `\bookfiguremodule{figure-pages-023-001}`），而不是在页面源码里写 `\input` 路径；这样图形模块的路径解析、重复嵌入和缺失主体都由类文件统一报错。原书的结构网络图和思维导图用可编译的树形或坐标矢量图重建，保留原书层级，不只处理首例。

## 5. 分批转写

分批纪律、任务清单、跨页交接、收敛门和停工反馈流程统一见 [collaboration-and-baseline.md](../governance/collaboration-and-baseline.md)。

本节只记录**内容侧**的转写约束：一个逻辑对象可以跨文件流动，但转写单元不得为了对齐文件边界而增删环境边界（见上一节的跨页规则）；不得以临时字体、颜色、间距或最相近环境代替未登记的样式，发现缺口就停工上报。
