#!/usr/bin/env python3
"""Create the lightweight workspace for a scanned-book reconstruction."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


CONTROL_DIR = ".reconstruct-scanned-pdf-to-latex"

DIRECTORIES = (
    "docs",
    "latex/front",
    "latex/back",
    "latex/pages/figures",
    "asserts",
    "scripts",
    "dist",
    "tmp",
    f"{CONTROL_DIR}/extraced",
    f"{CONTROL_DIR}/reviews",
)

README = """# 扫描教材 LaTeX 重建项目

- `docs/`：项目说明；`class-api.md` 记录项目类文件的实际接口。
- `latex/`：从零实现的项目专用 `.cls`、前置页、正文、后置页和矢量图源码。
- `asserts/`：参考类文件、构建脚本或其他不属于正文事实的辅助资源。
- `.reconstruct-scanned-pdf-to-latex/`：最终页面标识、修正规则、样式卡片和复核材料。
- `dist/`：最终成品；`tmp/`：可删除的临时文件。

页面内容只通过运行环境的原生多模态能力读取，不使用 OCR 或 PDF 文字层提取。
项目专用 `.cls` 与根目录构建脚本应在分析原书后另行实现；初始化器不提供模板。
页面重编号脚本会生成正文逐页 `.tex`、按语义类型命名的前后置逻辑模块骨架和 `latex/main.tex` 导入入口；入口只用项目 `.cls` 的一条 `\\bookinput{1}{N}` 载入正文，但不会生成项目 `.cls`。前后置模块禁止使用 `front-xxx.tex`、`back-xxx.tex` 或其他页码式名称。
逐页源码和复核表使用 `front-xxx`、`pages-xxx`、`back-xxx` 页面标识及成品构建目标定位，不记录 PDF 物理页或逐页页码。
初始化后先逐页检查书内版权/出版/印刷信息是否标明开本或成品尺寸，再记录页数、方向、`MediaBox` 范围、资源类型、扫描边框和页面分型；印刷规格只用原生多模态能力读取，其他输入审计只读元数据、对象树和渲染图像，不读取文字层。
环境、命令、计数器、标签键和内部 API 必须使用英文 ASCII 标识符；中文只作为内容或显示文本的值。
完整书和做题本只使用同一个 `latex/main.tex`；构建脚本通过 driver 定义 `\\BookBuildOptions` 后再输入它，不能生成 `main-workbook.tex`。
全部可见内容（包括普通正文）必须由项目 `.cls` 已登记的语义环境或结构命令拥有，
不得在逐页源码顶层保留裸正文、公式、列表、表格或图形。
所有者可以按原件语义嵌套；直接父级关系与嵌套答案的显示规则记录在 `class-api.md`
和 `semantic-audit.json` 中。
项目源码和审核记录使用 Git 管理；可再生页图、编译缓存和成品默认不进入普通 Git 历史。
"""

GITIGNORE = """# 可从源 PDF 和配置重建的大体积页图
/.reconstruct-scanned-pdf-to-latex/extraced/
/.reconstruct-scanned-pdf-to-latex/*.png

# 构建缓存与成品
/tmp/
/dist/
/build/
*.aux
*.bbl
*.bcf
*.blg
*.dvi
*.fdb_latexmk
*.fls
*.idx
*.ilg
*.ind
*.log
*.out
*.run.xml
*.synctex.gz
*.toc
*.xdv
_minted-*/

# PDF 默认作为本地输入或外部发布附件；需要纳入版本控制时显式采用 Git LFS
*.pdf

# Python、编辑器与系统缓存
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.venv/
.vscode/
.idea/
.DS_Store
Thumbs.db
Desktop.ini
*.swp
*.swo
*~
"""

GITATTRIBUTES = """* text=auto eol=lf

*.md text eol=lf
*.tex text eol=lf diff=tex
*.cls text eol=lf diff=tex
*.sty text eol=lf diff=tex
*.bib text eol=lf
*.ps1 text eol=lf
*.psm1 text eol=lf
*.psd1 text eol=lf
*.py text eol=lf
*.json text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
.gitattributes text eol=lf
.gitignore text eol=lf

*.pdf binary
*.png binary
*.jpg binary
*.jpeg binary
*.tif binary
*.tiff binary
*.zip binary
*.woff binary
*.woff2 binary
*.ttf binary
*.otf binary
"""

CLASS_API = """# 项目类文件 API

本文件是待填写的实际接口记录骨架，在样式实现阶段与项目 `.cls` 同步维护。
只记录实际存在且已经编译验证的接口，不预先登记命令、环境或视觉样式。
`asserts/base.cls` 只可用于理解接口形状，不是项目模板、父类或视觉值来源。
环境、命令、计数器、标签键和内部 API 的名称必须是英文 ASCII 标识符；中文只能写入正文或显示文本值。

## 类文件

- 文件：待确定
- 基类与编译引擎：待确定
- 书内印刷规格证据（开本/成品尺寸/单位/最终页面标识）：待记录
- 经页面几何验证的原书纸张尺寸：待确认

## 所有者域

为每类事实指定唯一所有者；逐页文件、入口和图形模块不得复制 `.cls` 的共享职责。

| 所有者域 | 实际唯一所有者 | 允许的公共接口 | 禁止越界事项 | 编译验证 |
|---|---|---|---|---|
| 内容事实与语义边界 | 待填写 | 待填写 | 待填写 | 待验证 |
| 版式、环境外观与中央样式 | 待填写 | 待填写 | 待填写 | 待验证 |
| 计数器、显示模式与做题本状态 | 待填写 | 待填写 | 待填写 | 待验证 |
| 题注、标签、引用与媒体主体 | 待填写 | 待填写 | 待填写 | 待验证 |

## 页面加载

阶段 4 生成的唯一 `main.tex` 在 `\\documentclass` 前接收 driver 的 `\\BookBuildOptions`，再对前置页和后置页逐条写入原生 `\\input`，正文必须使用项目类文件的
`\\bookinput{1}{N}` 以一条范围调用导入全部 `pages/pages-xxx.tex`。前置页和后置页使用
`cover`、`dedication`、`toc`、`preface`、`afterword`、`references` 等经人工确认的语义类型文件名；禁止 `front-xxx`、`back-xxx` 或其他页码式模块名，一个模块可以自然扩展多页。
正文页使用 `pages/pages-xxx.tex`。在此记录正文范围、三位编号规则、导入顺序和缺页/非法范围的报错契约；
项目 `.cls` 不负责扫描或猜测页面文件，但必须按 `\\bookinput` 的显式范围加载对应正文页。

## 环境覆盖矩阵

全部最终可见内容都必须由已记录的语义环境或公共命令承载，普通正文也不得成为
无所有者的裸文本。所有者可按原件语义形成父子树；每个可见块只记录一个直接
所有者，子所有者先受父级内容是否展开约束，再执行自己的显示规则。按原件实际
角色逐项增删行；不存在的角色明确记为“不适用”。

| 可见内容角色 | 实际环境或命令 | 直接所有者域 | 允许的父所有者 | 显示条件 | 中央样式钩子 | 计数器 | 跨页契约 | 验证用例 |
|---|---|---|---|---|---|---|---|---|
| 普通正文 | 待填写 | 待填写 | 根/待填写 | 待填写 | 待填写 | 不适用或待填写 | 待填写 | 待验证 |
| 标题与知识块 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |
| 例题、习题及其他题目 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |
| 答案、解析、提示与证明 | 待填写 | 待填写 | 题目/待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |
| 图、表、题注、脚注及其他可见内容 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 所有者父子关系

逐项记录允许的父子组合和求值顺序。典型关系为题目包含答案、解析、提示和媒体；
答案包含步骤、评注和答案专属媒体。父级隐藏时子级不得单独出现；父级显示但子级
关闭时只隐藏子级。至少编译验证一个嵌套答案在完整书籍可见、做题本不可见。

| 父所有者 | 子所有者 | 是否允许 | 求值顺序 | 隐藏父级 | 隐藏子级 | 编译验证 |
|---|---|---|---|---|---|---|
| 题目 | 答案/解析/提示 | 待填写 | 父级后子级 | 子级不展开 | 题干保留 | 待验证 |

## 语义审计配置

`.reconstruct-scanned-pdf-to-latex/semantic-audit.json` 与本矩阵同步维护。阶段 6
把项目实际使用的所有者环境、`owner_parent_environments` 直接父级白名单、
`cross_page_owner_environments`、结构命令、内部布局环境、题目环境、答案环境和答案专属媒体写入配置；集合中的值是完整替换而非增量追加。白名单的键是子所有者，值是允许的直接父所有者数组，`$root` 表示根所有者。跨页集合只能登记同时位于所有者集合中的流式环境；审计器允许它们跨连续源码文件，但在完整输入结束时仍要求闭合。
每次公共接口变更后运行语义审计和常规编译复核，再把二者标记为已验证。

## 显示模式布尔组合

不得只记录模式名称。逐个记录原始布尔状态、组合或求值顺序，以及每类环境和媒体
的预期可见性；未实现的模式不写入本表。

| 实际模式 | 布尔状态与组合 | 可见环境 | 隐藏环境 | 媒体规则 | 编译用例 |
|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 中央样式钩子

记录 `.cls` 集中提供的字体、间距、边框、颜色、分页和媒体排版钩子。说明参数、
作用域和允许覆盖方式；逐页文件不得安装共享样式或全局钩子。

| 作用域 | 实际钩子 | 参数 | 所有者域 | 允许的局部覆盖 | 编译验证 |
|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 计数器与父级

每个显示编号都由 `.cls` 计数器产生。逐项记录父计数器、重置层级、步进位置、
显示格式、引用键约束，以及隐藏模式下是否仍推进；无编号角色明确记为“不适用”。

| 语义角色 | 实际计数器 | 父计数器与重置层级 | 步进位置 | 显示与引用格式 | 隐藏模式行为 | 编译验证 |
|---|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 跨页环境契约

对每种可跨页知识块和题目记录单一环境名、允许跨越的连续源码范围、初始化行为、
终止行为、计数器步进和错误行为。一个逻辑题只能编号一次；做题本答题区只能由唯一
的 `\\end{...}` 生成一次。可跨页环境必须是非捕获正文的流式实现，并以单条 `\\bookinput`
连续加载两个页面文件的最小夹具验证。

| 对象类型 | 环境 | `\\begin` 初始化 | `\\end` 行为 | 文件边界规则 | 编号/答题区契约 | 失败行为 | 验证用例 |
|---|---|---|---|---|---|---|---|
| 跨页知识块 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |
| 跨页题目 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 媒体所有权

记录正文必需媒体、答案专属媒体和矢量主体的唯一所有者。图形模块只提供可嵌入
主体；浮动体、题注、标签、引用、显示条件和编号的实际所有者须在此明确。

| 媒体角色 | 主体文件或接口 | 主体所有者 | 浮动体/题注/标签所有者 | 显示模式 | 答案归属 | 编译验证 |
|---|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 内容视图、做题本与答案隔离

记录实际存在的内容视图、题目范围、纸张 profile、主题和答题区接口。做题本必须
保留完整题干及解题必需媒体，同时隔离答案、解析、提示、证明和答案专属媒体；
未选题目不得产生答题区，跨页逻辑题也只能在唯一的 `\\end{...}` 产生一次答题区。
答案所有者可以嵌入题目，也可以作为同级后续块；记录通过父级上下文、最近题目类型
还是显式稳定键建立归属。每种分类视图都要验证不会显示其他题目域的答案；做题本
必须验证嵌套答案被隐藏，而外层题干和唯一答题区保留。

| 范围或视图 | 选择布尔条件 | 保留内容与媒体 | 隔离的答案所有者 | 答题区触发条件 | 编号/引用行为 | 编译验证 |
|---|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待验证 |

## 图形接口

记录矢量图占位、嵌入、题注、标签和答案专属图形接口。页面标识只作为源码注释和
复核元数据，不由图形模块输出到成品。
"""

PROGRESS = """# 重建进度

## 可复现输入

- 源 PDF 标识：待记录
- 源 PDF SHA-256：待记录
- 输入审计状态：待记录
- 书内印刷规格（原文/开本/成品尺寸/单位/最终页面标识）：待记录；阶段 4 后补写页面标识
- 页面方向与 `MediaBox` 范围（含尺寸漂移/异常结论）：待记录
- 页面资源类型与扫描边框结论：待记录
- 页面分型清单（仅记录实际存在的类型）：待记录
- 拆页策略（auto/embedded/render）：待记录
- 回退渲染 DPI：待记录
- 页面命名范围（front-xxx/pages-xxx/back-xxx）：待记录
- 项目类名：待记录

## 阶段

- [x] 01 文件树搭建
- [ ] 02 页面拆分
- [ ] 03 页面修正
- [ ] 04 页面重编号
- [ ] 05 样式总结与代表页选择
- [ ] 06 项目 `.cls` 实现
- [ ] 07 样式复核与人工确认
- [ ] 08 内容按页实现
- [ ] 09 矢量图实现
- [ ] 10 矢量图复核与人工确认
- [ ] 11 全书复核
- [ ] 12 编译、成品与做题本复核
- [ ] 13 补充材料
- [ ] 14 最终复核
"""

PAGE_CORRECTIONS = {"pages": {}}
SEMANTIC_AUDIT = {
    "owner_parent_environments": {},
    "cross_page_owner_environments": [],
}

STYLE_CARDS = """# 样式卡片

本文件只保存样式摘要，不复制页面。代表页使用最终标识 `front-xxx`、`pages-xxx` 或 `back-xxx`，不记录 PDF 物理页。

- 样式摘要版本：待填写；每次确认样式、`.cls` 接口或可见性契约后递增。

| 样式 ID | 页面分型 | 语义角色 | 环境或命令 | 视觉特征 | 辨识条件 | 显示模式 | 代表页标识 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 待填写 | 普通正文或其他类型 | 普通正文 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待覆盖 |
"""

REVIEW_FILES = {
    "style.md": (
        "# 样式复核\n\n"
        "| 代表页标识 | 源文件 | 成品构建目标 | 轮次 | 评分 | 剩余差异 | 人工结论 |\n"
        "|---|---|---|---:|---:|---|---|\n"
    ),
    "style-gaps.md": (
        "# 样式缺口\n\n"
        "内容填充中发现未登记样式时立即上报，由主执行者记录。未完成分类、类文件实现、代表页复核和重新发布样式摘要前，不得用最相近样式代替。\n\n"
        "| 缺口 ID | 发现时间 | 页面标识 | 可见特征 | 候选语义角色 | 受影响页面 | 状态 | `.cls`/API 处理 | 复核 | 结论 |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    ),
    "figures.md": (
        "# 矢量图复核\n\n"
        "| 图形 ID | 页面标识 | 页面源码 | 图形源码 | 成品构建目标 | 轮次/评分 | 状态 | 人工结论 |\n"
        "|---|---|---|---|---|---:|---|---|\n"
    ),
    "book.md": (
        "# 全书复核\n\n"
        "| 问题 ID | 页面标识 | 成品构建目标 | 问题 | 修正 | 复核结论 |\n"
        "|---|---|---|---|---|---|\n"
    ),
    "final.md": (
        "# 最终复核\n\n"
        "逐个记录最终 PDF 的文件名、页数、SHA-256、完整构建命令、"
        "已知差异和人工结论。\n"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建扫描教材 LaTeX 重建项目目录。")
    parser.add_argument("project", type=Path, help="要创建的项目目录")
    parser.add_argument(
        "--git",
        action="store_true",
        help="若不在现有 Git 工作树内，则初始化新仓库；不创建提交",
    )
    return parser.parse_args()


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def populate(stage: Path) -> None:
    for relative in DIRECTORIES:
        (stage / relative).mkdir(parents=True, exist_ok=True)
    write_text(stage / "README.MD", README)
    write_text(stage / ".gitignore", GITIGNORE)
    write_text(stage / ".gitattributes", GITATTRIBUTES)
    write_text(stage / "docs" / "class-api.md", CLASS_API)
    write_text(stage / CONTROL_DIR / "progress.md", PROGRESS)
    write_text(stage / CONTROL_DIR / "style-cards.md", STYLE_CARDS)
    for name, content in REVIEW_FILES.items():
        write_text(stage / CONTROL_DIR / "reviews" / name, content)
    write_text(
        stage / CONTROL_DIR / "page-corrections.json",
        json.dumps(PAGE_CORRECTIONS, ensure_ascii=False, indent=2) + "\n",
    )
    write_text(
        stage / CONTROL_DIR / "semantic-audit.json",
        json.dumps(SEMANTIC_AUDIT, ensure_ascii=False, indent=2) + "\n",
    )


def prepare_git(directory: Path, executable: str) -> str:
    probe = subprocess.run(
        [executable, "-C", str(directory), "rev-parse", "--show-toplevel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return "existing"
    subprocess.run(
        [executable, "-C", str(directory), "init"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=True,
    )
    return "initialized"


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    parent = project.parent
    parent.mkdir(parents=True, exist_ok=True)

    if project.is_symlink() or (project.exists() and not project.is_dir()):
        print(f"目标必须是不存在或为空的普通目录: {project}", file=sys.stderr)
        return 2
    if project.exists() and any(project.iterdir()):
        print(f"目标目录不为空: {project}", file=sys.stderr)
        return 2

    git_executable = shutil.which("git") if args.git else None
    if args.git and git_executable is None:
        print("未找到 Git；项目尚未创建。", file=sys.stderr)
        return 2

    stage = parent / f".{project.name}.init-{uuid.uuid4().hex}"
    empty_backup: Path | None = None
    git_mode: str | None = None
    try:
        stage.mkdir()
        populate(stage)
        if git_executable is not None:
            git_mode = prepare_git(stage, git_executable)
        if project.exists():
            empty_backup = parent / f".{project.name}.empty-{uuid.uuid4().hex}"
            os.replace(project, empty_backup)
        os.replace(stage, project)
        if empty_backup is not None and empty_backup.exists():
            try:
                empty_backup.rmdir()
            except OSError as cleanup_error:
                print(f"警告：无法清理空目录备份 {empty_backup}: {cleanup_error}", file=sys.stderr)
            empty_backup = None
    except Exception as exc:
        if empty_backup is not None and empty_backup.exists() and not project.exists():
            os.replace(empty_backup, project)
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        print(f"初始化失败，未保留半成品: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"项目已创建: {project}")
    if git_mode == "initialized":
        print("Git: 已初始化新仓库；尚未创建提交。")
    elif git_mode == "existing":
        print("Git: 已沿用上级工作树；未创建嵌套仓库。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
