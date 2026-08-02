# 参考模板：复制到项目根目录后，按项目 .cls 的实际接口调整入口和宏名。
# 该模板不导入扫描页图；它只编译 LaTeX 源码并发布经过检查的 PDF。

[CmdletBinding()]
param(
    [ValidateSet('book', 'workbook', 'matrix')]
    [string]$Target = 'book',
    [ValidateSet('examples', 'exercises', 'all')]
    [string[]]$Scope = @(),
    [ValidateSet('original', 'pad11', 'pad13', 'a4')]
    [string]$Profile = 'original',
    [ValidateSet('print', 'eyecare')]
    [string]$Theme = 'print',
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
if (-not $SkipVisualCheck) { Assert-Command 'pdftoppm' }

if ($Target -eq 'book' -and $Profile -ne 'original') {
    throw '完整书不接受 A4/Pad profile；请确认原书尺寸并使用 original。'
}
if ($Target -eq 'book' -and $Scope.Count -gt 0) {
    throw '完整书不接受 workbook scope；请使用 -Target workbook 或 matrix。'
}
if ($Target -eq 'matrix' -and ($Profile -ne 'original' -or $Theme -ne 'print')) {
    throw 'matrix 会固定生成完整书的 print/eyecare 和全部做题本 profile；请改用单目标 workbook 调整轴。'
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
    if ($Scope.Count -ne 1) {
        throw 'Target workbook 需要恰好一个 -Scope；矩阵目标可用逗号传入多个实际题型。'
    }
    $scopeName = $Scope[0]
    $jobs.Add((New-Job 'workbook' "workbook-$scopeName-$Profile-$Theme" $scopeName $Profile $Theme))
}
if ($Target -eq 'matrix') {
    # Matrix mode always covers both themes for the complete book.  Workbook
    # scopes are opt-in: pass only question types that exist in this source;
    # an omitted scope means no workbook target is generated.
    foreach ($themeName in @('print', 'eyecare')) {
        $jobs.Add((New-Job 'book' "book-$themeName" 'all' 'original' $themeName))
    }
    foreach ($scopeName in ($Scope | Select-Object -Unique)) {
        foreach ($profileName in @('original', 'pad11', 'pad13', 'a4')) {
            foreach ($themeName in @('print', 'eyecare')) {
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

function Assert-Pdf([string]$Pdf, [string]$Log, [string]$JobName) {
    if (-not (Test-Path -LiteralPath $Pdf -PathType Leaf)) {
        throw "没有生成 PDF: $Pdf"
    }
    if ((Get-Item -LiteralPath $Pdf).Length -lt 1024) {
        throw "PDF 过小，疑似空产物: $Pdf"
    }
    $logText = Get-Content -Raw -LiteralPath $Log
    if ($logText -match 'Fatal error|Emergency stop|Undefined control sequence|LaTeX Error|undefined references|There were undefined references') {
        throw "构建日志存在致命错误或未收敛引用: $JobName"
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
    Push-Location $LatexRoot
    try {
        for ($script:PassIndex = 1; $script:PassIndex -le $Passes; $script:PassIndex++) {
            Invoke-LatexPass $arguments $Job.JobName
        }
    }
    finally { Pop-Location }
    $pdf = Join-Path $cache "$($Job.JobName).pdf"
    $log = Join-Path $cache "$($Job.JobName).log"
    Assert-Pdf $pdf $log $Job.JobName
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
