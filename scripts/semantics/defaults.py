"""默认的语义所有者、结构命令、媒体环境与禁用命令集合。"""

from __future__ import annotations

import re


# Hyphens are valid in filenames, but not in custom LaTeX environment,
# command, counter, or configuration identifiers. Standard LaTeX layout
# environments have a separate starred form (for example ``figure*``), so the
# source parser accepts one trailing star while semantic configuration sets
# remain strict identifiers.
IDENTIFIER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
ENVIRONMENT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\*)?")
MODULE_FILENAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
PAGE_LIKE_MODULE = re.compile(
    r"^(?:front|back|page|pages)(?:[-_]?\d+)?$|^(?:front|back)[-_].*$",
    re.IGNORECASE,
)


DEFAULT_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookfrontmatterblock",
        "bookbackmatterblock",
        "booksupplement",
        "bookbody",
        "booktext",
        "bookexposition",
        "textbookexposition",
        "bookknowledgeprose",
        "knowledgeprose",
        "bookknowledgeblock",
        "knowledgeblock",
        "bookdefinition",
        "booktheorem",
        "booklemma",
        "bookproposition",
        "bookcorollary",
        "bookproperty",
        "bookconcept",
        "bookproof",
        "bookexample",
        "bookexercise",
        "bookquestion",
        "bookanswer",
        "booksolution",
        "bookanalysis",
        "bookhint",
        "bookmethodstep",
        "bookproofstep",
        "bookanalysisstep",
        "booksolutionstep",
        "bookcase",
        "bookremark",
        "booknote",
        "booktip",
        "bookwarning",
        "booksummary",
        "bookfigure",
        "booktable",
        "bookalgorithm",
        "bookequation",
        "bookformula",
    }
)

DEFAULT_STRUCTURE_COMMANDS = frozenset(
    {
        "bookpart",
        "bookchapter",
        "booksection",
        "booksubsection",
        "booksubsubsection",
        "bookparagraph",
    }
)

# 前后置模块可以在顶层直接调用的集中接口；它们由 .cls 实现，参数形状各不相同，
# 因此审计器只放行，不按结构命令那样要求固定花括号参数。
DEFAULT_STANDALONE_COMMANDS = frozenset(
    {
        "bookmaketoc",
        "bookbookmarkmodule",
        "booksetoriginalpagesize",
        "booksourcepage",
    }
)

# 这些是内部布局或媒体组件，不是语义所有者，必须继承外层所有者。
DEFAULT_MEDIA_ENVIRONMENTS = frozenset(
    {
        "figure",
        "figure*",
        "table",
        "table*",
        "tabular",
        "tabular*",
        "tabularx",
        "longtable",
        "tikzpicture",
        "axis",
        "algorithm",
        "algorithmic",
        "equation",
        "equation*",
        "align",
        "align*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "displaymath",
        "itemize",
        "enumerate",
        "description",
        "quote",
        "quotation",
        "verse",
        "minipage",
        "center",
        "flushleft",
        "flushright",
        "answerfigure",
        "solutionfigure",
        "bookanswerfigure",
        "booksolutionfigure",
    }
)

DEFAULT_ANSWER_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookanswer",
        "booksolution",
        "bookanalysis",
        "bookhint",
        "bookmethodstep",
        "bookproofstep",
        "bookanalysisstep",
        "booksolutionstep",
        "bookcase",
    }
)

DEFAULT_QUESTION_OWNER_ENVIRONMENTS = frozenset(
    {
        "bookexample",
        "bookexercise",
        "bookquestion",
    }
)

DEFAULT_ANSWER_MEDIA_ENVIRONMENTS = frozenset(
    {"answerfigure", "solutionfigure", "bookanswerfigure", "booksolutionfigure"}
)

DEFAULT_CROSS_PAGE_OWNER_ENVIRONMENTS = frozenset()

# 页面和前后置源码不得自行插入目录条目、书签、手工计数器或复用入口命令。
# 这些职责属于项目 .cls 的集中接口；出现即视为硬编码，而不是普通排版问题。

DEFAULT_FORBIDDEN_COMMANDS = frozenset(
    {
        "addcontentsline",
        "addtocontents",
        "tableofcontents",
        "setcounter",
        "stepcounter",
        "pdfbookmark",
        "currentpdfbookmark",
        "belowpdfbookmark",
        "bookmark",
        "input",
        "include",
    }
)
