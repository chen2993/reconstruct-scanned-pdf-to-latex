# Git 工作流

Git 保存可审查的源码、决策和审核结论，不保存中间拆页、联系表、缓存或成品 PDF。项目位于现有工作树时沿用它，不创建嵌套仓库。

## 提交前检查

```powershell
git -C <project> status --short
git -C <project> diff --check
git -C <project> diff -- <paths>
git -C <project> add -- <exact-paths>
git -C <project> diff --cached --check
git -C <project> diff --cached
git -C <project> commit -m "<message>"
```

不使用 `git add -A`、`git commit -a`、`stash`、强制检出、硬重置或历史重写来处理他人改动。并行执行单元不操作暂存区、提交、标签或历史，只有主执行者在验收后提交。

## 提交消息

格式固定为：

```text
<actor><area> action
```

- `actor` 为 `agent` 或 `human`；
- `area` 为 `init`、`pages`、`style`、`class`、`content`、`figure`、`book`、`build`、`docs`、`release` 或 `fix`；
- 内容批次带页面范围，例如 `<agent><content> transcribe pages 001-010`；
- 人工结论单独提交，例如 `<human><class> approved`、`<human><content> pages 001-010 accepted`；
- 图形使用稳定文件 ID，例如 `<agent><figure> reconstruct figure-pages-023-001`。

## 检查点

| 阶段 | 提交内容 | 示例 |
|---|---|---|
| 1 | 目录、Git 边界文件、API 和状态骨架 | `<agent><init> initialize reconstruction workspace` |
| 2-4 | 修正规则、最终页面命名、入口和页面骨架 | `<agent><pages> scaffold source pages` |
| 5-7 | 样式卡片、项目 `.cls`、API、样式复核 | `<agent><class> implement source matched layout` |
| 8 | 已三轮复核的连续内容批次 | `<agent><content> transcribe pages 001-010` |
| 9-10 | 已复核矢量图和图形表 | `<agent><figure> reconstruct figure-pages-023-001` |
| 11-12 | 全书修正、构建脚本和矩阵复核 | `<agent><build> verify book and workbook matrix` |
| 13-14 | 新增说明、最终复核和发布结论 | `<agent><release> finalize reconstructed sources` |

人工明确确认后才创建审核标签。标签只标记已提交、工作树干净且人工已审核的状态。
