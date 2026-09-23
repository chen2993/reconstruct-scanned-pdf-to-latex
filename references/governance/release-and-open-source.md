# 发布与开源

重建项目完成后，用户可能要求**推送到 GitHub 等远端**或**开源**。这一步涉及他人的著作权，因此本文件的规则与其它阶段不同：**agent 不做权利判断，只做产物准备与泄漏检查**。

## 0. 两条硬规则

1. **是否开源必须询问人类**。agent 可以准备产物、可以推送到用户指定的远端，但"这个仓库是否公开"必须由用户明确回答后才能执行；不得自行把仓库设为 public，不得自行选择开源许可证。
2. **扫描件与页图绝不能进入版本控制**。原书扫描、页图渲染、提取的图片都是**本地 QA 输入**，不是项目源码。一旦进了 Git 历史，删除后仍可从历史恢复，属于既成事实的再分发。

## 1. 权利边界：三类材料，三种地位

重建成品是**他人著作的衍生**，所以不能给一个裸许可证覆盖全部。必须先分类：

| 类别 | 内容 | 能否授权 | 处理 |
|---|---|---|---|
| **A 项目自有** | 构建脚本、审计工具、独立实现的可复用 `.cls` 基础设施、原创维护文档 | ✅ 可以 | 由项目 LICENSE 覆盖 |
| **B 源生内容** | 重建的正文、例题、解答、插图、版式、前言等由原书衍生或选择编排的部分 | ❌ 不可以 | 明确列为"排除材料" |
| **C 第三方** | 原书扫描、页图渲染、外部参考工程、字体、TeX 宏包、书名与商标 | ❌ 不可以 | 只作本地输入，不得进入仓库或发布包 |

**成品 PDF 是最容易判断错的**：它把 A 与 B 混在一起，因此**不能整体按项目许可证授权**。

## 2. 决策门：先问人类

发布前必须向用户确认三件事，不能替用户决定：

1. **发布范围**：只发布工具链（A + 空的源码骨架），还是连同重建内容（B）？
2. **权利状态**：若含 B，用户是否已获得原书权利人许可？（未获许可只能私有或只发布 A）
3. **可见性**：私有仓库、公开仓库，还是先本地提交不推远端？

在用户明确回答前，**只能停在本地产物准备**。

## 3. 四件产物

### `.gitignore`：必须在首次提交之前就位

扫描件一旦被提交，事后删除仍留在历史里。所以 `.gitignore` 要在第一次 `git add` 之前写好：

```gitignore
# 本地 QA 输入：原书扫描、页图渲染、外部参考工程
/reference/
/references/
/sources/
/dist/
/tmp/
/.reconstruct-scanned-pdf-to-latex/*.png

# 构建缓存
*.aux  *.log  *.out  *.toc  *.synctex.gz  *.fls  *.fdb_latexmk  *.xdv

# 本地工具与编辑器元数据
/.agents/
/.codex/
__pycache__/
.pytest_cache/
.ruff_cache/
.vscode/
.idea/
.DS_Store
Thumbs.db
```

注意：**`.reconstruct-scanned-pdf-to-latex/*.png` 是必删项**——那正是最终页面标识对应的页图。

### `LICENSE`：带范围声明

不能只写标准 MIT/Apache 正文。开头要加**范围声明**，明确只覆盖 A 类，并指向 `NOTICE.md`：

```text
<许可证名>

Scope notice

This license applies only to material independently authored for this repository
as software or project infrastructure, including build and validation tooling,
reusable LaTeX class infrastructure, and original maintenance documentation, in
each case only to the extent that the repository contributors have the right to
license that material.

This license does not apply to the reconstructed book text, source-aligned front
matter, exercises, solutions, mathematical exposition, reconstructed
illustrations or page designs, source scans, reference documents, third-party
fonts, names, marks, or other third-party material. Compiled book PDFs combine
project infrastructure with excluded content and are not licensed as a whole
under this license. See NOTICE.md for the repository's content and dependency
boundaries.

<许可证正文>
```

### `NOTICE.md`：列出边界

至少四节：

1. **项目自有材料**（受 LICENSE 覆盖）——逐项列明，含"可复用部分"的限定语（`latex/<class>.cls` 里可能有源生设计，须说明）；
2. **排除材料**——重建正文、插图、版式、扫描、外部参考、第三方名称与字体、成品 PDF；
3. **依赖**——TeX Live、XeLaTeX、latexmk、字体等各自保留自己的许可证，不因本仓库而重新授权；
4. **本地输入**——明确外部扫描与参考工程只作本地 QA，不得进入源码包、发布包或公开历史。

### `README.md`：让陌生人能构建

至少包含：项目简介、权利提示（一段话 + 指向 NOTICE）、环境要求（引擎与字体）、快速构建（一条命令）、目录结构、构建脚本用法。

## 4. 双通道打包

源码包与发布包**法律地位不同**，必须分开：

| 通道 | 内容 | 不含 |
|---|---|---|
| **源码包** | LaTeX 源码、脚本、`LICENSE`、`NOTICE.md`、`README` | 扫描件、页图、构建缓存、成品 PDF |
| **发布包** | 通过审计的成品 PDF、`README`、`LICENSE`、`NOTICE.md` | 扫描件、参考资料、源码缓存 |

两个包都应附带**文件清单与 SHA-256 校验文件**。发布包里放 PDF **不扩大许可证授予范围**——这一点要在 `NOTICE.md` 里写明。

## 5. 推送到远端

用户指定远端后：

```powershell
git -C <project> remote add origin <url>
git -C <project> branch -M main
git -C <project> push -u origin main
```

- 推送前先跑第 6 节的泄漏审计；
- **不要自行决定仓库可见性**，也不要自行创建公开仓库；
- 强制推送、改写历史需要用户明确同意：如果历史里已经混入扫描件，改写历史是唯一彻底的补救，但这属于破坏性操作，必须由用户决定；
- 若历史已含扫描件且用户不同意改写历史，如实说明"这些文件仍在历史中可被恢复"，并建议改为新仓库重新开始。

## 6. 发布前泄漏审计

提交或推送之前，必须核对版本控制里**没有**本地输入。检查项：

1. `git ls-files` 里没有 `.png`/`.jpg`/`.jpeg`/`.tif`/`.pdf` 形式的页图或扫描；
2. 没有被跟踪的 `reference/`、`references/`、`sources/` 内容；
3. `dist/` 下只有经用户确认要发布的成品（或干脆不提交 `dist/`）；
4. `.gitignore` 覆盖上述所有路径；
5. `LICENSE` 与 `NOTICE.md` 同时存在——**源码包或发布包缺任一都不合格**。

`scripts/audit_release.py` 自动完成这五项检查。发现页图/扫描被跟踪时它返回失败，并列出具体路径供人工处理，**不自行删除**（历史问题需要人工决定处理方式）。

## 7. 与其它阶段的关系

- 发布是**可选阶段**，由用户显式触发；用户没提就不要做；
- 本阶段不改变前面任何产物，只新增仓库级文件与检查；
- `LICENSE`/`NOTICE.md` 的措辞属于法律文本，agent 提供**模板与边界清单**，最终内容由用户确认。
