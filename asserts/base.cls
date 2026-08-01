% Reference only. Start each project class from a blank file.
% Reuse interface shapes when helpful; replace every visual choice from source pages.
% Public environment, command, counter, label, and internal API names are
% English ASCII identifiers; role macros may expand to localized display text.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{base}[2026/08/01 Semantic scanned-book class contract]

\makeatletter

% The reference class accepts the same single-entry option shape used by the
% generated main.tex.  A project class may extend these options or replace the
% visual implementation, but it should keep the axes independent.
\newcommand{\book@initialmode}{full}
\newcommand{\book@initialscope}{all}
\newcommand{\book@initialprofile}{a4}
\newcommand{\book@initialtheme}{print}
\DeclareOption{book}{\renewcommand{\book@initialmode}{full}}
\DeclareOption{workbook}{\renewcommand{\book@initialmode}{workbook}}
\DeclareOption{examples}{\renewcommand{\book@initialscope}{examples}}
\DeclareOption{exercises}{\renewcommand{\book@initialscope}{exercises}}
\DeclareOption{all}{\renewcommand{\book@initialscope}{all}}
\DeclareOption{original}{\renewcommand{\book@initialprofile}{original}}
\DeclareOption{a4}{\renewcommand{\book@initialprofile}{a4}}
\DeclareOption{pad11}{\renewcommand{\book@initialprofile}{pad11}}
\DeclareOption{pad13}{\renewcommand{\book@initialprofile}{pad13}}
\DeclareOption{print}{\renewcommand{\book@initialtheme}{print}}
\DeclareOption{eyecare}{\renewcommand{\book@initialtheme}{eyecare}}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{ctexbook}}
\ProcessOptions\relax

\LoadClass[UTF8,openany]{ctexbook}
\RequirePackage{amsmath,amssymb}
\RequirePackage{environ}
\RequirePackage{etoolbox}
\RequirePackage{geometry}
\RequirePackage{xcolor}

% --------------------------------------------------------------------------
% Front and back modules are explicit in main.tex. Body pages may use \bookinput
% so a class can load pages/pages-001.tex through pages/pages-999.tex in order.
% File names may contain hyphens; command and environment names below do not.
% --------------------------------------------------------------------------

\newcount\book@inputpage
\newcount\book@inputlastpage
\newcommand{\bookinput}[2]{%
  \book@inputpage=#1\relax
  \book@inputlastpage=#2\relax
  \book@inputnext
}
\newcommand{\book@inputnext}{%
  \ifnum\book@inputpage<10
    \edef\book@inputfilename{pages/pages-00\number\book@inputpage}%
  \else\ifnum\book@inputpage<100
    \edef\book@inputfilename{pages/pages-0\number\book@inputpage}%
  \else
    \edef\book@inputfilename{pages/pages-\number\book@inputpage}%
  \fi\fi
  \input{\book@inputfilename}%
  \ifnum\book@inputpage<\book@inputlastpage
    \advance\book@inputpage by 1\relax
    \expandafter\book@inputnext
  \fi
}
\let\bookinputpages\bookinput

% --------------------------------------------------------------------------
% Semantic visibility. Every visible block has one direct owner and may inherit
% visibility from registered ancestor owners.
% --------------------------------------------------------------------------
\newif\ifbook@showstructure
\newif\ifbook@showmatter
\newif\ifbook@showbody
\newif\ifbook@showknowledge
\newif\ifbook@showproofs
\newif\ifbook@showquestions
\newif\ifbook@showanswers
\newif\ifbook@showcommentary
\newif\ifbook@showmedia
\newif\ifbook@workbook
\newif\ifbook@workbooksectionbreak
\newif\ifbook@selectedquestion
\newif\ifbook@selectedanswer
\newif\ifbook@insideknowledge
\newif\ifbook@insidequestion
\newif\ifbook@insideanswer
\newcommand{\book@questionfilter}{all}
\newcommand{\book@workbookscope}{all}
\newcommand{\book@currentquestionkind}{none}
\newcommand{\book@workbookstyle}{normal}

\newcommand{\book@hideall}{%
  \book@showstructurefalse
  \book@showmatterfalse
  \book@showbodyfalse
  \book@showknowledgefalse
  \book@showproofsfalse
  \book@showquestionsfalse
  \book@showanswersfalse
  \book@showcommentaryfalse
  \book@showmediafalse
  \book@workbookfalse
  \def\book@questionfilter{all}%
}

\newcommand{\book@mode@full}{%
  \book@showstructuretrue
  \book@showmattertrue
  \book@showbodytrue
  \book@showknowledgetrue
  \book@showproofstrue
  \book@showquestionstrue
  \book@showanswerstrue
  \book@showcommentarytrue
  \book@showmediatrue
}
\let\book@mode@all\book@mode@full

\newcommand{\book@mode@body}{%
  \book@showstructuretrue
  \book@showbodytrue
  \book@showcommentarytrue
  \book@showmediatrue
}

\newcommand{\book@mode@knowledge}{%
  \book@showstructuretrue
  \book@showknowledgetrue
  \book@showproofstrue
  \book@showmediatrue
}
\let\book@mode@definitions\book@mode@knowledge

\newcommand{\book@mode@questions}{%
  \book@showstructuretrue
  \book@showquestionstrue
  \book@showmediatrue
  \def\book@questionfilter{all}%
}

\newcommand{\book@mode@examples}{%
  \book@showstructuretrue
  \book@showquestionstrue
  \book@showanswerstrue
  \book@showproofstrue
  \book@showmediatrue
  \def\book@questionfilter{examples}%
}

\newcommand{\book@mode@exercises}{%
  \book@showstructuretrue
  \book@showquestionstrue
  \book@showanswerstrue
  \book@showproofstrue
  \book@showmediatrue
  \def\book@questionfilter{exercises}%
}

\newcommand{\book@mode@solutions}{%
  \book@showstructuretrue
  \book@showquestionstrue
  \book@showanswerstrue
  \book@showproofstrue
  \book@showmediatrue
  \def\book@questionfilter{all}%
}
\let\book@mode@answers\book@mode@solutions

\newcommand{\book@mode@workbook}{%
  \book@showstructuretrue
  \book@showmediatrue
  \book@workbooktrue
}

\newcommand{\booksetcontentmode}[1]{%
  \edef\book@requestedmode{#1}%
  \book@hideall
  \ifcsdef{book@mode@\book@requestedmode}{%
    \csuse{book@mode@\book@requestedmode}%
  }{%
    \ClassError{base}{Unknown content mode `\book@requestedmode'}%
      {Use full, body, knowledge, questions, examples, exercises, solutions, or workbook.}%
  }%
}

\newcommand{\booksetworkbookscope}[1]{%
  \edef\book@requestedscope{#1}%
  \ifdefstring{\book@requestedscope}{examples}{\def\book@workbookscope{examples}}{%
    \ifdefstring{\book@requestedscope}{exercises}{\def\book@workbookscope{exercises}}{%
      \ifdefstring{\book@requestedscope}{all}{\def\book@workbookscope{all}}{%
        \ClassError{base}{Unknown workbook scope `\book@requestedscope'}%
          {Use examples, exercises, or all.}%
      }%
    }%
  }%
}

% Optional workbook axes. A project class decides the actual geometry and
% heading treatment; these setters keep configuration orthogonal and make
% unsupported values fail instead of silently changing the full-book view.
\newcommand{\booksetworkbookstyle}[1]{%
  \edef\book@requestedworkbookstyle{#1}%
  \ifdefstring{\book@requestedworkbookstyle}{simple}{%
    \def\book@workbookstyle{simple}%
  }{\ifdefstring{\book@requestedworkbookstyle}{normal}{%
    \def\book@workbookstyle{normal}%
  }{%
    \ClassError{base}{Unknown workbook style `\book@requestedworkbookstyle'}%
      {Use simple or normal.}%
  }}%
}

\newcommand{\booksetworkbooksectionbreak}[1]{%
  \edef\book@requestedsectionbreak{#1}%
  \ifdefstring{\book@requestedsectionbreak}{true}{%
    \book@workbooksectionbreaktrue
  }{\ifdefstring{\book@requestedsectionbreak}{false}{%
    \book@workbooksectionbreakfalse
  }{%
    \ClassError{base}{Unknown workbook section-break value `\book@requestedsectionbreak'}%
      {Use true or false.}%
  }}%
}

\newcommand{\bookifworkbookstyle}[2]{%
  \ifdefstring{\book@workbookstyle}{simple}{#1}{#2}%
}

\newcommand{\bookifworkbooksectionbreak}[1]{%
  \ifbook@workbooksectionbreak #1\fi
}

% Public conditional used by the single main.tex entry point.  The project
% class may provide a richer equivalent, but the name must remain English.
\newcommand{\bookifworkbook}[2]{%
  \ifbook@workbook #1\else #2\fi
}

\newcommand{\book@selectquestionkind}[1]{%
  \gdef\book@currentquestionkind{#1}%
  \book@selectedquestionfalse
  \ifbook@workbook
    \ifdefstring{\book@workbookscope}{all}{\book@selectedquestiontrue}{%
      \ifdefstring{\book@workbookscope}{#1}{\book@selectedquestiontrue}{}%
    }%
  \else
    \ifbook@showquestions
      \ifdefstring{\book@questionfilter}{all}{\book@selectedquestiontrue}{%
        \ifdefstring{\book@questionfilter}{#1}{\book@selectedquestiontrue}{}%
      }%
    \fi
  \fi
}

\newcommand{\book@selectexample}{\book@selectquestionkind{examples}}
\newcommand{\book@selectexercise}{\book@selectquestionkind{exercises}}
\newcommand{\book@selectgenericquestion}{%
  \gdef\book@currentquestionkind{questions}%
  \book@selectedquestionfalse
  \ifbook@workbook
    \ifdefstring{\book@workbookscope}{all}{\book@selectedquestiontrue}{}%
  \else
    \ifbook@showquestions\book@selectedquestiontrue\fi
  \fi
}

\newcommand{\book@selectanswer}{%
  \book@selectedanswerfalse
  \ifbook@showanswers
    \ifdefstring{\book@questionfilter}{all}{\book@selectedanswertrue}{%
      \ifdefstrequal{\book@questionfilter}{\book@currentquestionkind}{%
        \book@selectedanswertrue
      }{}%
    }%
  \fi
}

% --------------------------------------------------------------------------
% Central vocabulary and style hooks. Project classes redefine these hooks.
% --------------------------------------------------------------------------
\newcommand{\bookrolebody}{正文}
\newcommand{\bookrolefrontmatter}{前置内容}
\newcommand{\bookrolebackmatter}{后置内容}
\newcommand{\bookrolesupplement}{补充内容}
\newcommand{\bookroleknowledge}{知识}
\newcommand{\bookroledefinition}{定义}
\newcommand{\bookroletheorem}{定理}
\newcommand{\bookrolelemma}{引理}
\newcommand{\bookroleproposition}{命题}
\newcommand{\bookrolecorollary}{推论}
\newcommand{\bookroleproperty}{性质}
\newcommand{\bookroleconcept}{概念}
\newcommand{\bookroleproof}{证明}
\newcommand{\bookroleexample}{例}
\newcommand{\bookroleexercise}{习题}
\newcommand{\bookrolequestion}{问题}
\newcommand{\bookroleanswer}{答案}
\newcommand{\bookrolesolution}{解答}
\newcommand{\bookroleanalysis}{分析}
\newcommand{\bookrolehint}{提示}
\newcommand{\bookroleremark}{注}
\newcommand{\bookrolenote}{说明}
\newcommand{\bookroletip}{技巧}
\newcommand{\bookrolewarning}{注意}
\newcommand{\bookrolesummary}{小结}
\newcommand{\bookrolemethod}{方法}
\newcommand{\bookrolestep}{步骤}
\newcommand{\bookrolecase}{情形}
\newcommand{\bookrolefigure}{图}
\newcommand{\bookroletable}{表}
\newcommand{\bookrolealgorithm}{算法}

\newcommand{\bookstylelabel}[1]{\textbf{#1}}
\newcommand{\bookstylestructure}[2]{#1{#2}}
\newcommand{\bookstylebody}[1]{#1}
\newcommand{\bookstylematter}[3]{%
  \par\medskip\noindent
  \ifstrempty{#2}{}{\bookstylelabel{#1}\space\bookstylelabel{#2}\par\smallskip}%
  \bookstylebody{#3}\par\medskip
}
\newcommand{\bookstyleknowledge}[4]{%
  \par\medskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
  \ifstrempty{#3}{}{\space（#3）}%
  \quad\bookstylebody{#4}\par\medskip
}
\newcommand{\bookstylequestion}[4]{%
  \par\medskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
  \ifstrempty{#3}{}{\space（#3）}%
  \quad\bookstylebody{#4}\par
}
\newcommand{\bookstyleanswer}[3]{%
  \par\smallskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space（#2）}%
  \quad\bookstylebody{#3}\par\smallskip
}
\newcommand{\bookstylecommentary}[3]{%
  \par\smallskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space（#2）}%
  \quad\bookstylebody{#3}\par\smallskip
}
\newcommand{\bookstylemedia}[4]{%
  \par\medskip\noindent #4%
  \ifstrempty{#3}{}{%
    \par\smallskip\noindent
    \bookstylelabel{#1}%
    \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
    \space #3%
  }%
  \par\medskip
}
\newcommand{\bookstyleequation}[1]{\begin{equation}#1\end{equation}}

% --------------------------------------------------------------------------
% Visibility-aware renderers. Owners may form a semantic tree. A parent controls
% expansion; nested body blocks inherit context and specialized children apply
% their own visibility rule.
% --------------------------------------------------------------------------
\newcommand{\book@renderbody}[1]{%
  \ifbook@showbody
    \bookstylebody{#1}%
  \else\ifbook@insideknowledge
    \bookstylebody{#1}%
  \else\ifbook@insidequestion
    \bookstylebody{#1}%
  \else\ifbook@insideanswer
    \bookstylebody{#1}%
  \fi\fi\fi\fi
}

\newcommand{\book@renderknowledge}[4]{%
  \ifbook@showknowledge
    \begingroup
      \book@insideknowledgetrue
      \bookstyleknowledge{#1}{#2}{#3}{#4}%
    \endgroup
  \fi
}

\newcommand{\book@renderknowledgeprose}[1]{%
  \ifbook@showknowledge
    \begingroup
      \book@insideknowledgetrue
      \bookstylebody{#1}%
    \endgroup
  \fi
}

\newcommand{\book@rendermatter}[3]{%
  \ifbook@showmatter
    \bookstylematter{#1}{#2}{#3}%
  \fi
}

\newcommand{\book@renderproof}[2]{%
  \ifbook@showproofs
    \begingroup
      \book@insideknowledgetrue
      \bookstyleanswer{\bookroleproof}{#1}{#2}%
    \endgroup
  \fi
}

\newcommand{\book@renderquestionsegment}[4]{%
  \ifbook@selectedquestion
    \begingroup
      \book@insidequestiontrue
      \bookstylequestion{#1}{#2}{#3}{#4}%
    \endgroup
  \fi
}

\newcommand{\book@renderquestionterminal}[4]{%
  \book@renderquestionsegment{#1}{#2}{#3}{#4}%
  \ifbook@selectedquestion
    \ifbook@workbook\book@answerspace\fi
  \fi
}

\newcommand{\book@renderanswer}[3]{%
  \book@selectanswer
  \ifbook@selectedanswer
    \begingroup
      \book@insideanswertrue
      \bookstyleanswer{#1}{#2}{#3}%
    \endgroup
  \fi
}

\newcommand{\book@rendercommentary}[3]{%
  \ifbook@showcommentary
    \bookstylecommentary{#1}{#2}{#3}%
  \fi
}

\newcommand{\book@rendermedia}[4]{%
  \ifbook@showmedia
    \bookstylemedia{#1}{#2}{#3}{#4}%
  \fi
}

% --------------------------------------------------------------------------
% Counter-owned semantic environments. Projects may add roles, not bypass them.
% --------------------------------------------------------------------------
\newcounter{bookdefinition}[chapter]
\newcounter{booktheorem}[chapter]
\newcounter{booklemma}[chapter]
\newcounter{bookproposition}[chapter]
\newcounter{bookcorollary}[chapter]
\newcounter{bookproperty}[chapter]
\newcounter{bookconcept}[chapter]
\newcounter{bookexample}[chapter]
\newcounter{bookexercise}[chapter]
\newcounter{bookquestion}[chapter]
\newcounter{bookfigure}[chapter]
\newcounter{booktable}[chapter]
\newcounter{bookalgorithm}[chapter]
\newcounter{bookmethodstep}[bookexample]
\newcounter{bookproofstep}[bookexample]
\newcounter{bookanalysisstep}[bookexample]
\newcounter{booksolutionstep}[bookexample]
\newcounter{bookcase}[bookquestion]

% These child sequences may belong to an example, exercise, or generic question.
% Reset them centrally whenever a new logical question starts.
\newcommand{\book@resetquestionchildren}{%
  \setcounter{bookmethodstep}{0}%
  \setcounter{bookproofstep}{0}%
  \setcounter{bookanalysisstep}{0}%
  \setcounter{booksolutionstep}{0}%
  \setcounter{bookcase}{0}%
}

\newcommand{\book@chaptercounterformat}[1]{\thechapter.\arabic{#1}}
\renewcommand{\thebookdefinition}{\book@chaptercounterformat{bookdefinition}}
\renewcommand{\thebooktheorem}{\book@chaptercounterformat{booktheorem}}
\renewcommand{\thebooklemma}{\book@chaptercounterformat{booklemma}}
\renewcommand{\thebookproposition}{\book@chaptercounterformat{bookproposition}}
\renewcommand{\thebookcorollary}{\book@chaptercounterformat{bookcorollary}}
\renewcommand{\thebookproperty}{\book@chaptercounterformat{bookproperty}}
\renewcommand{\thebookconcept}{\book@chaptercounterformat{bookconcept}}
\renewcommand{\thebookexample}{\book@chaptercounterformat{bookexample}}
\renewcommand{\thebookexercise}{\book@chaptercounterformat{bookexercise}}
\renewcommand{\thebookquestion}{\book@chaptercounterformat{bookquestion}}
\renewcommand{\thebookfigure}{\book@chaptercounterformat{bookfigure}}
\renewcommand{\thebooktable}{\book@chaptercounterformat{booktable}}
\renewcommand{\thebookalgorithm}{\book@chaptercounterformat{bookalgorithm}}
\renewcommand{\thebookcase}{\Roman{bookcase}}

\newcommand{\bookpart}[1]{\ifbook@showstructure\bookstylestructure{\part}{#1}\fi}
\newcommand{\bookchapter}[1]{\ifbook@showstructure\bookstylestructure{\chapter}{#1}\fi}
\newcommand{\booksection}[1]{\ifbook@showstructure\bookstylestructure{\section}{#1}\fi}
\newcommand{\booksubsection}[1]{\ifbook@showstructure\bookstylestructure{\subsection}{#1}\fi}
\newcommand{\booksubsubsection}[1]{\ifbook@showstructure\bookstylestructure{\subsubsection}{#1}\fi}
\newcommand{\bookparagraph}[1]{\ifbook@showstructure\bookstylestructure{\paragraph}{#1}\fi}

\NewEnviron{bookbody}{\book@renderbody{\BODY}}
\NewEnviron{booktext}{\book@renderbody{\BODY}}
\NewEnviron{bookexposition}{\book@renderbody{\BODY}}
\NewEnviron{textbookexposition}{\book@renderbody{\BODY}}
\NewEnviron{bookfrontmatterblock}[1][]{%
  \book@rendermatter{\bookrolefrontmatter}{#1}{\BODY}%
}
\NewEnviron{bookbackmatterblock}[1][]{%
  \book@rendermatter{\bookrolebackmatter}{#1}{\BODY}%
}
\NewEnviron{booksupplement}[1][]{%
  \book@rendermatter{\bookrolesupplement}{#1}{\BODY}%
}
\NewEnviron{bookknowledgeprose}{\book@renderknowledgeprose{\BODY}}
\NewEnviron{knowledgeprose}{\book@renderknowledgeprose{\BODY}}

\NewEnviron{bookknowledgeblock}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{bookknowledgeblockopen}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{bookknowledgeblockmiddle}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{bookknowledgeblockcontinued}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{knowledgeblock}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{knowledgeblockopen}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{knowledgeblockmiddle}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}
\NewEnviron{knowledgeblockcontinued}[1][]{%
  \book@renderknowledge{\bookroleknowledge}{}{#1}{\BODY}%
}

\NewEnviron{bookdefinition}[1][]{%
  \refstepcounter{bookdefinition}%
  \book@renderknowledge{\bookroledefinition}{\thebookdefinition}{#1}{\BODY}%
}
\NewEnviron{booktheorem}[1][]{%
  \refstepcounter{booktheorem}%
  \book@renderknowledge{\bookroletheorem}{\thebooktheorem}{#1}{\BODY}%
}
\NewEnviron{booklemma}[1][]{%
  \refstepcounter{booklemma}%
  \book@renderknowledge{\bookrolelemma}{\thebooklemma}{#1}{\BODY}%
}
\NewEnviron{bookproposition}[1][]{%
  \refstepcounter{bookproposition}%
  \book@renderknowledge{\bookroleproposition}{\thebookproposition}{#1}{\BODY}%
}
\NewEnviron{bookcorollary}[1][]{%
  \refstepcounter{bookcorollary}%
  \book@renderknowledge{\bookrolecorollary}{\thebookcorollary}{#1}{\BODY}%
}
\NewEnviron{bookproperty}[1][]{%
  \refstepcounter{bookproperty}%
  \book@renderknowledge{\bookroleproperty}{\thebookproperty}{#1}{\BODY}%
}
\NewEnviron{bookconcept}[1][]{%
  \refstepcounter{bookconcept}%
  \book@renderknowledge{\bookroleconcept}{\thebookconcept}{#1}{\BODY}%
}
\NewEnviron{bookproof}[1][]{\book@renderproof{#1}{\BODY}}

\newlength{\bookworkbookanswerspace}
\setlength{\bookworkbookanswerspace}{0.22\textheight}
\newcommand{\booksetanswerspace}[1]{\setlength{\bookworkbookanswerspace}{#1}}
\newcommand{\book@answerspace}{%
  \par\nobreak\vspace{\bookworkbookanswerspace}\par
}

\NewEnviron{bookexample}[1][]{%
  \refstepcounter{bookexample}%
  \book@resetquestionchildren
  \book@selectexample
  \book@renderquestionterminal{\bookroleexample}{\thebookexample}{#1}{\BODY}%
}
\NewEnviron{bookexamplestart}[1][]{%
  \refstepcounter{bookexample}%
  \book@resetquestionchildren
  \book@selectexample
  \book@renderquestionsegment{\bookroleexample}{\thebookexample}{#1}{\BODY}%
}
\NewEnviron{bookexamplecontinuation}[1][]{%
  \book@selectexample
  \book@renderquestionsegment{\bookroleexample}{\thebookexample}{#1}{\BODY}%
}
\NewEnviron{bookexampleend}[1][]{%
  \book@selectexample
  \book@renderquestionterminal{\bookroleexample}{\thebookexample}{#1}{\BODY}%
}

\NewEnviron{bookexercise}[1][]{%
  \refstepcounter{bookexercise}%
  \book@resetquestionchildren
  \book@selectexercise
  \book@renderquestionterminal{\bookroleexercise}{\thebookexercise}{#1}{\BODY}%
}
\NewEnviron{bookexercisestart}[1][]{%
  \refstepcounter{bookexercise}%
  \book@resetquestionchildren
  \book@selectexercise
  \book@renderquestionsegment{\bookroleexercise}{\thebookexercise}{#1}{\BODY}%
}
\NewEnviron{bookexercisecontinuation}[1][]{%
  \book@selectexercise
  \book@renderquestionsegment{\bookroleexercise}{\thebookexercise}{#1}{\BODY}%
}
\NewEnviron{bookexerciseend}[1][]{%
  \book@selectexercise
  \book@renderquestionterminal{\bookroleexercise}{\thebookexercise}{#1}{\BODY}%
}

\NewEnviron{bookquestion}[1][]{%
  \refstepcounter{bookquestion}%
  \book@resetquestionchildren
  \book@selectgenericquestion
  \book@renderquestionterminal{\bookrolequestion}{\thebookquestion}{#1}{\BODY}%
}
\NewEnviron{bookquestionstart}[1][]{%
  \refstepcounter{bookquestion}%
  \book@resetquestionchildren
  \book@selectgenericquestion
  \book@renderquestionsegment{\bookrolequestion}{\thebookquestion}{#1}{\BODY}%
}
\NewEnviron{bookquestioncontinuation}[1][]{%
  \book@selectgenericquestion
  \book@renderquestionsegment{\bookrolequestion}{\thebookquestion}{#1}{\BODY}%
}
\NewEnviron{bookquestionend}[1][]{%
  \book@selectgenericquestion
  \book@renderquestionterminal{\bookrolequestion}{\thebookquestion}{#1}{\BODY}%
}

% Answer owners may be nested in their question owner or follow it as siblings.
% Their visibility follows the question kind, so example-only views do not leak
% exercise answers and workbook builds retain the question while hiding answers.
\NewEnviron{bookanswer}[1][]{\book@renderanswer{\bookroleanswer}{#1}{\BODY}}
\NewEnviron{booksolution}[1][]{\book@renderanswer{\bookrolesolution}{#1}{\BODY}}
\NewEnviron{bookanalysis}[1][]{\book@renderanswer{\bookroleanalysis}{#1}{\BODY}}
\NewEnviron{bookhint}[1][]{\book@renderanswer{\bookrolehint}{#1}{\BODY}}

\NewEnviron{bookmethodstep}[1][]{%
  \refstepcounter{bookmethodstep}%
  \book@renderanswer{\bookrolemethod\space\arabic{bookmethodstep}}{#1}{\BODY}%
}
\NewEnviron{bookproofstep}[1][]{%
  \refstepcounter{bookproofstep}%
  \book@renderanswer{\bookroleproof\space\arabic{bookproofstep}}{#1}{\BODY}%
}
\NewEnviron{bookanalysisstep}[1][]{%
  \refstepcounter{bookanalysisstep}%
  \book@renderanswer{\bookroleanalysis\space\arabic{bookanalysisstep}}{#1}{\BODY}%
}
\NewEnviron{booksolutionstep}[1][]{%
  \refstepcounter{booksolutionstep}%
  \book@renderanswer{\bookrolestep\space\arabic{booksolutionstep}}{#1}{\BODY}%
}
\NewEnviron{bookcase}[1][]{%
  \refstepcounter{bookcase}%
  \book@renderanswer{\bookrolecase\space\thebookcase}{#1}{\BODY}%
}

\NewEnviron{bookremark}[1][]{\book@rendercommentary{\bookroleremark}{#1}{\BODY}}
\NewEnviron{booknote}[1][]{\book@rendercommentary{\bookrolenote}{#1}{\BODY}}
\NewEnviron{booktip}[1][]{\book@rendercommentary{\bookroletip}{#1}{\BODY}}
\NewEnviron{bookwarning}[1][]{\book@rendercommentary{\bookrolewarning}{#1}{\BODY}}
\NewEnviron{booksummary}[1][]{\book@rendercommentary{\bookrolesummary}{#1}{\BODY}}

\NewEnviron{bookfigure}[1][]{%
  \refstepcounter{bookfigure}%
  \book@rendermedia{\bookrolefigure}{\thebookfigure}{#1}{\BODY}%
}
\NewEnviron{booktable}[1][]{%
  \refstepcounter{booktable}%
  \book@rendermedia{\bookroletable}{\thebooktable}{#1}{\BODY}%
}
\NewEnviron{bookalgorithm}[1][]{%
  \refstepcounter{bookalgorithm}%
  \book@rendermedia{\bookrolealgorithm}{\thebookalgorithm}{#1}{\BODY}%
}
\NewEnviron{bookequation}{%
  \ifbook@showmedia
    \bookstyleequation{\BODY}%
  \else
    \refstepcounter{equation}%
  \fi
}
\NewEnviron{bookformula}{%
  \ifbook@showmedia
    \bookstyleequation{\BODY}%
  \else
    \refstepcounter{equation}%
  \fi
}

% --------------------------------------------------------------------------
% Figure placeholder: use only before vector reconstruction is complete.
% --------------------------------------------------------------------------
\newcommand{\bookfigureplaceholder}[1]{%
  \par\medskip\noindent
  \fbox{\parbox{0.92\linewidth}{\centering Vector figure pending: \texttt{#1}}}%
  \par\medskip
}

% --------------------------------------------------------------------------
% Workbook profiles and themes. The original size must be supplied by project.
% --------------------------------------------------------------------------
\newcommand{\book@originalwidth}{}
\newcommand{\book@originalheight}{}
\newcommand{\booksetoriginalpagesize}[2]{%
  \def\book@originalwidth{#1}%
  \def\book@originalheight{#2}%
}

\newcommand{\booksetworkbookprofile}[1]{%
  \edef\book@requestedprofile{#1}%
  \ifdefstring{\book@requestedprofile}{original}{%
    \ifx\book@originalwidth\@empty
      \ClassError{base}{Original paper size is not configured}%
        {Call \string\booksetoriginalpagesize before selecting original.}%
    \else
      \geometry{paperwidth=\book@originalwidth,paperheight=\book@originalheight,margin=15mm}%
    \fi
  }{\ifdefstring{\book@requestedprofile}{pad11}{%
    \geometry{paperwidth=280mm,paperheight=193mm,margin=14mm}%
  }{\ifdefstring{\book@requestedprofile}{pad13}{%
    \geometry{paperwidth=280mm,paperheight=210mm,margin=15mm}%
  }{\ifdefstring{\book@requestedprofile}{a4}{%
    \geometry{a4paper,margin=18mm}%
  }{%
    \ClassError{base}{Unknown workbook profile `\book@requestedprofile'}%
      {Use original, pad11, pad13, or a4.}%
  }}}}%
}

\definecolor{BookReferenceEyePage}{HTML}{F5F0C8}
\definecolor{BookReferenceEyeText}{HTML}{242821}
\newcommand{\booksettheme}[1]{%
  \edef\book@requestedtheme{#1}%
  \ifdefstring{\book@requestedtheme}{print}{%
    \pagecolor{white}\color{black}%
  }{\ifdefstring{\book@requestedtheme}{eyecare}{%
    \pagecolor{BookReferenceEyePage}\color{BookReferenceEyeText}%
  }{%
    \ClassError{base}{Unknown theme `\book@requestedtheme'}{Use print or eyecare.}%
  }}%
}

\booksetcontentmode{\book@initialmode}
\ifbook@workbook
  \booksetworkbookscope{\book@initialscope}%
  \booksetworkbookprofile{\book@initialprofile}%
\fi
\booksettheme{\book@initialtheme}

\makeatother
