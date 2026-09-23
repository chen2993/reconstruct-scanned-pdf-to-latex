# 参考模板：复制到项目根目录后，按项目 .cls 的实际接口调整入口和宏名。
# 该模板不导入扫描页图；它只编译 LaTeX 源码并发布经过检查的 PDF。

[CmdletBinding()]
param(
    [ValidateSet('book', 'workbook', 'matrix')]
    [string]$Target = 'book',
    # 不用 ValidateSet：PowerShell 以 -File 调用时会把逗号列表当成单个字符串，
    # 导致参考文档中的 `-Scope examples,all` 被判为非法。改为在脚本内拆分校验。
    [string[]]$Scope = @(),
    [ValidateSet('original', 'pad11', 'pad13', 'a4')]
    [string]$Profile = 'original',
    # 单目标主题也允许项目自订主题；合法值由下面的 -Themes 集合校验决定。
    [string]$Theme = 'print',
    # 主题集合由用户按项目实际实现的主题确认；参考默认只包含完整书基线所需的
    # print/eyecare。项目实现了别的主题（例如深色）时才追加，不预先假定。
    [string[]]$Themes = @('print', 'eyecare'),
    # 前后置模块按原书实际存在的情况登记，不是固定清单：原件有献词就必须登记
    # 献词，没有就不该出现献词书签；原件没有任何前后置模块（纯正文扫描件）时留空。
    # 默认留空表示"不做模块书签覆盖检查"，只有 outline 结构检查。顺序即原件顺序。
    [string[]]$RequiredBookmarks = @(),
    # 做题本目标必须提供答案哨兵文件：答案的位置和长度无法靠目视抽查保证，
    # 只能在构建时逐页比对。每行一条哨兵文本，`#` 开头为注释。
    [string]$AnswerSentinels = '',
    [ValidateRange(2, 3)]
    [int]$Passes = 3,
    [switch]$Force,
    [switch]$Publish,
    [switch]$DryRun,
    [switch]$SkipVisualCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$LatexRoot = Join-Path $ProjectRoot 'latex'
$CacheRoot = Join-Path $ProjectRoot 'tmp\latexmk'
$DistRoot = Join-Path $ProjectRoot 'dist'

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "缺少构建命令: $Name"
    }
}

Assert-Command 'latexmk'
Assert-Command 'xelatex'
Assert-Command 'python'
if (-not $SkipVisualCheck) { Assert-Command 'pdftoppm' }

# -File 调用时 PowerShell 会把逗号列表作为单个字符串传入；先拆分再校验，
# 使 `./build.ps1 -Themes a,b` 和 `pwsh -File build.ps1 -Themes a,b` 都可用。
$themeSet = @(
    $Themes | ForEach-Object { $_ -split ',' } |
        ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique
)
$Scope = @(
    $Scope | ForEach-Object { $_ -split ',' } |
        ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique
)

if ($Target -eq 'book' -and $Profile -ne 'original') {
    throw '完整书不接受 A4/Pad profile；请确认原书尺寸并使用 original。'
}
if ($Target -eq 'book' -and $Scope.Count -gt 0) {
    throw '完整书不接受 workbook scope；请使用 -Target workbook 或 matrix。'
}
if ($Target -eq 'matrix' -and ($Profile -ne 'original' -or $Theme -ne 'print')) {
    throw 'matrix 会为确认的主题集合生成完整书和全部做题本 profile；请改用单目标 workbook 或 -Themes 调整轴。'
}
if ($Target -eq 'workbook' -and $Scope.Count -ne 1) {
    throw 'Target workbook 需要恰好一个 -Scope；矩阵目标可传入多个实际题型。'
}
foreach ($name in $Scope) {
    if (@('examples', 'exercises', 'all') -notcontains $name) {
        throw "未知的做题本范围: $name（可用 examples、exercises、all）"
    }
}
if ($themeSet.Count -eq 0) {
    throw 'Themes 不能为空；至少提供用户确认的 print 主题。'
}
# 逐元素校验，而不是依赖 ValidatePattern：参数校验会把整个列表当成一个值。
foreach ($name in $themeSet) {
    if ($name -notmatch '^[A-Za-z][A-Za-z0-9_]*$') {
        throw "Themes 中的主题名必须是英文 ASCII 标识符: $name"
    }
}
if ($themeSet -notcontains 'print') {
    throw 'Themes 必须包含 print 作为完整书基线主题。'
}
if ($Target -ne 'matrix' -and $themeSet -notcontains $Theme) {
    throw "Theme '$Theme' 不在用户确认的 Themes 集合内；请先确认项目实际实现的主题。"
}
$bookmarkEntries = @($RequiredBookmarks | ForEach-Object {
    $_ -split ',' | ForEach-Object { $_.Trim() }
} | Where-Object { $_ })
# 允许为空：原件可能没有任何前后置模块（纯正文扫描件），此时只做 outline 结构检查。
$providedKeys = @()
$providedTitles = @()
foreach ($entry in $bookmarkEntries) {
    $parts = $entry -split '=', 2
    if ($parts.Count -ne 2 -or [string]::IsNullOrWhiteSpace($parts[0]) -or
        [string]::IsNullOrWhiteSpace($parts[1])) {
        throw "RequiredBookmarks 映射无效: $entry；应为 KEY=TITLE。"
    }
    $key = $parts[0].Trim()
    if ($key -notmatch '^[a-z][a-z0-9_]*$') {
        throw "RequiredBookmarks 的语义键必须是英文 ASCII 标识符: $key"
    }
    $providedKeys += $key
    $providedTitles += $parts[1].Trim()
}
if (@($providedKeys | Select-Object -Unique).Count -ne $providedKeys.Count) {
    throw "RequiredBookmarks 的语义键重复: $($providedKeys -join ', ')"
}
if (@($providedTitles | Select-Object -Unique).Count -ne $providedTitles.Count) {
    throw "RequiredBookmarks 的显示标题重复: $($providedTitles -join ', ')"
}

function New-Job([string]$Kind, [string]$JobName, [string]$ScopeName,
    [string]$ProfileName, [string]$ThemeName) {
    [pscustomobject]@{
        Kind = $Kind
        JobName = $JobName
        Scope = $ScopeName
        Profile = $ProfileName
        Theme = $ThemeName
    }
}

$jobs = [System.Collections.Generic.List[object]]::new()
if ($Target -eq 'book') {
    # A complete book always uses the confirmed original paper size.  Theme is
    # the only single-target axis accepted here.
    $jobs.Add((New-Job 'book' "book-$Theme" 'all' 'original' $Theme))
}
if ($Target -eq 'workbook') {
    $scopeName = $Scope[0]
    $jobs.Add((New-Job 'workbook' "workbook-$scopeName-$Profile-$Theme" $scopeName $Profile $Theme))
}
if ($Target -eq 'matrix') {
    # Matrix mode covers every user-confirmed theme for the complete book.
    # Workbook scopes are opt-in: pass only question types that exist in this
    # source; an omitted scope means no workbook target is generated.
    foreach ($themeName in $themeSet) {
        $jobs.Add((New-Job 'book' "book-$themeName" 'all' 'original' $themeName))
    }
    foreach ($scopeName in ($Scope | Select-Object -Unique)) {
        foreach ($profileName in @('original', 'pad11', 'pad13', 'a4')) {
            foreach ($themeName in $themeSet) {
                $jobs.Add((New-Job 'workbook' "workbook-$scopeName-$profileName-$themeName" `
                    $scopeName $profileName $themeName))
            }
        }
    }
}
if ($jobs.Count -eq 0) { throw '没有可构建的目标。' }

function New-Driver([object]$Job, [string]$Path) {
    $options = if ($Job.Kind -eq 'book') {
        "book,$($Job.Theme)"
    }
    else {
        "workbook,$($Job.Scope),$($Job.Profile),$($Job.Theme)"
    }
    $text = @"
\def\BookBuildOptions{$options}
\input{main.tex}
"@
    # BOM keeps generated TeX drivers readable under Windows PowerShell 5.1.
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($true))
}

function Invoke-LatexPass([string[]]$Arguments, [string]$JobName) {
    & latexmk @Arguments
    if ($LASTEXITCODE -ne 0) { throw "latexmk 第 $script:PassIndex 遍失败: $JobName" }
}

function Assert-Pdf([string]$Pdf, [string]$Log, [string]$JobName, [string]$ProfileName) {
    if (-not (Test-Path -LiteralPath $Pdf -PathType Leaf)) {
        throw "没有生成 PDF: $Pdf"
    }
    if ((Get-Item -LiteralPath $Pdf).Length -lt 1024) {
        throw "PDF 过小，疑似空产物: $Pdf"
    }
    $logText = Get-Content -Raw -LiteralPath $Log
    if ($logText -match 'Fatal error|Emergency stop|Undefined control sequence|LaTeX Error|undefined references|There were undefined references|Rerun to get|Label(s) may have changed|multiply defined|destination with the same identifier') {
        throw "构建日志存在致命错误或未收敛引用: $JobName"
    }
    $outlineScript = Join-Path $ProjectRoot 'scripts\audit_pdf_outline.py'
    if (-not (Test-Path -LiteralPath $outlineScript -PathType Leaf)) {
        throw "缺少 PDF outline 审计脚本: $outlineScript"
    }
    & python '-X' 'utf8' $outlineScript $Pdf '--required-map' @bookmarkEntries
    if ($LASTEXITCODE -ne 0) {
        throw "PDF outline 未通过模块书签检查: $JobName"
    }
    if (-not $SkipVisualCheck) {
        $probe = Join-Path (Split-Path -Parent $Pdf) 'visual-probe'
        $probeBase = Join-Path (Split-Path -Parent $Pdf) 'visual-probe'
        & pdftoppm '-f' '1' '-l' '1' '-singlefile' '-png' '-r' '40' $Pdf $probeBase
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "$probe.png" -PathType Leaf)) {
            throw "无法渲染首个页面进行非空检查: $JobName"
        }
        if ((Get-Item -LiteralPath "$probe.png").Length -lt 512) {
            throw "首个页面渲染结果为空: $JobName"
        }
        Remove-Item -LiteralPath "$probe.png" -Force
    }

    # 整页位图包装和答案泄漏都要在成品对象层检查；目视抽查发现不了漏网的一页。
    $buildScript = Join-Path $ProjectRoot 'scripts\audit_pdf_build.py'
    if (-not (Test-Path -LiteralPath $buildScript -PathType Leaf)) {
        throw "缺少成品审计脚本: $buildScript"
    }
    $buildArguments = @('-X', 'utf8', $buildScript, $Pdf)
    # 完整书用项目登记的 original 尺寸；做题本用各自的 profile。逐页核对 MediaBox，
    # 只报告"集合里有正确尺寸"会漏掉真正混错的那几页。
    if (-not [string]::IsNullOrWhiteSpace($ProfileName)) {
        $buildArguments += @('--profile', $ProfileName)
    }
    if ($JobName -like 'workbook-*') {
        if ([string]::IsNullOrWhiteSpace($AnswerSentinels)) {
            throw "做题本目标必须提供 -AnswerSentinels 才能检查答案是否被隐藏: $JobName"
        }
        if (-not (Test-Path -LiteralPath $AnswerSentinels -PathType Leaf)) {
            throw "答案哨兵文件不存在: $AnswerSentinels"
        }
        $buildArguments += @('--sentinels', $AnswerSentinels)
    }
    & python @buildArguments
    if ($LASTEXITCODE -ne 0) {
        throw "成品审计未通过: $JobName"
    }
}

function Invoke-Job([object]$Job) {
    $cache = Join-Path $CacheRoot $Job.JobName
    $driver = Join-Path $cache 'driver.tex'
    $arguments = @(
        '-xelatex', '-cd-', '-interaction=nonstopmode', '-halt-on-error',
        '-file-line-error', '-recorder', '-latexoption=-no-shell-escape',
        "-outdir=$cache", "-jobname=$($Job.JobName)", $driver
    )
    if ($Force) { $arguments = @('-g') + $arguments }
    if ($DryRun) {
        Write-Host "[$($Job.JobName)] $Passes pass(es): latexmk $($arguments -join ' ')"
        return [pscustomobject]@{ JobName = $Job.JobName; Pdf = $null }
    }
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    New-Driver $Job $driver
    $tocScript = Join-Path $ProjectRoot 'scripts\audit_toc.py'
    if (-not (Test-Path -LiteralPath $tocScript -PathType Leaf)) {
        throw "缺少自动目录审计脚本: $tocScript"
    }
    & python '-X' 'utf8' $tocScript $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "自动目录审计失败: $($Job.JobName)"
    }
    # 来源页标记必须逐页可追溯，否则重编号/迁移后的漏页与错位只会在人工抽样里漏掉。
    $provenanceScript = Join-Path $ProjectRoot 'scripts\audit_provenance.py'
    if (Test-Path -LiteralPath $provenanceScript -PathType Leaf) {
        & python '-X' 'utf8' $provenanceScript $ProjectRoot
        if ($LASTEXITCODE -ne 0) {
            throw "来源页标记审计失败: $($Job.JobName)"
        }
    }
    $tocHashes = @()
    $outlineHashes = @()
    Push-Location $LatexRoot
    try {
        for ($script:PassIndex = 1; $script:PassIndex -le $Passes; $script:PassIndex++) {
            Invoke-LatexPass $arguments $Job.JobName
            foreach ($artifact in @(
                @{ Path = (Join-Path $cache "$($Job.JobName).toc"); Name = 'toc' },
                @{ Path = (Join-Path $cache "$($Job.JobName).out"); Name = 'outline' }
            )) {
                if (-not (Test-Path -LiteralPath $artifact.Path -PathType Leaf)) {
                    if ($artifact.Name -eq 'toc') { $tocHashes += '<missing>' }
                    else { $outlineHashes += '<missing>' }
                    continue
                }
                $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.Path).Hash
                if ($artifact.Name -eq 'toc') { $tocHashes += $hash }
                else { $outlineHashes += $hash }
            }
        }
    }
    finally { Pop-Location }
    if ($tocHashes.Count -lt 2 -or $outlineHashes.Count -lt 2 -or
        $tocHashes[-1] -eq '<missing>' -or $outlineHashes[-1] -eq '<missing>') {
        throw "缺少 .toc 或 PDF outline 辅助文件: $($Job.JobName)"
    }
    if ($tocHashes[-1] -ne $tocHashes[-2]) {
        throw "目录辅助文件在最后两遍之间仍未收敛: $($Job.JobName)"
    }
    if ($outlineHashes[-1] -ne $outlineHashes[-2]) {
        throw "PDF outline 辅助文件在最后两遍之间仍未收敛: $($Job.JobName)"
    }
    $pdf = Join-Path $cache "$($Job.JobName).pdf"
    $log = Join-Path $cache "$($Job.JobName).log"
    # 完整书用项目登记的 original 尺寸；做题本用各自的 profile。
    $profileForAudit = if ($Job.Profile) { $Job.Profile } else { 'original' }
    Assert-Pdf $pdf $log $Job.JobName $profileForAudit
    Write-Host "[$($Job.JobName)] OK"
    return [pscustomobject]@{ JobName = $Job.JobName; Pdf = $pdf }
}

function Publish-Atomic([object[]]$Results) {
    $distParent = Split-Path -Parent $DistRoot
    New-Item -ItemType Directory -Force -Path $distParent | Out-Null
    $token = [guid]::NewGuid().ToString('N')
    $stage = Join-Path $distParent ".dist-publish-$token"
    $backup = Join-Path $distParent ".dist-backup-$token"
    New-Item -ItemType Directory -Path $stage | Out-Null
    $swapped = $false
    try {
        # Preserve unrelated existing distribution files in the staged tree;
        # only after every target has been copied and checked is the directory
        # exchanged as one operation.
        if (Test-Path -LiteralPath $DistRoot -PathType Container) {
            Get-ChildItem -LiteralPath $DistRoot -Force | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
            }
        }
        foreach ($result in $Results) {
            $target = Join-Path $stage "$($result.JobName).pdf"
            Copy-Item -LiteralPath $result.Pdf -Destination $target -Force
            if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or
                (Get-Item -LiteralPath $target).Length -lt 1024) {
                throw "暂存发布产物无效: $target"
            }
        }
        if (Test-Path -LiteralPath $DistRoot) {
            Move-Item -LiteralPath $DistRoot -Destination $backup
        }
        Move-Item -LiteralPath $stage -Destination $DistRoot
        $swapped = $true
    }
    catch {
        if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $DistRoot)) {
            Move-Item -LiteralPath $backup -Destination $DistRoot
        }
        throw
    }
    finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
        if ($swapped -and (Test-Path -LiteralPath $backup)) { Remove-Item -LiteralPath $backup -Recurse -Force }
    }
}

$results = [System.Collections.Generic.List[object]]::new()
foreach ($job in $jobs) {
    $result = Invoke-Job $job
    if (-not $DryRun) { $results.Add($result) }
}
if ($Publish -and -not $DryRun) { Publish-Atomic $results }
Write-Host "完成 $($jobs.Count) 个目标。"
