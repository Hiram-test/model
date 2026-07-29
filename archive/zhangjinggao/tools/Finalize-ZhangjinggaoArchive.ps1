# 声明脚本参数块，用于接收上传进程、归档位置、GitHub 目标和本地精简开关。
param(
    # 指定正在运行的 Upload-ArchiveRelease.ps1 进程编号，脚本会等待该进程结束。
    [Parameter(Mandatory = $true)]
    [int]$UploaderProcessId,
    # 指定张靖皋大桥源目录绝对路径，精简操作仅允许发生在该目录内。
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    # 指定仓库内 archive/zhangjinggao 目录绝对路径，用于读取全部清单。
    [Parameter(Mandatory = $true)]
    [string]$ArchiveDirectory,
    # 指定干净 Git 工作树绝对路径，用于提交最终 Release 资产摘要。
    [Parameter(Mandatory = $true)]
    [string]$RepositoryWorktree,
    # 指定 GitHub 仓库全名，格式必须为 owner/name。
    [Parameter(Mandatory = $true)]
    [string]$Repository,
    # 指定保存完整数据的 GitHub Release 标签。
    [Parameter(Mandatory = $true)]
    [string]$ReleaseTag,
    # 指定最终资产摘要需要推送到的 Git 分支。
    [Parameter(Mandatory = $true)]
    [string]$BranchName,
    # 指定只读快照复核使用的临时目录，该目录必须位于源目录之外。
    [Parameter(Mandatory = $true)]
    [string]$VerificationRoot,
    # 指定是否在 Release 发布成功后执行本地精简；未提供时只完成云端发布。
    [Parameter(Mandatory = $false)]
    [switch]$EnableLocalPrune
)

# 启用严格模式，以便尽早发现缺失字段、空变量和类型错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，保证任一质量门失败都会阻止发布或删除。
$ErrorActionPreference = 'Stop'
# 固定预期源目录，避免参数误填时把精简范围扩大到其他目录。
$expectedSourceRoot = 'D:\张靖皋大桥'
# 固定每个可本地保留文本或输入文件的最大字节数为五十 MiB。
$maximumRetainedFileBytes = [int64](50MB)
# 固定上传进程轮询间隔为三十秒，兼顾及时收尾和较低系统开销。
$uploaderPollSeconds = 30
# 固定两次独立源快照复核之间的稳定观察时间为十五秒。
$snapshotStabilitySeconds = 15
# 固定逐文件完整哈希复核的进度输出间隔为五百个候选删除文件。
$hashProgressInterval = 500
# 固定实际删除阶段的进度输出间隔为一千个已处理文件。
$deleteProgressInterval = 1000

# 验证用户传入的源目录与本任务冻结的目录完全一致。
if (-not [string]::Equals($SourceRoot.TrimEnd('\'), $expectedSourceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    # 抛出包含实际路径的错误，拒绝在其他目录执行任何后续操作。
    throw "源目录不是冻结目标，拒绝继续：$SourceRoot"
}
# 验证源目录存在且为目录。
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    # 抛出包含实际路径的错误，阻止在缺失源目录时误判归档完成。
    throw "源目录不存在：$SourceRoot"
}
# 验证归档清单目录存在且为目录。
if (-not (Test-Path -LiteralPath $ArchiveDirectory -PathType Container)) {
    # 抛出包含实际路径的错误，阻止使用空清单发布。
    throw "归档目录不存在：$ArchiveDirectory"
}
# 验证 Git 工作树存在且包含 .git 元数据入口。
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryWorktree '.git'))) {
    # 抛出包含实际路径的错误，阻止在错误目录执行 Git 提交。
    throw "Git 工作树无效：$RepositoryWorktree"
}
# 验证仓库全名满足 owner/name 格式。
if ($Repository -notmatch '^[^/]+/[^/]+$') {
    # 抛出包含实际配置的错误，避免把资产上传到错误仓库。
    throw "GitHub 仓库格式无效：$Repository"
}
# 验证分支名称不是空白字符串。
if ([string]::IsNullOrWhiteSpace($BranchName)) {
    # 抛出分支缺失错误，避免无目标推送。
    throw 'Git 分支名称不能为空。'
}

# 将源目录解析为规范化绝对路径，供后续边界检查使用。
$resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path.TrimEnd('\')
# 将归档目录解析为规范化绝对路径，供清单和脚本定位使用。
$resolvedArchiveDirectory = (Resolve-Path -LiteralPath $ArchiveDirectory).Path.TrimEnd('\')
# 将 Git 工作树解析为规范化绝对路径，供精确提交和推送使用。
$resolvedRepositoryWorktree = (Resolve-Path -LiteralPath $RepositoryWorktree).Path.TrimEnd('\')
# 验证快照复核目录没有落在源目录内部，防止复核文件混入源快照。
$verificationFullPath = [System.IO.Path]::GetFullPath($VerificationRoot).TrimEnd('\')
# 构造源目录边界前缀，附加分隔符可防止相似名称目录通过前缀判断。
$sourceBoundaryPrefix = $resolvedSourceRoot + [System.IO.Path]::DirectorySeparatorChar
# 拒绝把快照复核目录放在源目录内部。
if ($verificationFullPath.StartsWith($sourceBoundaryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    # 抛出路径边界错误，避免验证过程改变待验证对象。
    throw "快照复核目录不能位于源目录内部：$verificationFullPath"
}
# 在快照复核目录不存在时创建该目录。
if (-not (Test-Path -LiteralPath $verificationFullPath -PathType Container)) {
    # 创建明确的复核目录并丢弃返回对象，保持日志简洁。
    $null = New-Item -ItemType Directory -Path $verificationFullPath -Force
}

# 定义完整源文件清单路径。
$manifestPath = Join-Path $resolvedArchiveDirectory 'archive-manifest.csv'
# 定义完整源文件摘要路径。
$manifestSummaryPath = Join-Path $resolvedArchiveDirectory 'manifest-summary.json'
# 定义 Release 分卷成员计划路径。
$packagePlanPath = Join-Path $resolvedArchiveDirectory 'package-members.csv'
# 定义 Release 分卷计划摘要路径。
$packageSummaryPath = Join-Path $resolvedArchiveDirectory 'package-members.summary.json'
# 定义已上传资产哈希记录路径。
$releaseAssetsPath = Join-Path $resolvedArchiveDirectory 'release-assets.csv'
# 定义上传器最终进度路径。
$uploadProgressPath = Join-Path $resolvedArchiveDirectory 'release-upload-progress.json'
# 定义源目录增量协调脚本路径。
$reconcileScriptPath = Join-Path $resolvedArchiveDirectory 'tools\Reconcile-ArchiveManifest.ps1'
# 定义恢复脚本路径。
$restoreScriptPath = Join-Path $resolvedArchiveDirectory 'tools\Restore-Zhangjinggao.ps1'
# 定义本地保留计划的临时输出路径，该文件在发布后复制到恢复目录。
$retentionPlanPath = Join-Path $resolvedArchiveDirectory 'local-retention-plan.csv'
# 定义守护脚本状态文件路径，便于无需读取长日志即可判断阶段。
$finalizerStatusPath = Join-Path $resolvedArchiveDirectory 'finalizer-status.json'

# 汇总所有必须存在的输入文件，避免在流程中途才发现清单缺失。
$requiredInputPaths = @(
    # 要求完整源文件清单存在。
    $manifestPath,
    # 要求完整源文件摘要存在。
    $manifestSummaryPath,
    # 要求 Release 分卷成员计划存在。
    $packagePlanPath,
    # 要求 Release 分卷计划摘要存在。
    $packageSummaryPath,
    # 要求增量协调脚本存在。
    $reconcileScriptPath,
    # 要求恢复脚本存在。
    $restoreScriptPath
)
# 逐项验证所有必需输入文件均存在。
foreach ($requiredInputPath in $requiredInputPaths) {
    # 判断当前必需输入是否为普通文件。
    if (-not (Test-Path -LiteralPath $requiredInputPath -PathType Leaf)) {
        # 抛出包含缺失路径的错误，阻止后续质量门被绕过。
        throw "归档必需文件不存在：$requiredInputPath"
    }
}

# 验证 GitHub CLI 已安装并可调用。
$ghCommand = Get-Command gh -ErrorAction Stop
# 验证 Git 命令已安装并可调用。
$gitCommand = Get-Command git -ErrorAction Stop
# 调用 GitHub CLI 检查当前认证状态。
& $ghCommand.Source auth status
# 检查认证命令退出码，非零表示远端校验和发布不可执行。
if ($LASTEXITCODE -ne 0) {
    # 抛出认证失败错误并停止。
    throw 'GitHub CLI 当前未通过认证。'
}

# 定义写入守护状态的函数，为后台监控提供原子化阶段摘要。
function Write-FinalizerStatus {
    # 声明函数参数块，用于接收阶段名称、说明和可选附加数据。
    param(
        # 指定当前阶段的稳定英文标识。
        [Parameter(Mandatory = $true)]
        [string]$Stage,
        # 指定当前阶段的中文说明。
        [Parameter(Mandatory = $true)]
        [string]$Message,
        # 指定需要附带写入状态文件的数据对象，允许为空。
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object]$Data
    )
    # 构造按固定顺序排列的守护状态对象。
    $statusObject = [ordered]@{
        # 记录阶段稳定标识。
        Stage = $Stage
        # 记录面向人工检查的阶段说明。
        Message = $Message
        # 记录状态更新时间，采用 UTC ISO 8601 格式。
        UpdatedAtUtc = [DateTime]::UtcNow.ToString('o')
        # 记录调用方提供的可选附加数据。
        Data = $Data
    }
    # 将状态对象写为 UTF-8 JSON，覆盖旧状态以反映最新阶段。
    $statusObject | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $finalizerStatusPath -Encoding utf8
    # 同时把简短状态写入标准输出，便于日志轮询。
    Write-Output ("[{0}] {1}" -f $Stage, $Message)
}

# 定义读取远端 Release 对象的函数，所有远端质量门复用同一字段集合。
function Get-ReleaseObject {
    # 调用 GitHub CLI 获取资产、草稿状态和公开 URL。
    $releaseJson = & $ghCommand.Source release view $ReleaseTag --repo $Repository --json assets,isDraft,url,tagName
    # 检查查询命令退出码，非零表示 Release 当前不可访问。
    if ($LASTEXITCODE -ne 0) {
        # 抛出包含标签名称的错误。
        throw "无法读取 GitHub Release：$ReleaseTag"
    }
    # 将 GitHub 返回的 JSON 转换为 PowerShell 对象并返回。
    return ($releaseJson | ConvertFrom-Json)
}

# 定义验证全部计划资产远端大小与 SHA-256 的函数。
function Assert-RemoteArchiveAssets {
    # 导入完整分卷计划并转换为数组，避免单行计划退化为标量。
    $planRows = @(Import-Csv -LiteralPath $packagePlanPath)
    # 从分卷计划提取唯一资产名称并稳定排序。
    $plannedAssetNames = @($planRows | Select-Object -ExpandProperty AssetName | Sort-Object -Unique)
    # 导入本地已上传资产记录并转换为数组。
    $assetRecords = @(Import-Csv -LiteralPath $releaseAssetsPath)
    # 验证本地资产记录数量与计划唯一资产数完全一致。
    if ($assetRecords.Count -ne $plannedAssetNames.Count) {
        # 抛出包含实际计数的错误，阻止使用缺失记录发布。
        throw "本地资产记录数量不等于计划数量：$($assetRecords.Count) / $($plannedAssetNames.Count)"
    }
    # 创建不区分大小写的本地资产记录字典。
    $recordMap = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 将每条本地资产记录加入字典，并拒绝重复名称。
    foreach ($assetRecord in $assetRecords) {
        # 读取当前记录资产名称。
        $recordName = [string]$assetRecord.AssetName
        # 验证当前资产名称尚未出现。
        if ($recordMap.ContainsKey($recordName)) {
            # 抛出重复资产记录错误。
            throw "本地资产记录存在重复名称：$recordName"
        }
        # 保存当前资产记录。
        $recordMap.Add($recordName, $assetRecord)
    }
    # 读取最新远端 Release 状态。
    $releaseObject = Get-ReleaseObject
    # 创建不区分大小写的远端资产字典。
    $remoteMap = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 将每个远端资产加入字典，并拒绝重复名称。
    foreach ($remoteAsset in @($releaseObject.assets)) {
        # 读取当前远端资产名称。
        $remoteName = [string]$remoteAsset.name
        # 验证当前远端资产名称尚未出现。
        if ($remoteMap.ContainsKey($remoteName)) {
            # 抛出远端重复资产错误。
            throw "远端 Release 存在重复资产名称：$remoteName"
        }
        # 保存当前远端资产对象。
        $remoteMap.Add($remoteName, $remoteAsset)
    }
    # 初始化已验证远端数据资产总字节数。
    $verifiedRemoteBytes = [int64]0
    # 逐项验证计划中的每个资产。
    foreach ($plannedAssetName in $plannedAssetNames) {
        # 验证本地记录字典包含当前计划资产。
        if (-not $recordMap.ContainsKey($plannedAssetName)) {
            # 抛出缺失本地记录错误。
            throw "计划资产缺少本地哈希记录：$plannedAssetName"
        }
        # 验证远端资产字典包含当前计划资产。
        if (-not $remoteMap.ContainsKey($plannedAssetName)) {
            # 抛出缺失远端资产错误。
            throw "计划资产尚未上传到远端：$plannedAssetName"
        }
        # 读取当前资产本地记录。
        $localRecord = $recordMap[$plannedAssetName]
        # 读取当前资产远端记录。
        $verifiedRemoteAsset = $remoteMap[$plannedAssetName]
        # 构造 GitHub 服务端返回的标准 SHA-256 摘要格式。
        $expectedDigest = 'sha256:' + ([string]$localRecord.SHA256).ToLowerInvariant()
        # 验证远端精确字节数等于本地记录。
        if ([int64]$verifiedRemoteAsset.size -ne [int64]$localRecord.Length) {
            # 抛出包含资产名称的大小不一致错误。
            throw "远端资产大小不一致：$plannedAssetName"
        }
        # 验证远端服务端摘要等于本地 SHA-256。
        if (([string]$verifiedRemoteAsset.digest).ToLowerInvariant() -ne $expectedDigest) {
            # 抛出包含资产名称的摘要不一致错误。
            throw "远端资产 SHA-256 不一致：$plannedAssetName"
        }
        # 将当前远端资产字节数加入累计值。
        $verifiedRemoteBytes += [int64]$verifiedRemoteAsset.size
    }
    # 返回远端完整性摘要，供状态文件和最终记录使用。
    return [PSCustomObject][ordered]@{
        # 记录已验证资产数量。
        VerifiedAssetCount = $plannedAssetNames.Count
        # 记录已验证资产总字节数。
        VerifiedAssetBytes = $verifiedRemoteBytes
        # 记录 Release 当前是否仍为草稿。
        IsDraft = [bool]$releaseObject.isDraft
        # 记录 GitHub 返回的 Release URL。
        ReleaseUrl = [string]$releaseObject.url
    }
}

# 定义执行一次相对基线的独立源快照复核函数。
function Test-SourceSnapshotAgainstBaseline {
    # 声明函数参数块，用于接收本次复核目录名称。
    param(
        # 指定本次复核的唯一目录名称。
        [Parameter(Mandatory = $true)]
        [string]$RunName
    )
    # 拼接本次复核目录绝对路径。
    $runDirectory = Join-Path $verificationFullPath $RunName
    # 若同名目录已经存在则停止，避免覆盖既有审计证据。
    if (Test-Path -LiteralPath $runDirectory) {
        # 抛出包含冲突路径的错误。
        throw "快照复核目录已经存在：$runDirectory"
    }
    # 创建本次独立复核目录。
    $null = New-Item -ItemType Directory -Path $runDirectory
    # 拼接本次复核使用的清单副本路径。
    $runManifestPath = Join-Path $runDirectory 'archive-manifest.csv'
    # 复制冻结基线清单，确保协调脚本不会覆盖仓库内正式清单。
    Copy-Item -LiteralPath $manifestPath -Destination $runManifestPath
    # 在清单副本上运行增量协调，并丢弃详细对象输出。
    & $reconcileScriptPath -SourceRoot $resolvedSourceRoot -ManifestPath $runManifestPath | Out-Null
    # 拼接本次复核摘要路径。
    $runSummaryPath = Join-Path $runDirectory 'manifest-summary.json'
    # 验证协调脚本确实生成摘要文件。
    if (-not (Test-Path -LiteralPath $runSummaryPath -PathType Leaf)) {
        # 抛出缺失摘要错误。
        throw "快照复核未生成摘要：$RunName"
    }
    # 读取并解析本次复核摘要。
    $runSummary = Get-Content -LiteralPath $runSummaryPath -Encoding UTF8 -Raw | ConvertFrom-Json
    # 计算所有会破坏冻结快照的变化总数。
    $changeCount = [int64]$runSummary.AddedFiles + [int64]$runSummary.RehashedFiles + [int64]$runSummary.RemovedFiles + [int64]$runSummary.HashFailures
    # 要求新增、变化、删除和哈希失败数量之和严格为零。
    if ($changeCount -ne 0) {
        # 抛出包含分类计数的错误，阻止发布和本地精简。
        throw "源快照相对基线发生变化：新增 $($runSummary.AddedFiles)，变化 $($runSummary.RehashedFiles)，删除 $($runSummary.RemovedFiles)，失败 $($runSummary.HashFailures)"
    }
    # 返回通过质量门的快照摘要。
    return $runSummary
}

# 定义上传并验证恢复辅助文件的函数。
function Publish-AndVerifySupportAssets {
    # 构造需要作为 Release 辅助资产上传的明确文件列表。
    $supportPaths = @(
        # 上传归档说明文档。
        (Join-Path $resolvedArchiveDirectory 'README.md'),
        # 上传完整源文件清单。
        $manifestPath,
        # 上传完整源文件摘要。
        $manifestSummaryPath,
        # 上传分卷成员计划。
        $packagePlanPath,
        # 上传分卷计划摘要。
        $packageSummaryPath,
        # 上传远端资产摘要。
        $releaseAssetsPath,
        # 上传恢复脚本。
        $restoreScriptPath,
        # 上传源清单构建脚本。
        (Join-Path $resolvedArchiveDirectory 'tools\Build-ArchiveManifest.ps1'),
        # 上传源清单协调脚本。
        $reconcileScriptPath,
        # 上传分卷计划构建脚本。
        (Join-Path $resolvedArchiveDirectory 'tools\Build-PackagePlan.ps1'),
        # 上传 Release 资产上传脚本。
        (Join-Path $resolvedArchiveDirectory 'tools\Upload-ArchiveRelease.ps1'),
        # 上传本守护收尾脚本。
        (Join-Path $resolvedArchiveDirectory 'tools\Finalize-ZhangjinggaoArchive.ps1')
    )
    # 逐项验证辅助资产存在并上传到目标 Release。
    foreach ($supportPath in $supportPaths) {
        # 验证当前辅助资产为普通文件。
        if (-not (Test-Path -LiteralPath $supportPath -PathType Leaf)) {
            # 抛出缺失辅助资产错误。
            throw "恢复辅助文件不存在：$supportPath"
        }
        # 使用 clobber 明确更新同名辅助资产，数据分卷不在该列表中因此不会被覆盖。
        & $ghCommand.Source release upload $ReleaseTag $supportPath --repo $Repository --clobber
        # 检查当前辅助资产上传命令退出码。
        if ($LASTEXITCODE -ne 0) {
            # 抛出包含文件名的上传失败错误。
            throw "恢复辅助文件上传失败：$(Split-Path -Leaf $supportPath)"
        }
    }
    # 读取辅助资产上传后的最新远端 Release 状态。
    $supportReleaseObject = Get-ReleaseObject
    # 创建不区分大小写的远端辅助资产字典。
    $supportRemoteMap = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 将全部远端资产按名称加入字典。
    foreach ($supportRemoteAsset in @($supportReleaseObject.assets)) {
        # 保存当前远端资产；前置完整性函数已经拒绝重复名称。
        $supportRemoteMap[[string]$supportRemoteAsset.name] = $supportRemoteAsset
    }
    # 逐项验证每个辅助资产的远端大小和服务端 SHA-256。
    foreach ($supportPath in $supportPaths) {
        # 读取当前辅助资产文件名。
        $supportName = Split-Path -Leaf $supportPath
        # 验证远端存在当前辅助资产。
        if (-not $supportRemoteMap.ContainsKey($supportName)) {
            # 抛出远端辅助资产缺失错误。
            throw "远端缺少恢复辅助文件：$supportName"
        }
        # 读取当前辅助资产的远端对象。
        $supportRemoteAsset = $supportRemoteMap[$supportName]
        # 读取当前辅助资产本地精确字节数。
        $supportLength = [int64](Get-Item -LiteralPath $supportPath).Length
        # 计算当前辅助资产本地 SHA-256。
        $supportSha256 = (Get-FileHash -LiteralPath $supportPath -Algorithm SHA256).Hash.ToLowerInvariant()
        # 构造 GitHub 服务端摘要格式。
        $supportExpectedDigest = 'sha256:' + $supportSha256
        # 验证远端辅助资产字节数与本地一致。
        if ([int64]$supportRemoteAsset.size -ne $supportLength) {
            # 抛出包含文件名的大小不一致错误。
            throw "恢复辅助文件远端大小不一致：$supportName"
        }
        # 验证远端辅助资产摘要与本地一致。
        if (([string]$supportRemoteAsset.digest).ToLowerInvariant() -ne $supportExpectedDigest) {
            # 抛出包含文件名的摘要不一致错误。
            throw "恢复辅助文件远端 SHA-256 不一致：$supportName"
        }
    }
    # 返回已验证辅助资产数量。
    return [int64]$supportPaths.Count
}

# 定义构建本地保留计划并完整哈希全部候选删除文件的函数。
function New-AndVerifyLocalRetentionPlan {
    # 导入冻结源文件清单。
    $manifestRows = @(Import-Csv -LiteralPath $manifestPath)
    # 创建允许本地保留的扩展名集合，采用不区分大小写比较。
    $retainedExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 定义需要保留的脚本、配置、文本、有限元输入和轻量数据扩展名。
    $retainedExtensionValues = @('.md','.txt','.py','.ps1','.psm1','.mjs','.js','.ts','.tsx','.jsx','.json','.jsonl','.yaml','.yml','.toml','.ini','.cfg','.conf','.xml','.html','.css','.scss','.bat','.cmd','.sh','.mct','.mac','.inp','.cdb','.dat','.csv','.tsv','.tex','.bib','.sql')
    # 将每个允许扩展名加入集合。
    foreach ($retainedExtensionValue in $retainedExtensionValues) {
        # 添加扩展名并丢弃布尔返回值。
        $null = $retainedExtensions.Add($retainedExtensionValue)
    }
    # 创建允许按文件名保留的无扩展名配置集合。
    $retainedFileNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 定义常见无扩展名工程配置和构建入口。
    $retainedFileNameValues = @('.gitignore','.gitattributes','.editorconfig','.npmrc','.python-version','Dockerfile','Makefile')
    # 将每个允许文件名加入集合。
    foreach ($retainedFileNameValue in $retainedFileNameValues) {
        # 添加文件名并丢弃布尔返回值。
        $null = $retainedFileNames.Add($retainedFileNameValue)
    }
    # 创建必须排除的可再生、依赖、缓存、输出和版本库目录段集合。
    $excludedSegments = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    # 定义不进入本地最小保留集的目录段。
    $excludedSegmentValues = @('.git','node_modules','.pnpm-store','__pycache__','.pytest_cache','.workbuddy','.codex_docx_preview','.codex-sdk-uploads','tmp','output','outputs','_agent_scratch','_docx_work')
    # 将每个排除目录段加入集合。
    foreach ($excludedSegmentValue in $excludedSegmentValues) {
        # 添加目录段并丢弃布尔返回值。
        $null = $excludedSegments.Add($excludedSegmentValue)
    }
    # 枚举源目录内全部重解析点，防止通过联接或符号链接越过源目录边界。
    $reparseItems = @(Get-ChildItem -LiteralPath $resolvedSourceRoot -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop)
    # 提取目录型重解析点的规范化绝对路径。
    $reparseDirectoryPaths = @($reparseItems | Where-Object { $_.PSIsContainer } | ForEach-Object { $_.FullName.TrimEnd('\') })
    # 创建保留计划记录列表。
    $retentionRecords = [System.Collections.Generic.List[object]]::new()
    # 创建候选删除记录列表，完成全量哈希后才允许进入实际删除阶段。
    $deleteCandidates = [System.Collections.Generic.List[object]]::new()
    # 初始化计划保留文件总字节数。
    $plannedKeptBytes = [int64]0
    # 初始化计划删除文件总字节数。
    $plannedDeleteBytes = [int64]0
    # 逐项分类冻结清单中的全部文件。
    foreach ($manifestRow in $manifestRows) {
        # 读取当前相对路径。
        $relativePath = [string]$manifestRow.RelativePath
        # 验证清单状态为 OK 且包含 SHA-256。
        if (([string]$manifestRow.Status -ne 'OK') -or [string]::IsNullOrWhiteSpace([string]$manifestRow.SHA256)) {
            # 抛出包含相对路径的基线错误，阻止删除任何文件。
            throw "基线清单存在不可验证文件：$relativePath"
        }
        # 拒绝绝对路径记录，确保所有操作都以冻结源目录为根。
        if ([System.IO.Path]::IsPathRooted($relativePath)) {
            # 抛出包含异常路径的错误。
            throw "清单包含绝对路径：$relativePath"
        }
        # 将路径按 Windows 分隔符拆分为目录段和文件名。
        $pathSegments = @($relativePath -split '[\\/]')
        # 拒绝任何父目录跳转段，防止路径逃逸。
        if ($pathSegments -contains '..') {
            # 抛出包含异常路径的错误。
            throw "清单包含父目录跳转：$relativePath"
        }
        # 读取当前文件名。
        $leafName = [string]$pathSegments[-1]
        # 读取当前文件扩展名。
        $extension = [System.IO.Path]::GetExtension($leafName)
        # 判断任一路径段是否属于明确排除目录。
        $hasExcludedSegment = $false
        # 逐项检查文件名之前的目录段。
        for ($segmentIndex = 0; $segmentIndex -lt ($pathSegments.Count - 1); $segmentIndex++) {
            # 判断当前目录段是否命中排除集合。
            if ($excludedSegments.Contains([string]$pathSegments[$segmentIndex])) {
                # 标记当前文件位于可再生或缓存目录中。
                $hasExcludedSegment = $true
                # 命中后结束目录段检查。
                break
            }
        }
        # 将当前文件长度转换为 64 位整数。
        $fileLength = [int64]$manifestRow.Length
        # 判断当前文件类型是否属于本地最小工程输入集合。
        $isRetainedType = $retainedExtensions.Contains($extension) -or $retainedFileNames.Contains($leafName)
        # 仅保留非排除目录、允许类型且不超过五十 MiB 的文件。
        $shouldKeep = (-not $hasExcludedSegment) -and $isRetainedType -and ($fileLength -le $maximumRetainedFileBytes)
        # 根据分类结果生成稳定操作名称。
        $action = if ($shouldKeep) { 'KEEP' } else { 'DELETE' }
        # 根据分类结果生成可审计原因。
        $reason = if ($shouldKeep) { '轻量脚本、配置、文本或有限元输入' } elseif ($hasExcludedSegment) { '依赖、缓存、输出或版本库内容，可从完整归档恢复' } elseif ($fileLength -gt $maximumRetainedFileBytes) { '文件超过五十 MiB，本地最小集不保留' } else { '非最小工程输入类型，可从完整归档恢复' }
        # 构造当前保留计划记录。
        $retentionRecord = [PSCustomObject][ordered]@{
            # 记录计划动作。
            Action = $action
            # 记录源目录相对路径。
            RelativePath = $relativePath
            # 记录文件精确字节数。
            Length = $fileLength
            # 记录冻结文件 UTC 修改时间。
            LastWriteTimeUtc = [string]$manifestRow.LastWriteTimeUtc
            # 记录冻结文件 SHA-256。
            SHA256 = ([string]$manifestRow.SHA256).ToLowerInvariant()
            # 记录分类原因。
            Reason = $reason
        }
        # 将当前记录加入完整保留计划。
        $retentionRecords.Add($retentionRecord)
        # 根据动作累计字节数并保存候选删除记录。
        if ($shouldKeep) {
            # 累计计划保留字节数。
            $plannedKeptBytes += $fileLength
        }
        # 处理候选删除文件。
        else {
            # 将当前记录加入候选删除列表。
            $deleteCandidates.Add($retentionRecord)
            # 累计计划删除字节数。
            $plannedDeleteBytes += $fileLength
        }
    }
    # 将完整保留计划写为 UTF-8 CSV，供恢复目录和人工审计使用。
    $retentionRecords | Export-Csv -LiteralPath $retentionPlanPath -NoTypeInformation -Encoding utf8
    # 初始化已完成完整哈希验证的候选删除文件数量。
    $verifiedDeleteCount = 0
    # 逐文件验证候选删除文件仍与冻结基线完全一致。
    foreach ($deleteCandidate in $deleteCandidates) {
        # 拼接候选文件绝对路径。
        $candidatePath = [System.IO.Path]::GetFullPath((Join-Path $resolvedSourceRoot ([string]$deleteCandidate.RelativePath)))
        # 验证候选路径严格位于源目录边界内。
        if (-not $candidatePath.StartsWith($sourceBoundaryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            # 抛出包含异常路径的边界错误。
            throw "候选删除路径越过源目录边界：$candidatePath"
        }
        # 验证候选文件存在且为普通文件。
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
            # 抛出包含相对路径的缺失错误。
            throw "候选删除文件不存在：$($deleteCandidate.RelativePath)"
        }
        # 读取候选文件当前元数据。
        $candidateItem = Get-Item -LiteralPath $candidatePath -Force
        # 拒绝删除文件型重解析点。
        if (($candidateItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            # 抛出包含路径的重解析点错误。
            throw "候选删除文件是重解析点：$candidatePath"
        }
        # 逐项检查候选文件是否位于目录型重解析点之下。
        foreach ($reparseDirectoryPath in $reparseDirectoryPaths) {
            # 构造当前重解析目录的边界前缀。
            $reparseBoundaryPrefix = $reparseDirectoryPath + [System.IO.Path]::DirectorySeparatorChar
            # 若候选文件位于重解析目录下则拒绝继续。
            if ($candidatePath.StartsWith($reparseBoundaryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                # 抛出包含候选路径和重解析目录的错误。
                throw "候选删除文件位于重解析目录下：$candidatePath；重解析目录：$reparseDirectoryPath"
            }
        }
        # 验证当前文件字节数仍与冻结基线一致。
        if ([int64]$candidateItem.Length -ne [int64]$deleteCandidate.Length) {
            # 抛出文件大小变化错误。
            throw "候选删除文件大小已变化：$($deleteCandidate.RelativePath)"
        }
        # 验证当前文件 UTC 修改时间仍与冻结基线一致。
        if ($candidateItem.LastWriteTimeUtc.ToString('o') -ne [string]$deleteCandidate.LastWriteTimeUtc) {
            # 抛出文件时间变化错误。
            throw "候选删除文件修改时间已变化：$($deleteCandidate.RelativePath)"
        }
        # 计算候选删除文件当前 SHA-256。
        $candidateSha256 = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        # 验证当前内容哈希仍与冻结基线一致。
        if ($candidateSha256 -ne ([string]$deleteCandidate.SHA256).ToLowerInvariant()) {
            # 抛出内容变化错误，且此时尚未删除任何源文件。
            throw "候选删除文件内容已变化：$($deleteCandidate.RelativePath)"
        }
        # 增加已验证候选删除文件数量。
        $verifiedDeleteCount++
        # 每验证固定数量文件时输出一次进度。
        if (($verifiedDeleteCount % $hashProgressInterval) -eq 0) {
            # 输出包含完成数量和总数量的哈希进度。
            Write-Output ("已完整哈希验证候选删除文件：{0} / {1}" -f $verifiedDeleteCount, $deleteCandidates.Count)
        }
    }
    # 返回保留计划、候选删除列表和容量摘要。
    return [PSCustomObject][ordered]@{
        # 记录已经逐文件完整哈希验证的候选删除记录。
        DeleteCandidates = @($deleteCandidates)
        # 记录计划保留文件数。
        PlannedKeptFiles = [int64]($retentionRecords.Count - $deleteCandidates.Count)
        # 记录计划保留总字节数。
        PlannedKeptBytes = $plannedKeptBytes
        # 记录计划删除文件数。
        PlannedDeleteFiles = [int64]$deleteCandidates.Count
        # 记录计划删除总字节数。
        PlannedDeleteBytes = $plannedDeleteBytes
    }
}

# 定义创建恢复工具包并删除已验证候选文件的函数。
function Invoke-VerifiedLocalPrune {
    # 声明函数参数块，用于接收已完成全量哈希的保留计划和公开 Release URL。
    param(
        # 指定 New-AndVerifyLocalRetentionPlan 返回的已验证计划对象。
        [Parameter(Mandatory = $true)]
        [object]$VerifiedPlan,
        # 指定公开发布后的 GitHub Release URL。
        [Parameter(Mandatory = $true)]
        [string]$PublishedReleaseUrl
    )
    # 定义源目录内恢复工具包目录。
    $recoveryDirectory = Join-Path $resolvedSourceRoot '.archive-recovery'
    # 在恢复工具包目录不存在时创建目录。
    if (-not (Test-Path -LiteralPath $recoveryDirectory -PathType Container)) {
        # 创建明确的恢复目录并丢弃返回对象。
        $null = New-Item -ItemType Directory -Path $recoveryDirectory
    }
    # 构造需要复制到本地恢复工具包的明确文件列表。
    $recoverySourcePaths = @(
        # 复制归档说明文档。
        (Join-Path $resolvedArchiveDirectory 'README.md'),
        # 复制完整源文件清单。
        $manifestPath,
        # 复制源文件摘要。
        $manifestSummaryPath,
        # 复制分卷成员计划。
        $packagePlanPath,
        # 复制分卷计划摘要。
        $packageSummaryPath,
        # 复制远端资产哈希记录。
        $releaseAssetsPath,
        # 复制本地保留计划。
        $retentionPlanPath,
        # 复制完整恢复脚本。
        $restoreScriptPath
    )
    # 逐项复制恢复所需文件到恢复工具包。
    foreach ($recoverySourcePath in $recoverySourcePaths) {
        # 复制并覆盖同名恢复文件，确保工具包与最终远端状态一致。
        Copy-Item -LiteralPath $recoverySourcePath -Destination (Join-Path $recoveryDirectory (Split-Path -Leaf $recoverySourcePath)) -Force
    }
    # 将公开 Release URL 写入独立文本文件，便于无需 GitHub CLI 也能定位归档。
    Set-Content -LiteralPath (Join-Path $recoveryDirectory 'release-url.txt') -Value $PublishedReleaseUrl -Encoding UTF8
    # 初始化成功删除文件数量。
    $deletedFileCount = [int64]0
    # 初始化成功删除总字节数。
    $deletedByteCount = [int64]0
    # 创建删除失败记录列表，失败文件会保留在本地。
    $deletionFailures = [System.Collections.Generic.List[object]]::new()
    # 逐项处理已经全量哈希验证的候选删除文件。
    foreach ($deleteCandidate in @($VerifiedPlan.DeleteCandidates)) {
        # 拼接候选文件绝对路径。
        $candidatePath = [System.IO.Path]::GetFullPath((Join-Path $resolvedSourceRoot ([string]$deleteCandidate.RelativePath)))
        # 在实际删除前再次验证候选路径严格位于源目录内部。
        if (-not $candidatePath.StartsWith($sourceBoundaryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            # 抛出路径边界错误，停止整个删除阶段。
            throw "实际删除路径越过源目录边界：$candidatePath"
        }
        # 尝试删除当前明确文件，任一失败只保留该文件并记录原因。
        try {
            # 读取当前文件元数据，确保哈希验证后没有被删除或替换。
            $candidateItem = Get-Item -LiteralPath $candidatePath -Force
            # 再次验证当前字节数与冻结值一致。
            if ([int64]$candidateItem.Length -ne [int64]$deleteCandidate.Length) {
                # 抛出大小变化错误，使当前文件进入失败记录而不被删除。
                throw '文件大小在完整哈希后发生变化。'
            }
            # 再次验证当前 UTC 修改时间与冻结值一致。
            if ($candidateItem.LastWriteTimeUtc.ToString('o') -ne [string]$deleteCandidate.LastWriteTimeUtc) {
                # 抛出时间变化错误，使当前文件进入失败记录而不被删除。
                throw '文件修改时间在完整哈希后发生变化。'
            }
            # 删除当前已经通过云端、基线、路径和完整哈希质量门的普通文件。
            Remove-Item -LiteralPath $candidatePath -Force
            # 增加成功删除文件数量。
            $deletedFileCount++
            # 累计成功删除字节数。
            $deletedByteCount += [int64]$deleteCandidate.Length
        }
        # 捕获文件占用、权限或最后时刻变化等异常。
        catch {
            # 构造当前删除失败记录。
            $failureRecord = [PSCustomObject][ordered]@{
                # 记录失败文件相对路径。
                RelativePath = [string]$deleteCandidate.RelativePath
                # 记录失败原因。
                Error = $_.Exception.Message
            }
            # 将失败记录加入列表，确保该文件继续保留在本地。
            $deletionFailures.Add($failureRecord)
        }
        # 每处理固定数量文件时输出一次删除进度。
        $processedDeleteCount = $deletedFileCount + [int64]$deletionFailures.Count
        # 判断当前处理数量是否达到进度输出间隔。
        if (($processedDeleteCount % $deleteProgressInterval) -eq 0) {
            # 输出成功、失败和总候选数量。
            Write-Output ("本地精简进度：已删 {0}，保留失败 {1}，总候选 {2}" -f $deletedFileCount, $deletionFailures.Count, @($VerifiedPlan.DeleteCandidates).Count)
        }
    }
    # 定义删除失败 CSV 路径。
    $failureCsvPath = Join-Path $recoveryDirectory 'prune-failures.csv'
    # 将失败记录写入恢复工具包，零失败时仍写字段头由空数组限制无法自动生成，因此仅在有失败时写入。
    if ($deletionFailures.Count -gt 0) {
        # 导出全部删除失败记录。
        $deletionFailures | Export-Csv -LiteralPath $failureCsvPath -NoTypeInformation -Encoding utf8
    }
    # 构造本地精简结果摘要。
    $pruneSummary = [ordered]@{
        # 记录公开 Release URL。
        ReleaseUrl = $PublishedReleaseUrl
        # 记录计划保留文件数，不含恢复工具包自身文件。
        PlannedKeptFiles = [int64]$VerifiedPlan.PlannedKeptFiles
        # 记录计划保留总字节数。
        PlannedKeptBytes = [int64]$VerifiedPlan.PlannedKeptBytes
        # 记录成功删除文件数。
        DeletedFiles = $deletedFileCount
        # 记录成功删除总字节数。
        DeletedBytes = $deletedByteCount
        # 记录因异常而继续保留的候选文件数。
        DeleteFailures = [int64]$deletionFailures.Count
        # 记录精简完成时间，采用 UTC ISO 8601 格式。
        CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
    }
    # 将精简摘要写入恢复工具包。
    $pruneSummary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $recoveryDirectory 'prune-summary.json') -Encoding utf8
    # 若存在删除失败则抛出错误，使守护状态明确标记为未完全精简。
    if ($deletionFailures.Count -gt 0) {
        # 抛出包含失败数量和失败清单路径的错误。
        throw "云端归档已发布，但有 $($deletionFailures.Count) 个本地文件未能精简；详见 $failureCsvPath"
    }
    # 返回成功精简摘要。
    return [PSCustomObject]$pruneSummary
}

# 写入等待上传器阶段状态。
Write-FinalizerStatus -Stage 'WAITING_UPLOAD' -Message "等待上传进程 $UploaderProcessId 完成。" -Data $null
# 持续轮询指定上传进程，只有命令行仍指向本归档上传脚本时才继续等待。
while ($true) {
    # 查询指定进程编号的当前进程对象。
    $uploaderProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$UploaderProcessId" -ErrorAction SilentlyContinue
    # 当进程不存在时结束等待。
    if ($null -eq $uploaderProcess) {
        # 跳出上传器等待循环。
        break
    }
    # 读取当前进程命令行。
    $uploaderCommandLine = [string]$uploaderProcess.CommandLine
    # 当进程编号已被其他程序复用时结束等待并转入结果质量门。
    if (($uploaderCommandLine -notlike '*Upload-ArchiveRelease.ps1*') -or ($uploaderCommandLine -notlike "*$ReleaseTag*")) {
        # 跳出上传器等待循环。
        break
    }
    # 等待固定轮询间隔后再次检查。
    Start-Sleep -Seconds $uploaderPollSeconds
}
# 等待两秒，确保上传器退出前写入的 CSV 和 JSON 已刷新到磁盘。
Start-Sleep -Seconds 2
# 验证上传器最终进度文件存在。
if (-not (Test-Path -LiteralPath $uploadProgressPath -PathType Leaf)) {
    # 抛出缺失进度文件错误。
    throw "上传器未生成最终进度文件：$uploadProgressPath"
}
# 读取上传器最终进度。
$uploadProgress = Get-Content -LiteralPath $uploadProgressPath -Encoding UTF8 -Raw | ConvertFrom-Json
# 验证最终进度对象明确标记全部资产完成。
if (($uploadProgress.PSObject.Properties.Name -notcontains 'AllAssetsCompleted') -or (-not [bool]$uploadProgress.AllAssetsCompleted)) {
    # 抛出包含当前进度内容的错误，禁止继续发布或删除。
    throw "上传器没有完成全部资产：$($uploadProgress | ConvertTo-Json -Compress)"
}

# 写入远端数据资产校验阶段状态。
Write-FinalizerStatus -Stage 'VERIFYING_REMOTE_DATA' -Message '上传器已结束，开始校验全部计划资产的远端大小和 SHA-256。' -Data $uploadProgress
# 执行全部数据资产远端完整性校验。
$remoteArchiveSummary = Assert-RemoteArchiveAssets
# 写入第一次源快照复核阶段状态。
Write-FinalizerStatus -Stage 'VERIFYING_SOURCE_A' -Message '远端数据资产完整，开始第一次相对基线的源快照复核。' -Data $remoteArchiveSummary
# 生成唯一的第一次快照复核目录名称。
$snapshotRunA = 'snapshot-a-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
# 执行第一次独立源快照复核。
$snapshotSummaryA = Test-SourceSnapshotAgainstBaseline -RunName $snapshotRunA
# 等待稳定观察窗口，捕获仍在持续写入的源目录。
Start-Sleep -Seconds $snapshotStabilitySeconds
# 写入第二次源快照复核阶段状态。
Write-FinalizerStatus -Stage 'VERIFYING_SOURCE_B' -Message '第一次源快照无变化，开始第二次独立复核。' -Data $snapshotSummaryA
# 生成唯一的第二次快照复核目录名称。
$snapshotRunB = 'snapshot-b-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
# 执行第二次独立源快照复核。
$snapshotSummaryB = Test-SourceSnapshotAgainstBaseline -RunName $snapshotRunB

# 写入辅助资产上传阶段状态。
Write-FinalizerStatus -Stage 'UPLOADING_SUPPORT' -Message '两次源快照均无变化，开始上传并校验恢复清单与脚本。' -Data $snapshotSummaryB
# 上传并校验全部恢复辅助资产。
$supportAssetCount = Publish-AndVerifySupportAssets
# 将最终 Release 资产记录精确加入 Git 暂存区。
& $gitCommand.Source -C $resolvedRepositoryWorktree add -- 'archive/zhangjinggao/release-assets.csv'
# 检查 Git add 命令退出码。
if ($LASTEXITCODE -ne 0) {
    # 抛出 Git 暂存失败错误。
    throw '无法暂存最终 release-assets.csv。'
}
# 检查最终资产记录是否形成待提交变化。
& $gitCommand.Source -C $resolvedRepositoryWorktree diff --cached --quiet -- 'archive/zhangjinggao/release-assets.csv'
# 保存 Git 暂存区差异检查退出码。
$stagedDiffExitCode = $LASTEXITCODE
# 当退出码为一时提交最终资产记录。
if ($stagedDiffExitCode -eq 1) {
    # 创建仅包含最终资产记录的明确提交。
    & $gitCommand.Source -C $resolvedRepositoryWorktree commit -m 'archive: record verified Zhangjinggao release assets'
    # 检查 Git 提交命令退出码。
    if ($LASTEXITCODE -ne 0) {
        # 抛出提交失败错误。
        throw '无法提交最终 release-assets.csv。'
    }
}
# 当退出码既不是零也不是一时视为 Git 检查失败。
elseif ($stagedDiffExitCode -ne 0) {
    # 抛出暂存区检查失败错误。
    throw "无法检查最终资产记录差异，Git 退出码：$stagedDiffExitCode"
}
# 将当前工作树 HEAD 明确推送到目标分支。
& $gitCommand.Source -C $resolvedRepositoryWorktree push origin ("HEAD:{0}" -f $BranchName)
# 检查 Git 推送命令退出码。
if ($LASTEXITCODE -ne 0) {
    # 抛出推送失败错误，Release 保持草稿且源目录不删。
    throw "无法推送最终资产记录到分支：$BranchName"
}

# 初始化本地保留计划变量，未启用精简时保持为空。
$verifiedRetentionPlan = $null
# 仅在调用方明确启用本地精简时构建计划并执行全量候选哈希。
if ($EnableLocalPrune.IsPresent) {
    # 写入本地候选完整哈希阶段状态。
    Write-FinalizerStatus -Stage 'VERIFYING_PRUNE_CANDIDATES' -Message '开始生成本地最小保留计划，并在删除前完整哈希全部候选文件。' -Data $null
    # 构建本地保留计划并完成所有候选删除文件的逐文件 SHA-256。
    $verifiedRetentionPlan = New-AndVerifyLocalRetentionPlan
    # 写入最后一次源快照复核阶段状态。
    Write-FinalizerStatus -Stage 'VERIFYING_SOURCE_C' -Message '候选删除文件完整哈希通过，执行发布前最后一次源快照复核。' -Data @{ PlannedKeptFiles = $verifiedRetentionPlan.PlannedKeptFiles; PlannedKeptBytes = $verifiedRetentionPlan.PlannedKeptBytes; PlannedDeleteFiles = $verifiedRetentionPlan.PlannedDeleteFiles; PlannedDeleteBytes = $verifiedRetentionPlan.PlannedDeleteBytes }
    # 生成唯一的第三次快照复核目录名称。
    $snapshotRunC = 'snapshot-c-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    # 执行第三次独立源快照复核。
    $snapshotSummaryC = Test-SourceSnapshotAgainstBaseline -RunName $snapshotRunC
}

# 写入最终远端复核阶段状态。
Write-FinalizerStatus -Stage 'FINAL_REMOTE_CHECK' -Message '发布前再次校验全部数据资产，任何差异都会保持草稿并保留源目录。' -Data @{ SupportAssets = $supportAssetCount }
# 再次执行全部数据分卷的远端大小和 SHA-256 校验。
$finalRemoteSummary = Assert-RemoteArchiveAssets
# 读取发布前最新 Release 状态。
$releaseBeforePublish = Get-ReleaseObject
# 仅当 Release 仍为草稿时切换为公开发布。
if ([bool]$releaseBeforePublish.isDraft) {
    # 将已通过全部质量门的 Release 从草稿切换为公开。
    & $ghCommand.Source release edit $ReleaseTag --repo $Repository --draft=false
    # 检查 Release 发布命令退出码。
    if ($LASTEXITCODE -ne 0) {
        # 抛出发布失败错误，源目录保持完整。
        throw "无法发布 GitHub Release：$ReleaseTag"
    }
}
# 读取发布后的最新 Release 状态。
$publishedRelease = Get-ReleaseObject
# 验证 Release 已不再处于草稿状态。
if ([bool]$publishedRelease.isDraft) {
    # 抛出发布状态异常错误。
    throw "GitHub Release 仍处于草稿状态：$ReleaseTag"
}
# 读取公开 Release URL。
$publishedReleaseUrl = [string]$publishedRelease.url
# 写入云端发布完成状态。
Write-FinalizerStatus -Stage 'REMOTE_PUBLISHED' -Message "完整归档已公开发布：$publishedReleaseUrl" -Data $finalRemoteSummary

# 初始化本地精简摘要变量，未启用精简时保持为空。
$pruneSummary = $null
# 仅在调用方明确启用且保留计划已完整验证时执行本地精简。
if ($EnableLocalPrune.IsPresent) {
    # 写入本地精简阶段状态。
    Write-FinalizerStatus -Stage 'PRUNING_LOCAL' -Message '云端完整归档已发布，开始创建恢复工具包并删除已验证的非最小本地文件。' -Data @{ PlannedKeptFiles = $verifiedRetentionPlan.PlannedKeptFiles; PlannedKeptBytes = $verifiedRetentionPlan.PlannedKeptBytes; PlannedDeleteFiles = $verifiedRetentionPlan.PlannedDeleteFiles; PlannedDeleteBytes = $verifiedRetentionPlan.PlannedDeleteBytes }
    # 创建恢复工具包并执行明确文件级精简。
    $pruneSummary = Invoke-VerifiedLocalPrune -VerifiedPlan $verifiedRetentionPlan -PublishedReleaseUrl $publishedReleaseUrl
}

# 构造最终成功摘要。
$finalSummary = [ordered]@{
    # 记录 GitHub 仓库全名。
    Repository = $Repository
    # 记录公开 Release 标签。
    ReleaseTag = $ReleaseTag
    # 记录公开 Release URL。
    ReleaseUrl = $publishedReleaseUrl
    # 记录已验证数据资产数量。
    VerifiedDataAssets = [int64]$finalRemoteSummary.VerifiedAssetCount
    # 记录已验证数据资产总字节数。
    VerifiedDataAssetBytes = [int64]$finalRemoteSummary.VerifiedAssetBytes
    # 记录已验证恢复辅助资产数量。
    VerifiedSupportAssets = [int64]$supportAssetCount
    # 记录是否执行本地精简。
    LocalPruneEnabled = [bool]$EnableLocalPrune.IsPresent
    # 记录本地精简摘要，未启用时为空。
    LocalPruneSummary = $pruneSummary
    # 记录最终完成时间，采用 UTC ISO 8601 格式。
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
}
# 写入最终完成状态。
Write-FinalizerStatus -Stage 'COMPLETE' -Message '张靖皋大桥云端归档与授权的本地最小保留流程已经完成。' -Data $finalSummary
# 输出最终成功摘要，便于日志和后续检查。
[PSCustomObject]$finalSummary
