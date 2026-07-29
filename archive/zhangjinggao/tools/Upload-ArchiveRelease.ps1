# 声明脚本参数块，用于接收源目录、分卷计划和 GitHub Release 配置。
param(
    # 指定张靖皋大桥完整源目录绝对路径。
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    # 指定由 Build-PackagePlan.ps1 生成的分卷成员计划。
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,
    # 指定 GitHub 仓库全名，格式必须为 owner/name。
    [Parameter(Mandatory = $true)]
    [string]$Repository,
    # 指定 GitHub Release 标签名称。
    [Parameter(Mandatory = $true)]
    [string]$ReleaseTag,
    # 指定 Release 所关联的 Git 分支或提交。
    [Parameter(Mandatory = $true)]
    [string]$ReleaseTarget,
    # 指定临时分卷目录，目录必须位于可用空间充足的本地磁盘。
    [Parameter(Mandatory = $true)]
    [string]$TemporaryRoot,
    # 指定本次最多处理的资产数，零表示处理全部剩余资产。
    [Parameter(Mandatory = $false)]
    [int]$MaximumAssets = 0,
    # 指定全部上传成功后是否立即发布草稿 Release。
    [Parameter(Mandatory = $false)]
    [switch]$PublishOnSuccess
)

# 启用严格模式，以便尽早发现字段和变量错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，防止误删未上传的临时分卷。
$ErrorActionPreference = 'Stop'

# 验证源目录存在且为目录。
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    # 抛出包含实际路径的错误，方便修正配置。
    throw "源目录不存在：$SourceRoot"
}
# 验证分卷计划存在且为文件。
if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf)) {
    # 抛出包含实际路径的错误，防止空计划上传。
    throw "分卷计划不存在：$PlanPath"
}
# 验证仓库全名包含一个斜杠，降低误传到错误仓库的风险。
if ($Repository -notmatch '^[^/]+/[^/]+$') {
    # 抛出包含实际值的错误，说明仓库格式无效。
    throw "GitHub 仓库格式无效：$Repository"
}
# 验证最多资产数不小于零。
if ($MaximumAssets -lt 0) {
    # 抛出包含实际值的错误，说明限制参数无效。
    throw "MaximumAssets 不能小于零：$MaximumAssets"
}

# 将源目录解析为规范化绝对路径，保证路径拼接和 tar 工作目录稳定。
$resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path.TrimEnd('\')
# 在临时分卷目录不存在时创建目录。
if (-not (Test-Path -LiteralPath $TemporaryRoot -PathType Container)) {
    # 创建临时目录并丢弃目录对象，保持脚本输出简洁。
    $null = New-Item -ItemType Directory -Path $TemporaryRoot -Force
}
# 将临时分卷目录解析为规范化绝对路径，供删除安全检查使用。
$resolvedTemporaryRoot = (Resolve-Path -LiteralPath $TemporaryRoot).Path.TrimEnd('\')
# 将分卷计划路径解析为规范化绝对路径。
$resolvedPlanPath = (Resolve-Path -LiteralPath $PlanPath).Path
# 解析分卷计划父目录，用于保存资产哈希和进度文件。
$planDirectory = Split-Path -Parent $resolvedPlanPath
# 定义资产哈希清单路径，记录每个远端资产的大小和 SHA-256。
$releaseAssetsPath = Join-Path $planDirectory 'release-assets.csv'
# 定义上传进度路径，供后台任务轮询。
$uploadProgressPath = Join-Path $planDirectory 'release-upload-progress.json'

# 验证 GitHub CLI 已安装并可调用。
$ghCommand = Get-Command gh -ErrorAction Stop
# 验证系统 tar 命令已安装并可调用。
$tarCommand = Get-Command tar.exe -ErrorAction Stop
# 调用 GitHub CLI 检查当前认证状态。
& $ghCommand.Source auth status
# 检查认证命令退出码，非零表示无法安全上传。
if ($LASTEXITCODE -ne 0) {
    # 抛出认证失败错误并停止。
    throw 'GitHub CLI 当前未通过认证。'
}

# 定义安全删除临时文件的函数，只允许删除临时根目录内的明确文件。
function Remove-VerifiedTemporaryFile {
    # 声明函数参数块，用于接收待删除文件路径。
    param(
        # 指定已经上传并验证的临时文件绝对路径。
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    # 将待删除文件解析为规范化绝对路径。
    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    # 构造临时根目录前缀，并附加目录分隔符防止前缀碰撞。
    $temporaryPrefix = $resolvedTemporaryRoot + [System.IO.Path]::DirectorySeparatorChar
    # 验证待删除文件确实位于临时根目录内部。
    if (-not $resolvedPath.StartsWith($temporaryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        # 抛出拒绝删除错误，防止路径计算异常伤及源数据。
        throw "拒绝删除临时根目录外的文件：$resolvedPath"
    }
    # 删除已经通过远端大小校验的临时分卷文件。
    Remove-Item -LiteralPath $resolvedPath -Force
}

# 定义读取远端 Release 资产列表的函数。
function Get-RemoteReleaseAssets {
    # 调用 GitHub CLI 获取 Release 资产名称和大小。
    $releaseJson = & $ghCommand.Source release view $ReleaseTag --repo $Repository --json assets
    # 检查查询命令退出码，非零表示 Release 不可访问。
    if ($LASTEXITCODE -ne 0) {
        # 抛出包含标签名称的错误，阻止在未知远端状态下继续。
        throw "无法读取 GitHub Release：$ReleaseTag"
    }
    # 将 JSON 文本解析为对象。
    $releaseObject = $releaseJson | ConvertFrom-Json
    # 返回资产数组，调用方按名称和大小执行校验。
    return @($releaseObject.assets)
}

# 定义创建 TAR 资产的函数，将计划中的普通文件打包并保留相对路径。
function New-TarAsset {
    # 声明函数参数块，用于接收资产名称和成员记录。
    param(
        # 指定当前 TAR Release 资产名称。
        [Parameter(Mandatory = $true)]
        [string]$AssetName,
        # 指定当前 TAR 包含的全部分卷成员记录。
        [Parameter(Mandatory = $true)]
        [object[]]$Members
    )
    # 拼接当前 TAR 临时文件的完整路径。
    $assetPath = Join-Path $resolvedTemporaryRoot $AssetName
    # 拼接当前 TAR 文件列表的临时路径。
    $listPath = Join-Path $resolvedTemporaryRoot ($AssetName + '.files.txt')
    # 将 Windows 路径分隔符转换为 tar 更稳定支持的正斜杠。
    $relativePaths = @($Members | ForEach-Object { ([string]$_.RelativePath).Replace('\','/') })
    # 将成员路径以无 BOM UTF-8 写入 tar 文件列表。
    [System.IO.File]::WriteAllLines($listPath, $relativePaths, [System.Text.UTF8Encoding]::new($false))
    # 使用系统 tar 从源目录创建未压缩分卷，避免额外磁盘峰值和恢复依赖。
    & $tarCommand.Source -cf $assetPath -C $resolvedSourceRoot -T $listPath
    # 保存 tar 命令退出码，供清理文件列表后检查。
    $tarExitCode = $LASTEXITCODE
    # 删除仅用于创建当前 TAR 的临时文件列表。
    Remove-VerifiedTemporaryFile -Path $listPath
    # 检查 tar 命令退出码，非零表示分卷不完整。
    if ($tarExitCode -ne 0) {
        # 若失败 TAR 文件存在，则删除该临时不完整文件。
        if (Test-Path -LiteralPath $assetPath -PathType Leaf) {
            # 删除临时不完整 TAR，防止后续误上传。
            Remove-VerifiedTemporaryFile -Path $assetPath
        }
        # 抛出包含资产名称和退出码的错误。
        throw "创建 TAR 失败：$AssetName，退出码：$tarExitCode"
    }
    # 返回成功创建的 TAR 临时文件路径。
    return $assetPath
}

# 定义创建大型文件字节分片的函数。
function New-PartAsset {
    # 声明函数参数块，用于接收资产名称和唯一成员记录。
    param(
        # 指定当前大型文件分片的 Release 资产名称。
        [Parameter(Mandatory = $true)]
        [string]$AssetName,
        # 指定当前分片对应的唯一成员记录。
        [Parameter(Mandatory = $true)]
        [object]$Member
    )
    # 拼接源大型文件的完整路径。
    $sourcePath = Join-Path $resolvedSourceRoot ([string]$Member.RelativePath)
    # 验证源大型文件存在，防止生成空分片。
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        # 抛出包含源相对路径的错误。
        throw "大型源文件不存在：$($Member.RelativePath)"
    }
    # 拼接当前分片临时文件的完整路径。
    $assetPath = Join-Path $resolvedTemporaryRoot $AssetName
    # 将清单偏移转换为 64 位整数。
    $sourceOffset = [int64]$Member.SourceOffset
    # 将清单分片长度转换为 64 位整数。
    $sourceLength = [int64]$Member.SourceLength
    # 创建八 MiB 复制缓冲区，兼顾顺序读写吞吐和内存占用。
    $buffer = New-Object byte[] (8MB)
    # 打开源大型文件为只读流，并允许其他进程继续读取。
    $sourceStream = [System.IO.File]::Open($sourcePath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    # 创建分片输出流，并覆盖任何同名未完成临时文件。
    $partStream = [System.IO.File]::Open($assetPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    # 使用 try/finally 确保两个文件流始终关闭。
    try {
        # 将源文件读取位置移动到计划指定偏移。
        $null = $sourceStream.Seek($sourceOffset, [System.IO.SeekOrigin]::Begin)
        # 初始化尚需复制的字节数。
        $remainingBytes = $sourceLength
        # 在当前分片仍有字节需要复制时持续读取。
        while ($remainingBytes -gt 0) {
            # 计算本轮最多读取字节数，不超过缓冲区和剩余字节。
            $requestedBytes = [int][Math]::Min($buffer.Length, $remainingBytes)
            # 从源文件读取本轮字节。
            $readBytes = $sourceStream.Read($buffer, 0, $requestedBytes)
            # 检查是否意外到达文件末尾。
            if ($readBytes -le 0) {
                # 抛出源文件截断错误，防止上传不完整分片。
                throw "源文件在计划长度之前结束：$($Member.RelativePath)"
            }
            # 将读取到的字节写入当前分片。
            $partStream.Write($buffer, 0, $readBytes)
            # 从剩余字节数中扣除本轮已复制字节。
            $remainingBytes -= $readBytes
        }
    }
    # 无论复制成功或失败都关闭文件流。
    finally {
        # 释放分片输出流并刷新缓冲数据。
        $partStream.Dispose()
        # 释放源文件读取流。
        $sourceStream.Dispose()
    }
    # 验证生成分片大小与计划长度完全一致。
    if ((Get-Item -LiteralPath $assetPath).Length -ne $sourceLength) {
        # 删除长度不一致的临时分片。
        Remove-VerifiedTemporaryFile -Path $assetPath
        # 抛出包含资产名称的长度校验错误。
        throw "大型文件分片长度校验失败：$AssetName"
    }
    # 返回成功创建的分片临时文件路径。
    return $assetPath
}

# 检查目标 Release 是否已经存在。
& $ghCommand.Source release view $ReleaseTag --repo $Repository *> $null
# 保存 Release 查询退出码，供后续决定是否创建。
$releaseViewExitCode = $LASTEXITCODE
# 在目标 Release 不存在时创建草稿 Release。
if ($releaseViewExitCode -ne 0) {
    # 创建草稿 Release，并指向用户允许使用的归档分支。
    & $ghCommand.Source release create $ReleaseTag --repo $Repository --target $ReleaseTarget --title '张靖皋大桥完整归档 2026-07-29' --notes '完整数据按 TAR 和大型文件字节分片存储；恢复与 SHA-256 校验方法见归档分支。' --draft
    # 检查 Release 创建命令退出码。
    if ($LASTEXITCODE -ne 0) {
        # 抛出创建失败错误并停止。
        throw "无法创建草稿 GitHub Release：$ReleaseTag"
    }
}

# 导入完整分卷计划。
$planRows = @(Import-Csv -LiteralPath $resolvedPlanPath)
# 按资产名称分组并排序，保证上传顺序稳定。
$assetGroups = @($planRows | Group-Object AssetName | Sort-Object Name)
# 初始化已完成资产记录列表。
$assetRecords = [System.Collections.Generic.List[object]]::new()
# 若存在之前的资产记录，则导入以支持断点续传。
if (Test-Path -LiteralPath $releaseAssetsPath -PathType Leaf) {
    # 将既有资产记录逐条加入内存列表。
    foreach ($existingRecord in (Import-Csv -LiteralPath $releaseAssetsPath)) {
        # 保留既有资产记录，避免重复计算和上传。
        $assetRecords.Add($existingRecord)
    }
}
# 读取远端 Release 当前资产列表。
$remoteAssets = @(Get-RemoteReleaseAssets)
# 初始化本次已处理资产数。
$processedThisRun = 0
# 初始化全部已完成资产数。
$completedAssetCount = 0

# 逐个处理计划资产，支持已上传资产跳过和单资产验证运行。
foreach ($assetGroup in $assetGroups) {
    # 若本次设置了资产上限且已经达到，则结束循环。
    if (($MaximumAssets -gt 0) -and ($processedThisRun -ge $MaximumAssets)) {
        # 跳出资产循环，将剩余资产留给下次续传。
        break
    }
    # 读取当前资产名称。
    $assetName = [string]$assetGroup.Name
    # 查找当前资产是否已存在于远端 Release。
    $remoteAsset = $remoteAssets | Where-Object name -eq $assetName | Select-Object -First 1
    # 查找当前资产是否已有本地哈希记录。
    $existingRecord = $assetRecords | Where-Object AssetName -eq $assetName | Select-Object -First 1
    # 当远端资产和本地记录同时存在且大小一致时直接跳过。
    if (($null -ne $remoteAsset) -and ($null -ne $existingRecord) -and ([int64]$remoteAsset.size -eq [int64]$existingRecord.Length)) {
        # 将全部已完成资产数增加一。
        $completedAssetCount++
        # 继续处理下一个计划资产。
        continue
    }
    # 若远端存在资产但本地没有可信记录，则停止以避免无意覆盖。
    if (($null -ne $remoteAsset) -and ($null -eq $existingRecord)) {
        # 抛出远端状态不明错误，要求人工核查该资产。
        throw "远端已存在但本地无哈希记录的资产：$assetName"
    }
    # 读取当前资产的包类型，组内所有成员必须一致。
    $packageTypes = @($assetGroup.Group | Select-Object -ExpandProperty PackageType -Unique)
    # 验证当前资产仅包含一种包类型。
    if ($packageTypes.Count -ne 1) {
        # 抛出包含资产名称的计划错误。
        throw "资产包含多种包类型：$assetName"
    }
    # 读取当前资产唯一包类型。
    $packageType = [string]$packageTypes[0]
    # 根据包类型创建 TAR 或大型文件分片。
    if ($packageType -eq 'TAR') {
        # 创建包含当前组全部普通文件的 TAR 资产。
        $assetPath = New-TarAsset -AssetName $assetName -Members @($assetGroup.Group)
    }
    # 处理大型文件字节分片类型。
    elseif ($packageType -eq 'PART') {
        # 验证每个分片资产仅对应一条成员记录。
        if ($assetGroup.Count -ne 1) {
            # 抛出包含资产名称的分片计划错误。
            throw "大型文件分片资产对应多条成员记录：$assetName"
        }
        # 创建当前大型文件字节分片资产。
        $assetPath = New-PartAsset -AssetName $assetName -Member $assetGroup.Group[0]
    }
    # 拒绝任何未知包类型，避免不可恢复资产进入 Release。
    else {
        # 抛出包含实际包类型和资产名称的错误。
        throw "未知包类型 $packageType：$assetName"
    }
    # 读取当前临时资产的精确字节数。
    $assetLength = [int64](Get-Item -LiteralPath $assetPath).Length
    # 验证资产严格小于 GitHub Release 的二 GiB 单文件限制。
    if ($assetLength -ge 2GB) {
        # 删除超限临时资产，防止误上传失败。
        Remove-VerifiedTemporaryFile -Path $assetPath
        # 抛出包含资产名称和实际大小的错误。
        throw "资产达到或超过 2 GiB：$assetName，字节数：$assetLength"
    }
    # 计算当前临时资产 SHA-256，并统一转换为小写。
    $assetSha256 = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    # 上传当前资产到草稿 Release。
    & $ghCommand.Source release upload $ReleaseTag $assetPath --repo $Repository
    # 检查上传命令退出码，失败时保留临时资产以便重试。
    if ($LASTEXITCODE -ne 0) {
        # 抛出上传失败错误，不删除当前临时资产。
        throw "GitHub Release 资产上传失败：$assetName"
    }
    # 刷新远端 Release 资产列表，用于核对实际接收大小。
    $remoteAssets = @(Get-RemoteReleaseAssets)
    # 查找刚上传的远端资产记录。
    $uploadedRemoteAsset = $remoteAssets | Where-Object name -eq $assetName | Select-Object -First 1
    # 验证远端资产存在且字节数与本地完全一致。
    if (($null -eq $uploadedRemoteAsset) -or ([int64]$uploadedRemoteAsset.size -ne $assetLength)) {
        # 抛出远端大小校验失败错误，并保留本地临时资产。
        throw "远端资产大小校验失败：$assetName"
    }
    # 创建当前资产完成记录。
    $assetRecord = [PSCustomObject][ordered]@{
        # 记录 Release 资产文件名。
        AssetName = $assetName
        # 记录资产包类型。
        PackageType = $packageType
        # 记录资产精确字节数。
        Length = $assetLength
        # 记录资产 SHA-256。
        SHA256 = $assetSha256
        # 记录上传完成时间，使用 UTC ISO 8601 格式。
        UploadedAtUtc = [DateTime]::UtcNow.ToString('o')
    }
    # 将当前资产记录加入内存列表。
    $assetRecords.Add($assetRecord)
    # 将全部资产记录覆盖导出为 UTF-8 CSV，形成断点续传状态。
    $assetRecords | Sort-Object AssetName | Export-Csv -LiteralPath $releaseAssetsPath -NoTypeInformation -Encoding utf8
    # 删除已通过远端大小校验的临时资产，释放本地空间。
    Remove-VerifiedTemporaryFile -Path $assetPath
    # 将本次已处理资产数增加一。
    $processedThisRun++
    # 将全部已完成资产数增加一。
    $completedAssetCount++
    # 构造当前上传进度对象。
    $uploadProgress = [ordered]@{
        # 记录计划资产总数。
        TotalAssets = $assetGroups.Count
        # 记录已经确认完成的资产数。
        CompletedAssets = $completedAssetCount
        # 记录本次运行实际新上传资产数。
        UploadedThisRun = $processedThisRun
        # 记录最后完成的资产名称。
        LastCompletedAsset = $assetName
        # 记录进度更新时间，使用 UTC ISO 8601 格式。
        UpdatedAtUtc = [DateTime]::UtcNow.ToString('o')
    }
    # 将上传进度写入 JSON 文件。
    $uploadProgress | ConvertTo-Json | Set-Content -LiteralPath $uploadProgressPath -Encoding utf8
}

# 判断全部计划资产是否已经完成上传。
$allAssetsCompleted = ($completedAssetCount -eq $assetGroups.Count)
# 构造本次运行最终摘要对象。
$finalSummary = [ordered]@{
    # 记录计划资产总数。
    TotalAssets = $assetGroups.Count
    # 记录已经确认完成的资产数。
    CompletedAssets = $completedAssetCount
    # 记录本次运行实际新上传资产数。
    UploadedThisRun = $processedThisRun
    # 记录是否全部完成。
    AllAssetsCompleted = $allAssetsCompleted
    # 记录运行结束时间，使用 UTC ISO 8601 格式。
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
}
# 将最终摘要写入上传进度 JSON 文件。
$finalSummary | ConvertTo-Json | Set-Content -LiteralPath $uploadProgressPath -Encoding utf8

# 仅在全部资产完成且调用方明确要求时发布草稿 Release。
if ($allAssetsCompleted -and $PublishOnSuccess.IsPresent) {
    # 将目标 Release 从草稿状态切换为公开发布状态。
    & $ghCommand.Source release edit $ReleaseTag --repo $Repository --draft=false
    # 检查 Release 发布命令退出码。
    if ($LASTEXITCODE -ne 0) {
        # 抛出发布失败错误，但不影响已经上传的草稿资产。
        throw "全部资产已上传，但发布 Release 失败：$ReleaseTag"
    }
}

# 输出最终摘要对象，便于调用方确认完成度。
$finalSummary

