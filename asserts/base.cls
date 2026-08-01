% Reference only. Start each project class from a blank file.
% Reuse interface shapes when helpful; replace every visual choice from source pages.
% Public environment, command, counter, label, and internal API names are
% English ASCII identifiers; role macros may expand to localized display text.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{base}[2026/08/02 Semantic scanned-book class contract]

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

% Streaming style hooks.  A project class redefines these begin/end pairs
% instead of collecting an environment body.  This keeps a semantic owner
% open across sequential \input files.
\newcommand{\bookstylebodybegin}{}
\newcommand{\bookstylebodyend}{}
\newcommand{\bookstylematterbegin}[2]{%
  \par\medskip\noindent
  \ifstrempty{#2}{}{\bookstylelabel{#1}\space\bookstylelabel{#2}\par\smallskip}%
}
\newcommand{\bookstylematterend}{\par\medskip}
\newcommand{\bookstyleknowledgebegin}[3]{%
  \par\medskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
  \ifstrempty{#3}{}{\space（#3）}%
  \quad
}
\newcommand{\bookstyleknowledgeend}{\par\medskip}
\newcommand{\bookstylequestionbegin}[3]{%
  \par\medskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
  \ifstrempty{#3}{}{\space（#3）}%
  \quad
}
\newcommand{\bookstylequestionend}{\par}
\newcommand{\bookstyleanswerbegin}[2]{%
  \par\smallskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space（#2）}%
  \quad
}
\newcommand{\bookstyleanswerend}{\par\smallskip}
\newcommand{\bookstylecommentarybegin}[2]{%
  \par\smallskip\noindent
  \bookstylelabel{#1}%
  \ifstrempty{#2}{}{\space（#2）}%
  \quad
}
\newcommand{\bookstylecommentaryend}{\par\smallskip}
\newcommand{\bookstylemediabegin}[3]{\par\medskip\noindent}
\newcommand{\bookstylemediaend}[3]{%
  \ifstrempty{#3}{}{%
    \par\smallskip\noindent
    \bookstylelabel{#1}%
    \ifstrempty{#2}{}{\space\bookstylelabel{#2}}%
    \space #3%
  }%
  \par\medskip
}
\newcommand{\bookstyleequationbegin}{\begin{equation}}
\newcommand{\bookstyleequationend}{\end{equation}}

% --------------------------------------------------------------------------
% Streaming semantic-owner support.  Do not replace these with body-capturing
% definitions: a single \begin may be in pages/pages-001.tex and its matching
% \end in a later sequential \input file.  When a selected owner is hidden,
% its content is still expanded in a discarded box so nested counters, labels,
% and semantic structure remain valid without leaking visible material.
% --------------------------------------------------------------------------
\newif\ifbook@streamvisible
\newif\ifbook@discarding
\newif\ifbook@owncapture
\newbox\book@discardbox
\book@streamvisibletrue
\book@discardingfalse

\newcommand{\book@streambegin}[1]{%
  \begingroup
  \book@owncapturefalse
  \ifbook@streamvisible
    #1%
  \else
    \book@streamvisiblefalse
  \fi
  \ifbook@streamvisible\else
    \ifbook@discarding\else
      \book@owncapturetrue
      \book@discardingtrue
      \setbox\book@discardbox=\vbox\bgroup
    \fi
  \fi
}
\newcommand{\book@streamend}{%
  \ifbook@owncapture\egroup\fi
  \endgroup
}

\newcommand{\book@selectvisiblebody}{%
  \book@streamvisiblefalse
  \ifbook@showbody
    \book@streamvisibletrue
  \else\ifbook@insideknowledge
    \book@streamvisibletrue
  \else\ifbook@insidequestion
    \book@streamvisibletrue
  \else\ifbook@insideanswer
    \book@streamvisibletrue
  \fi\fi\fi\fi
}
\newcommand{\book@selectvisiblematter}{%
  \ifbook@showmatter\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisibleknowledge}{%
  \ifbook@showknowledge\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisibleproof}{%
  \ifbook@showproofs\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisiblequestion}{%
  \ifbook@selectedquestion\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisibleanswer}{%
  \ifbook@selectedanswer\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisiblecommentary}{%
  \ifbook@showcommentary\book@streamvisibletrue\else\book@streamvisiblefalse\fi
}
\newcommand{\book@selectvisiblemedia}{%
  \ifbook@showmedia\book@streamvisibletrue\else\book@streamvisiblefalse\fi
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

\newcommand{\book@beginbody}{%
  \book@streambegin{\book@selectvisiblebody}%
  \ifbook@streamvisible\bookstylebodybegin\fi
}
\newcommand{\book@endbody}{%
  \ifbook@streamvisible\bookstylebodyend\fi
  \book@streamend
}
\newcommand{\book@beginmatter}[2]{%
  \book@streambegin{\book@selectvisiblematter}%
  \ifbook@streamvisible\bookstylematterbegin{#1}{#2}\fi
}
\newcommand{\book@endmatter}{%
  \ifbook@streamvisible\bookstylematterend\fi
  \book@streamend
}
\newcommand{\book@beginknowledge}[3]{%
  \book@streambegin{\book@selectvisibleknowledge}%
  \ifbook@streamvisible
    \book@insideknowledgetrue
    \bookstyleknowledgebegin{#1}{#2}{#3}%
  \fi
}
\newcommand{\book@endknowledge}{%
  \ifbook@streamvisible\bookstyleknowledgeend\fi
  \book@streamend
}
\newcommand{\book@beginproof}[1]{%
  \book@streambegin{\book@selectvisibleproof}%
  \ifbook@streamvisible
    \book@insideknowledgetrue
    \bookstyleanswerbegin{\bookroleproof}{#1}%
  \fi
}
\newcommand{\book@endproof}{%
  \ifbook@streamvisible\bookstyleanswerend\fi
  \book@streamend
}

\newenvironment{bookbody}{\book@beginbody}{\book@endbody}
\newenvironment{booktext}{\book@beginbody}{\book@endbody}
\newenvironment{bookexposition}{\book@beginbody}{\book@endbody}
\newenvironment{textbookexposition}{\book@beginbody}{\book@endbody}
\newenvironment{bookfrontmatterblock}[1][]%
  {\book@beginmatter{\bookrolefrontmatter}{#1}}{\book@endmatter}
\newenvironment{bookbackmatterblock}[1][]%
  {\book@beginmatter{\bookrolebackmatter}{#1}}{\book@endmatter}
\newenvironment{booksupplement}[1][]%
  {\book@beginmatter{\bookrolesupplement}{#1}}{\book@endmatter}
\newenvironment{bookknowledgeprose}{%
  \book@streambegin{\book@selectvisibleknowledge}%
  \ifbook@streamvisible\book@insideknowledgetrue\bookstylebodybegin\fi
}{%
  \ifbook@streamvisible\bookstylebodyend\fi
  \book@streamend
}
\newenvironment{knowledgeprose}{\begin{bookknowledgeprose}}{\end{bookknowledgeprose}}
\newenvironment{bookknowledgeblock}[1][]%
  {\book@beginknowledge{\bookroleknowledge}{}{#1}}{\book@endknowledge}
\newenvironment{knowledgeblock}[1][]%
  {\book@beginknowledge{\bookroleknowledge}{}{#1}}{\book@endknowledge}

\newenvironment{bookdefinition}[1][]%
  {\refstepcounter{bookdefinition}\book@beginknowledge{\bookroledefinition}{\thebookdefinition}{#1}}%
  {\book@endknowledge}
\newenvironment{booktheorem}[1][]%
  {\refstepcounter{booktheorem}\book@beginknowledge{\bookroletheorem}{\thebooktheorem}{#1}}%
  {\book@endknowledge}
\newenvironment{booklemma}[1][]%
  {\refstepcounter{booklemma}\book@beginknowledge{\bookrolelemma}{\thebooklemma}{#1}}%
  {\book@endknowledge}
\newenvironment{bookproposition}[1][]%
  {\refstepcounter{bookproposition}\book@beginknowledge{\bookroleproposition}{\thebookproposition}{#1}}%
  {\book@endknowledge}
\newenvironment{bookcorollary}[1][]%
  {\refstepcounter{bookcorollary}\book@beginknowledge{\bookrolecorollary}{\thebookcorollary}{#1}}%
  {\book@endknowledge}
\newenvironment{bookproperty}[1][]%
  {\refstepcounter{bookproperty}\book@beginknowledge{\bookroleproperty}{\thebookproperty}{#1}}%
  {\book@endknowledge}
\newenvironment{bookconcept}[1][]%
  {\refstepcounter{bookconcept}\book@beginknowledge{\bookroleconcept}{\thebookconcept}{#1}}%
  {\book@endknowledge}
\newenvironment{bookproof}[1][]%
  {\book@beginproof{#1}}{\book@endproof}

\newlength{\bookworkbookanswerspace}
\setlength{\bookworkbookanswerspace}{0.22\textheight}
\newcommand{\booksetanswerspace}[1]{\setlength{\bookworkbookanswerspace}{#1}}
\newcommand{\book@answerspace}{%
  \par\nobreak\vspace{\bookworkbookanswerspace}\par
}

\newcommand{\book@beginquestion}[4]{%
  #1%
  \book@streambegin{\book@selectvisiblequestion}%
  \ifbook@streamvisible
    \book@insidequestiontrue
    \bookstylequestionbegin{#2}{#3}{#4}%
  \fi
}
\newcommand{\book@endquestion}{%
  \ifbook@streamvisible
    \bookstylequestionend
    \ifbook@workbook\book@answerspace\fi
  \fi
  \book@streamend
}

% A logical question is one streaming environment.  It may begin in one page
% source file and end in any later file reached by the same \bookinput call.
% Counters are advanced only here at \begin time; answer space is emitted only
% in \book@endquestion.
\newenvironment{bookexample}[1][]%
  {\refstepcounter{bookexample}\book@resetquestionchildren\book@beginquestion{\book@selectexample}{\bookroleexample}{\thebookexample}{#1}}%
  {\book@endquestion}
\newenvironment{bookexercise}[1][]%
  {\refstepcounter{bookexercise}\book@resetquestionchildren\book@beginquestion{\book@selectexercise}{\bookroleexercise}{\thebookexercise}{#1}}%
  {\book@endquestion}
\newenvironment{bookquestion}[1][]%
  {\refstepcounter{bookquestion}\book@resetquestionchildren\book@beginquestion{\book@selectgenericquestion}{\bookrolequestion}{\thebookquestion}{#1}}%
  {\book@endquestion}

% Answer owners may be nested in their question owner or follow it as
% siblings.  They are also streaming so a long solution can cross a source
% page boundary without a second public fragment environment.
\newcommand{\book@beginanswer}[2]{%
  \book@selectanswer
  \book@streambegin{\book@selectvisibleanswer}%
  \ifbook@streamvisible
    \book@insideanswertrue
    \bookstyleanswerbegin{#1}{#2}%
  \fi
}
\newcommand{\book@endanswer}{%
  \ifbook@streamvisible\bookstyleanswerend\fi
  \book@streamend
}
\newenvironment{bookanswer}[1][]%
  {\book@beginanswer{\bookroleanswer}{#1}}{\book@endanswer}
\newenvironment{booksolution}[1][]%
  {\book@beginanswer{\bookrolesolution}{#1}}{\book@endanswer}
\newenvironment{bookanalysis}[1][]%
  {\book@beginanswer{\bookroleanalysis}{#1}}{\book@endanswer}
\newenvironment{bookhint}[1][]%
  {\book@beginanswer{\bookrolehint}{#1}}{\book@endanswer}
\newenvironment{bookmethodstep}[1][]%
  {\refstepcounter{bookmethodstep}\book@beginanswer{\bookrolemethod\space\arabic{bookmethodstep}}{#1}}%
  {\book@endanswer}
\newenvironment{bookproofstep}[1][]%
  {\refstepcounter{bookproofstep}\book@beginanswer{\bookroleproof\space\arabic{bookproofstep}}{#1}}%
  {\book@endanswer}
\newenvironment{bookanalysisstep}[1][]%
  {\refstepcounter{bookanalysisstep}\book@beginanswer{\bookroleanalysis\space\arabic{bookanalysisstep}}{#1}}%
  {\book@endanswer}
\newenvironment{booksolutionstep}[1][]%
  {\refstepcounter{booksolutionstep}\book@beginanswer{\bookrolestep\space\arabic{booksolutionstep}}{#1}}%
  {\book@endanswer}
\newenvironment{bookcase}[1][]%
  {\refstepcounter{bookcase}\book@beginanswer{\bookrolecase\space\thebookcase}{#1}}%
  {\book@endanswer}

\newcommand{\book@begincommentary}[2]{%
  \book@streambegin{\book@selectvisiblecommentary}%
  \ifbook@streamvisible\bookstylecommentarybegin{#1}{#2}\fi
}
\newcommand{\book@endcommentary}{%
  \ifbook@streamvisible\bookstylecommentaryend\fi
  \book@streamend
}
\newenvironment{bookremark}[1][]%
  {\book@begincommentary{\bookroleremark}{#1}}{\book@endcommentary}
\newenvironment{booknote}[1][]%
  {\book@begincommentary{\bookrolenote}{#1}}{\book@endcommentary}
\newenvironment{booktip}[1][]%
  {\book@begincommentary{\bookroletip}{#1}}{\book@endcommentary}
\newenvironment{bookwarning}[1][]%
  {\book@begincommentary{\bookrolewarning}{#1}}{\book@endcommentary}
\newenvironment{booksummary}[1][]%
  {\book@begincommentary{\bookrolesummary}{#1}}{\book@endcommentary}

\newcommand{\book@beginmedia}[3]{%
  \book@streambegin{\book@selectvisiblemedia}%
  \ifbook@streamvisible
    \def\book@media@role{#1}%
    \edef\book@media@number{#2}%
    \def\book@media@title{#3}%
    \bookstylemediabegin{#1}{#2}{#3}%
  \fi
}
\newcommand{\book@endmedia}{%
  \ifbook@streamvisible
    \bookstylemediaend{\book@media@role}{\book@media@number}{\book@media@title}%
  \fi
  \book@streamend
}
\newenvironment{bookfigure}[1][]%
  {\refstepcounter{bookfigure}\book@beginmedia{\bookrolefigure}{\thebookfigure}{#1}}%
  {\book@endmedia}
\newenvironment{booktable}[1][]%
  {\refstepcounter{booktable}\book@beginmedia{\bookroletable}{\thebooktable}{#1}}%
  {\book@endmedia}
\newenvironment{bookalgorithm}[1][]%
  {\refstepcounter{bookalgorithm}\book@beginmedia{\bookrolealgorithm}{\thebookalgorithm}{#1}}%
  {\book@endmedia}
\newenvironment{bookequation}{%
  \book@beginmedia{equation}{}{}%
  \bookstyleequationbegin
}{%
  \bookstyleequationend
  \book@endmedia
}
\newenvironment{bookformula}{%
  \book@beginmedia{formula}{}{}%
  \bookstyleequationbegin
}{%
  \bookstyleequationend
  \book@endmedia
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
