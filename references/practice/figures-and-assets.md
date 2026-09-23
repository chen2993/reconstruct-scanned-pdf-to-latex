# 矢量图与资产

需要保留的图必须有可编译的矢量源码。本文件给出**按图形类型选手段**的策略、每种手段的落地方式，以及资产组织与逐图收敛的规则。

## 0. 先判类型，再选手段

不要用一种方法硬套所有图。先看图里**信息载体是什么**，再选：

| 图形类型 | 信息载体 | 手段 | 为什么 |
|---|---|---|---|
| 结构图、知识树、分类图 | 节点与层级 | **forest**（自动排版） | 只写节点嵌套，布局交给引擎；手工排坐标是最贵、最易错的做法 |
| 函数图像、区域、几何关系 | 曲线与坐标 | TikZ `plot` + 局部坐标系 | 可参数化，改一个系数全图跟着变 |
| 多子图（(a)(b)(c)(d)） | 同一套坐标的多种情形 | TikZ `scope` + `shift` | 共用一套坐标系与样式，只换参数 |
| 立体/3D 示意 | 投影后的线面 | TikZ 手工投影，**不用 3D 引擎** | 教材 3D 图是**画给人看的投影**，不是真实渲染 |
| 书法题字、校名、印章、手写签名 | 字形本身 | 从最高分辨率页**描摹成矢量轮廓** | 字形是内容，不能用相近字体代替 |
| 照片、连续色调、云纹渐变 | 像素 | **暂停并询问用户** | 无法诚实矢量化，不得塞入截图或位图 |

## 1. 结构图与知识树：用 forest，不要手排坐标

教材每章开头的「知识结构」通常是同一版面：矩形节点、直角折线连边、越深越窄、部分叶节点竖排。**这类图不要逐张手写坐标**——一张图几十个 `\node at (x,y)` 既难改又难对齐。

正确做法是在 `.cls` 里定义**一套共用样式**，各图只写节点数据：

```tex
% .cls：全书共用一套样式
\useforestlibrary{edges}
\forestset{
  booktree/.style={
    for tree={
      draw, rectangle, line width=0.4pt, inner sep=1.7pt,
      align=center, anchor=north, parent anchor=south, child anchor=north,
      edge={draw, line width=0.4pt},
      l sep=5.2mm, s sep=3.8mm,
    },
    forked edges,
  },
  % 叶节点多、横向挤不下时的紧凑变体
  booktreecompact/.style={booktree, for tree={s sep=1.2mm, l sep=4.6mm}},
}
```

```tex
% 图形模块：只写节点嵌套，不写坐标
\begin{forest}
  booktree,
  [多元函数积分学
    [概念与性质 [几何意义] [物理意义]]
    [二重积分 [直角坐标] [极坐标 [积分换序]] [换元法]]
  ]
\end{forest}
```

**两条实测陷阱**：

- **竖排节点不要用 style 实现**。三种写法实测比对：`content/.wrap value={\rotatebox…}` 会让节点渲染成**空框**（框在、字没了）；`tikz={\node[rotate=90]{…}}` 会在原节点上**再叠一个**节点、字重影。只有**把 `\rotatebox` 直接写进节点文本**是干净的：

  ```tex
  \newcommand{\bookv}[1]{\rotatebox[origin=c]{90}{\shortstack{#1}}}
  % 用法：[\bookv{交错\\级数}]
  ```

- **节点文本里有逗号要用双层花括号**。forest 会把逗号当节点选项分隔符，报一大批 `Missing \endcsname`（实测一棵树因此少报 91 个 error）。公式节点常含逗号：

  ```tex
  [{{\(y''=f(x,y')\) 型}}]
  ```

**超宽处理**：树宽随叶节点数变化，常会超出版心。用「先排版量宽、只有超宽才整体缩放」的环境包住，避免用 `\resizebox` 无条件缩放（那会把字号一起缩、破坏全书一致性）：

```tex
\newsavebox{\booktreebox}
\newlength{\booktreemaxwidth}
\newenvironment{booktreefit}[1][\textwidth]{%
  \setlength{\booktreemaxwidth}{#1}%
  \begin{lrbox}{\booktreebox}%
}{%
  \end{lrbox}%
  \ifdim\wd\booktreebox>\booktreemaxwidth
    \resizebox{\booktreemaxwidth}{!}{\usebox{\booktreebox}}%
  \else
    \usebox{\booktreebox}%
  \fi
}
```

这样绝大多数章不触发缩放、字号保持全书一致，只有个别叶节点特别多的章略小——与原书出版时的处理一致。

## 2. 函数图像：局部坐标系 + 参数化曲线

关键技巧是**在 `scope` 里换坐标系**：把「1 个数据单位 = 多少 mm」交给 TikZ，画图时直接用数学坐标，不必手算每个点的毫米值。

```tex
\begin{tikzpicture}[x=1mm, y=1mm,
  bookfigaxis/.style={line width=0.25mm},
  bookfigcurve/.style={line width=0.3mm},
  bookfigdash/.style={line width=0.25mm, dash pattern=on 1.3mm off 1.35mm},
  bookfigarrow/.style={line width=0.25mm, -{Latex[length=2.2mm,width=1.6mm]}},
]
  % 原点放在 (12,30)mm，1 个数据单位 = 20mm
  \begin{scope}[shift={(12,30)}, x=20mm, y=20mm]
    \draw[bookfigaxis] (-0.22,0) -- (1.28,0);
    \draw[bookfigarrow] (1.28,0) -- (1.40,0);
    \draw[bookfigcurve] plot[domain=0:1, samples=80, variable=\t] (\t,{\t*\t});
  \end{scope}
\end{tikzpicture}
```

要点：

- **曲线一律 `plot` 而不是手写折线**：`samples` 给够（曲线 60–80），改系数时形状自动跟上；
- **箭头单独画**：`\draw[axis]` 画轴线、`\draw[arrow]` 画带箭头的一小段，避免箭头把轴线末端变形；
- **区域阴影用「裁剪 + 网点」而不是灰色填充块**：原书常用网点（halftone）区分区域，直接 `\fill[black!12]` 会得到实心块，观感不符：

  ```tex
  \begin{scope}
    \clip (0.5,0.25) -- (1,1)
          plot[domain=1:0.5, samples=60, variable=\t] (\t,{\t*\t}) -- cycle;
    \foreach \px in {0.50,0.525,...,1.00}{%
      \foreach \py in {0.25,0.275,...,1.00}{%
        \fill[black!65] (\px,\py) circle (0.10mm);%
      }%
    }%
  \end{scope}
  ```

- **尺寸按原图实测**，不要凭感觉定比例。在模块注释里记下实测值（例如「1 个数据单位 ≈ 20mm、原点距页边 12mm/30mm」），后续修改才有依据。

## 3. 多子图：`scope` + `shift` 复用一套坐标

原书常见 `(a)(b)(c)(d)` 四种情形的对比图，它们是**同一套坐标系与样式**换参数。不要复制四遍代码，用 `scope` 平移：

```tex
\def\uu{12}
\def\dx{28}
\begin{scope}
  % (a) 情形一
\end{scope}
\begin{scope}[shift={(\dx,0)}]
  % (b) 情形二，坐标与样式沿用
\end{scope}
\begin{scope}[shift={(2*\dx,0)}]
  % (c)
\end{scope}
```

好处：改 `\uu`（单位尺寸）或 `\dx`（间距）时四个子图一起变；样式只在 `tikzpicture` 选项里定义一次。

## 4. 3D 立体图：手工投影，不用 3D 引擎

教材里的立体图（锥面、球面、坐标系）是**为读者画出来的投影示意**，不是真实渲染：线是干净的单线、可见与不可见部分靠虚实区分、比例经过作者简化。

因此**不要**引入需要真实渲染的 3D 方案（`pgfplots` 的 `axis` 环境、`surf`、TikZ 的 `3d` 库自动投影）：它们会追求几何正确，反而与原书那种"示意性投影"不符，而且轴与透视难与原件对齐。

**推荐做法**：把立体图当作**平面几何图**来画——自己定投影关系，用 `\coordinate` 标出关键点，用 `\draw`/`\draw[dashed]` 区分可见/被遮挡的线：

```tex
\def\X{14.0}   % 竖直对称线
\def\YO{34.0}  % 切点 O
\def\R{10.0}   % 大圆半径
\begin{tikzpicture}[x=1mm, y=1mm, line cap=round, line join=round]
  \coordinate (O)  at (\X, \YO);
  \coordinate (O1) at (\X, {\YO + \R});
  ...
  % 可见轮廓实线，被遮挡部分虚线
  \draw[line width=0.3mm] (O1) circle[radius=\R];
  \draw[line width=0.25mm, dash pattern=on 1.3mm off 1.35mm] ...
\end{tikzpicture}
```

关键点：

- **能用几何关系算出的点就不要手调**。例如公切线的切点位置由「两圆对锥顶位似」定出，把推导写进注释、用 `\def` 定义中间量，让坐标随参数变化：

  ```tex
  % T 由两圆对锥顶位似定出：|TO1|/|TO2| = R/r，且 |TO1|-|TO2| = R+r
  % 故 |TO1| = 40、|TO2| = 24，T_y = (YO - r) - 24
  \def\Ty{4.0}
  ```

- **虚实线是信息**，不是装饰：被遮挡的棱线必须用虚线，原图不画的线（例如原图没有带箭头的坐标轴）也不要自己加；
- **比例取自原图实测**，把实测值写进注释（例如 `R≈10.0mm、r≈6.0mm，r/R≈0.6`）；
- **辨认不出的元素不要猜着画**。原图里有几处无法辨认的元素（某个字母的含义、一条斜虚线、一段角弧）就**不画**，在交付说明里列出「未绘制项及原因」，而不是编一个看起来合理的版本。

## 5. 书法题字、校名、印章、手写签名

这类元素的**字形本身即内容**，不能用相近字体代替，也不要塞位图。做法是从原件最高分辨率页描摹成矢量轮廓，保留字形骨架与字距。

- 资产放独立目录（`latex/assets/`），用可复现的描摹脚本生成；**描摹脚本属于源码，必须保留**；
- 尺寸、颜色、位置由 `.cls` 的宏集中管理，不在页面里写死；
- 做**像素级复核**：量原字与矢量外接框的宽高和位置，多轮逼近到 1–2 px 量级。

## 6. 资产组织

- 图形主体：`latex/pages/figures/figure-<section>-<页号>-<序号>.tex`（如 `figure-pages-023-001.tex`；前后置图用 `figure-front-001-001.tex`）；
- 共用资产：`latex/assets/`（题字、蒙版、校徽、装饰）；
- 图形模块**不写**题注、编号、页码或位图；文件名里的页号只是源码元数据；
- 页面通过类文件的集中接口嵌入（参考 `\bookfiguremodule{figure-pages-023-001}`），不在页面源码里写 `\input{...}` 路径；缺失或重复的主体由类文件报错。

## 7. 逐图收敛

每个单元一次只实现一张图。

1. 先独立编译图形模块，再检查嵌入正文后的环绕与分页；
2. 逐图检查结构、标签、公式、连接关系、尺寸、基线、题注、环绕；
3. 反查正文：**原书没有的图号、题注和「见图 x.y」式引用必须删除**，不得由转写补造；
4. 达到 90% 后仍需人工复核，结果写入 `reviews/figures.md`；
5. 把「未绘制项、存疑项、与原书的差异」写进交付说明，而不是沉默略过。
