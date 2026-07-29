# 声明恢复脚本参数块，用于接收下载目录和恢复目标目录。
param(
    # 指定已经下载全部 Release 资产的本地目录。
    [Parameter(Mandatory = $true)]
    [string]$AssetDirectory,
    # 指定恢复张靖皋大桥文件结构的目标目录。
    [Parameter(Mandatory = $true)]
    [string]$RestoreRoot
)

# 启用严格模式，以便尽早发现恢复清单或变量错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，避免产生不完整但表面成功的恢复结果。
$ErrorActionPreference = 'Stop'

# 验证资产目录是否存在，防止在错误目录中执行恢复。
if (-not (Test-Path -LiteralPath $AssetDirectory -PathType Container)) {
    # 抛出包含实际输入路径的错误，方便用户修正下载位置。
    throw "Release 资产目录不存在：$AssetDirectory"
}
# 在恢复目标目录不存在时创建目录，承载全部解包结果。
if (-not (Test-Path -LiteralPath $RestoreRoot -PathType Container)) {
    # 创建恢复目录并丢弃目录对象，保持脚本输出简洁。
    $null = New-Item -ItemType Directory -Path $RestoreRoot -Force
}

# 将资产目录解析为规范化绝对路径，保证清单查找稳定。
$resolvedAssetDirectory = (Resolve-Path -LiteralPath $AssetDirectory).Path.TrimEnd('\')
# 将恢复目录解析为规范化绝对路径，保证安全校验和路径拼接稳定。
$resolvedRestoreRoot = (Resolve-Path -LiteralPath $RestoreRoot).Path.TrimEnd('\')
# 定义分卷成员清单路径，用于识别 TAR 分卷和大型文件分片。
$packageMembersPath = Join-Path $resolvedAssetDirectory 'package-members.csv'
# 定义完整文件哈希清单路径，用于恢复后的逐文件验证。
$archiveManifestPath = Join-Path $resolvedAssetDirectory 'archive-manifest.csv'

# 验证分卷成员清单存在，缺失时无法可靠恢复大型文件。
if (-not (Test-Path -LiteralPath $packageMembersPath -PathType Leaf)) {
    # 抛出明确错误并停止，避免仅恢复部分文件。
    throw "缺少分卷成员清单：$packageMembersPath"
}
# 验证完整文件清单存在，缺失时无法确认恢复结果完整性。
if (-not (Test-Path -LiteralPath $archiveManifestPath -PathType Leaf)) {
    # 抛出明确错误并停止，避免交付未经校验的数据。
    throw "缺少完整文件清单：$archiveManifestPath"
}

# 导入分卷成员清单，供后续按资产类型恢复。
$packageMembers = @(Import-Csv -LiteralPath $packageMembersPath)
# 筛选 TAR 类型资产并去重，保证每个 TAR 只解包一次。
$tarAssets = @($packageMembers | Where-Object PackageType -eq 'TAR' | Select-Object -ExpandProperty AssetName -Unique | Sort-Object)
# 逐个解包 TAR 资产，以相对路径恢复普通文件。
foreach ($tarAsset in $tarAssets) {
    # 拼接当前 TAR 资产的本地完整路径。
    $tarAssetPath = Join-Path $resolvedAssetDirectory $tarAsset
    # 验证当前 TAR 资产存在，防止跳过缺失分卷。
    if (-not (Test-Path -LiteralPath $tarAssetPath -PathType Leaf)) {
        # 抛出包含缺失资产名称的错误，方便重新下载。
        throw "缺少 TAR 资产：$tarAsset"
    }
    # 使用系统 tar 将当前分卷解包到恢复根目录。
    & tar.exe -xf $tarAssetPath -C $resolvedRestoreRoot
    # 检查 tar 退出码，非零表示当前分卷解包失败。
    if ($LASTEXITCODE -ne 0) {
        # 抛出包含资产名称和退出码的错误，阻止继续产生混合状态。
        throw "TAR 解包失败：$tarAsset，退出码：$LASTEXITCODE"
    }
}

# 筛选原始或压缩大型文件分片记录并按目标路径分组。
$largePartGroups = @($packageMembers | Where-Object { $_.PackageType -in @('PART','PART_ZST') } | Group-Object RelativePath)
# 逐个重建被拆分的大型文件。
foreach ($largePartGroup in $largePartGroups) {
    # 读取当前目标文件的相对路径。
    $relativePath = [string]$largePartGroup.Name
    # 拼接当前目标文件的恢复完整路径。
    $targetPath = Join-Path $resolvedRestoreRoot $relativePath
    # 获取目标文件父目录路径。
    $targetDirectory = Split-Path -Parent $targetPath
    # 在父目录不存在时创建目录，确保文件流能够建立。
    if (-not (Test-Path -LiteralPath $targetDirectory -PathType Container)) {
        # 创建父目录并丢弃目录对象，保持脚本输出简洁。
        $null = New-Item -ItemType Directory -Path $targetDirectory -Force
    }
    # 创建目标文件流并覆盖任何同名旧恢复文件。
    $targetStream = [System.IO.File]::Open($targetPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    # 使用 try/finally 确保异常发生时目标文件流仍会关闭。
    try {
        # 按源文件偏移升序处理每个分片，保证字节顺序正确。
        foreach ($part in ($largePartGroup.Group | Sort-Object {[int64]$_.SourceOffset})) {
            # 拼接当前分片资产的本地完整路径。
            $partAssetPath = Join-Path $resolvedAssetDirectory $part.AssetName
            # 验证当前分片资产存在，防止生成截断文件。
            if (-not (Test-Path -LiteralPath $partAssetPath -PathType Leaf)) {
                # 抛出包含缺失分片名称的错误，方便重新下载。
                throw "缺少大型文件分片：$($part.AssetName)"
            }
            # 默认直接使用原始分片资产作为读取路径。
            $partPath = $partAssetPath
            # 判断当前分片是否采用 Zstandard 压缩 TAR 包装。
            $isCompressedPart = ([string]$part.PackageType -eq 'PART_ZST')
            # 对压缩分片先解包出临时原始字节文件。
            if ($isCompressedPart) {
                # 使用资产名称加 raw 后缀推导压缩包内的唯一成员名称。
                $rawPartName = ([string]$part.AssetName) + '.raw'
                # 使用系统 tar 将当前压缩分片解包到资产目录。
                & tar.exe -xf $partAssetPath -C $resolvedAssetDirectory
                # 检查 tar 解包退出码。
                if ($LASTEXITCODE -ne 0) {
                    # 抛出包含资产名称和退出码的解包错误。
                    throw "大型压缩分片解包失败：$($part.AssetName)，退出码：$LASTEXITCODE"
                }
                # 将读取路径切换为刚解包的原始字节文件。
                $partPath = Join-Path $resolvedAssetDirectory $rawPartName
                # 验证解包后的原始分片存在。
                if (-not (Test-Path -LiteralPath $partPath -PathType Leaf)) {
                    # 抛出缺失解包成员错误。
                    throw "大型压缩分片缺少预期成员：$rawPartName"
                }
            }
            # 打开当前分片为只读流，准备顺序复制到目标文件。
            $partStream = [System.IO.File]::OpenRead($partPath)
            # 使用 try/finally 确保每个分片读取流及时关闭。
            try {
                # 将当前分片全部复制到目标文件流的当前位置。
                $partStream.CopyTo($targetStream)
            }
            # 无论复制成功或失败都关闭当前分片读取流。
            finally {
                # 释放当前分片读取流及其文件句柄。
                $partStream.Dispose()
            }
            # 对压缩分片在复制完成后删除可重新解包的临时原始字节文件。
            if ($isCompressedPart) {
                # 解析临时原始分片绝对路径，用于删除范围校验。
                $resolvedRawPartPath = (Resolve-Path -LiteralPath $partPath).Path
                # 构造资产目录内部路径前缀。
                $assetDirectoryPrefix = $resolvedAssetDirectory + [System.IO.Path]::DirectorySeparatorChar
                # 验证临时原始分片严格位于资产目录内部。
                if (-not $resolvedRawPartPath.StartsWith($assetDirectoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                    # 路径越界时拒绝删除。
                    throw "拒绝删除资产目录外的临时原始分片：$resolvedRawPartPath"
                }
                # 删除已经复制到目标文件且可由压缩资产重建的临时原始分片。
                Remove-Item -LiteralPath $resolvedRawPartPath -Force
            }
        }
    }
    # 无论重建成功或失败都关闭目标文件写入流。
    finally {
        # 释放目标文件写入流并将缓冲数据刷新到磁盘。
        $targetStream.Dispose()
    }
}

# 导入完整文件清单，用于逐文件 SHA-256 验证。
$archiveManifest = @(Import-Csv -LiteralPath $archiveManifestPath)
# 初始化恢复校验失败列表，初始为空集合。
$verificationFailures = [System.Collections.Generic.List[object]]::new()
# 逐条验证应成功归档的文件，跳过源端已记录为错误的文件。
foreach ($entry in ($archiveManifest | Where-Object Status -eq 'OK')) {
    # 拼接当前恢复文件的完整路径。
    $restoredPath = Join-Path $resolvedRestoreRoot $entry.RelativePath
    # 检查当前恢复文件是否存在。
    if (-not (Test-Path -LiteralPath $restoredPath -PathType Leaf)) {
        # 将缺失文件记录到校验失败列表。
        $verificationFailures.Add([PSCustomObject]@{RelativePath=$entry.RelativePath;Reason='MISSING'})
        # 跳过当前文件的哈希计算并继续处理下一条记录。
        continue
    }
    # 计算当前恢复文件 SHA-256，并统一转换为小写进行比较。
    $actualHash = (Get-FileHash -LiteralPath $restoredPath -Algorithm SHA256).Hash.ToLowerInvariant()
    # 比较实际哈希与归档清单哈希是否完全一致。
    if ($actualHash -ne $entry.SHA256.ToLowerInvariant()) {
        # 将哈希不一致文件记录到校验失败列表。
        $verificationFailures.Add([PSCustomObject]@{RelativePath=$entry.RelativePath;Reason='SHA256_MISMATCH'})
    }
}

# 若存在任何校验失败，则输出失败清单并终止恢复。
if ($verificationFailures.Count -gt 0) {
    # 定义恢复校验失败清单路径。
    $verificationFailurePath = Join-Path $resolvedAssetDirectory 'restore-verification-failures.csv'
    # 将失败记录导出为 UTF-8 CSV，供重新下载或诊断。
    $verificationFailures | Export-Csv -LiteralPath $verificationFailurePath -NoTypeInformation -Encoding utf8
    # 抛出包含失败数量和清单位置的错误。
    throw "恢复校验失败 $($verificationFailures.Count) 个文件，详见：$verificationFailurePath"
}

# 输出成功消息，明确全部可校验文件已经通过 SHA-256。
Write-Output "恢复完成并通过 SHA-256 校验：$resolvedRestoreRoot"


