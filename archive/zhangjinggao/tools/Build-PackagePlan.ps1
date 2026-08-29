# 声明脚本参数块，用于接收完整清单和分卷计划输出路径。
param(
    # 指定由 Build-ArchiveManifest.ps1 生成的完整 CSV 清单。
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    # 指定分卷成员计划 CSV 的输出路径。
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,
    # 指定普通 TAR 分卷的目标源文件字节数，默认一千五百 MiB。
    [Parameter(Mandatory = $false)]
    [int64]$TargetAssetBytes = 1572864000
)

# 启用严格模式，以便尽早发现字段名和变量错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，防止生成不完整计划。
$ErrorActionPreference = 'Stop'

# 验证完整清单存在，缺失时无法构建可追溯分卷计划。
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    # 抛出包含实际清单路径的错误，方便调用方修正配置。
    throw "完整清单不存在：$ManifestPath"
}
# 验证目标分卷大小为正数，防止除零或无限循环。
if ($TargetAssetBytes -le 0) {
    # 抛出包含实际值的错误，说明目标大小配置无效。
    throw "目标分卷字节数必须大于零：$TargetAssetBytes"
}

# 解析分卷计划父目录，便于在不存在时创建。
$planDirectory = Split-Path -Parent $PlanPath
# 在分卷计划父目录不存在时创建目录。
if (-not (Test-Path -LiteralPath $planDirectory -PathType Container)) {
    # 创建父目录并丢弃目录对象，保持脚本输出简洁。
    $null = New-Item -ItemType Directory -Path $planDirectory -Force
}

# 导入哈希成功的源文件记录，并按相对路径排序以保证计划可重复。
$manifestEntries = @(Import-Csv -LiteralPath $ManifestPath | Where-Object Status -eq 'OK' | Sort-Object RelativePath)
# 初始化分卷成员记录列表，用于最终统一导出 CSV。
$planRows = [System.Collections.Generic.List[object]]::new()
# 初始化当前 TAR 分卷编号，编号从一开始。
$tarAssetNumber = 1
# 初始化当前 TAR 分卷累计源文件字节数，初始为零字节。
$currentTarBytes = [int64]0
# 初始化当前大型文件编号，编号从一开始。
$largeFileNumber = 1

# 逐个处理清单文件，根据大小分配到 TAR 分卷或独立字节分片。
foreach ($entry in $manifestEntries) {
    # 将清单中的文件长度转换为 64 位整数，避免大文件溢出。
    $fileLength = [int64]$entry.Length
    # 判断当前文件是否大于单个目标分卷容量。
    if ($fileLength -gt $TargetAssetBytes) {
        # 若当前 TAR 分卷已经包含文件，则推进到下一个 TAR 编号。
        if ($currentTarBytes -gt 0) {
            # 将 TAR 分卷编号增加一，避免大型文件后的普通文件混用旧名称。
            $tarAssetNumber++
            # 将当前 TAR 分卷累计字节数重置为零。
            $currentTarBytes = [int64]0
        }
        # 初始化当前大型文件分片偏移，首个分片从零字节开始。
        $sourceOffset = [int64]0
        # 初始化当前大型文件分片序号，序号从一开始。
        $partNumber = 1
        # 在尚未覆盖完整源文件时持续生成分片记录。
        while ($sourceOffset -lt $fileLength) {
            # 计算源文件从当前偏移到结尾尚余的字节数。
            $remainingBytes = $fileLength - $sourceOffset
            # 选择目标分卷大小和剩余字节数中的较小值作为当前分片长度。
            $partLength = [int64][Math]::Min($TargetAssetBytes, $remainingBytes)
            # 生成仅含 ASCII 的 Zstandard 压缩分片资产名称，避免 Release 接口编码差异。
            $assetName = 'large-{0:d4}-part-{1:d3}.part.tar.zst' -f $largeFileNumber, $partNumber
            # 添加当前大型文件分片的完整恢复映射记录。
            $planRows.Add([PSCustomObject][ordered]@{
                # 记录 GitHub Release 资产文件名。
                AssetName = $assetName
                # 标记当前资产为压缩字节分片，恢复时需要解包后顺序拼接。
                PackageType = 'PART_ZST'
                # 记录源文件相对张靖皋大桥根目录的路径。
                RelativePath = [string]$entry.RelativePath
                # 记录当前分片在源文件中的起始字节偏移。
                SourceOffset = $sourceOffset
                # 记录当前分片包含的精确字节数。
                SourceLength = $partLength
                # 记录完整源文件 SHA-256，用于恢复后的最终校验。
                SourceSHA256 = [string]$entry.SHA256
            })
            # 将源文件偏移推进当前分片长度。
            $sourceOffset += $partLength
            # 将当前大型文件分片序号增加一。
            $partNumber++
        }
        # 将大型文件编号增加一，为下一个大型文件生成唯一资产名称。
        $largeFileNumber++
        # 当前大型文件已完成计划，继续处理下一个清单文件。
        continue
    }
    # 判断当前文件加入现有 TAR 后是否会超过目标容量。
    if (($currentTarBytes -gt 0) -and (($currentTarBytes + $fileLength) -gt $TargetAssetBytes)) {
        # 将 TAR 分卷编号增加一，为当前文件开始新的分卷。
        $tarAssetNumber++
        # 将新 TAR 分卷累计字节数重置为零。
        $currentTarBytes = [int64]0
    }
    # 生成当前普通 Zstandard 压缩 TAR 分卷资产名称。
    $tarAssetName = 'archive-{0:d4}.tar.zst' -f $tarAssetNumber
    # 添加当前普通文件在 TAR 分卷中的成员映射记录。
    $planRows.Add([PSCustomObject][ordered]@{
        # 记录 GitHub Release 资产文件名。
        AssetName = $tarAssetName
        # 标记当前资产为 TAR，恢复时直接解包。
        PackageType = 'TAR'
        # 记录源文件相对张靖皋大桥根目录的路径。
        RelativePath = [string]$entry.RelativePath
        # 普通 TAR 成员不使用源偏移，因此固定为零字节。
        SourceOffset = [int64]0
        # 记录当前源文件的完整字节数。
        SourceLength = $fileLength
        # 记录当前源文件 SHA-256，用于恢复后的最终校验。
        SourceSHA256 = [string]$entry.SHA256
    })
    # 将当前 TAR 分卷累计字节数增加当前文件长度。
    $currentTarBytes += $fileLength
}

# 将分卷成员计划导出为 UTF-8 CSV，供上传和恢复脚本共同使用。
$planRows | Export-Csv -LiteralPath $PlanPath -NoTypeInformation -Encoding utf8
# 统计唯一 Release 资产数量，确认不超过平台每个 Release 一千项限制。
$assetCount = @($planRows | Select-Object -ExpandProperty AssetName -Unique).Count
# 统计普通 TAR 资产数量。
$tarAssetCount = @($planRows | Where-Object PackageType -eq 'TAR' | Select-Object -ExpandProperty AssetName -Unique).Count
# 统计大型文件压缩字节分片资产数量。
$partAssetCount = @($planRows | Where-Object PackageType -eq 'PART_ZST' | Select-Object -ExpandProperty AssetName -Unique).Count
# 构造分卷计划摘要对象，便于调用方执行质量门检查。
$summary = [ordered]@{
    # 记录参与分卷计划的源文件数量。
    SourceFileCount = $manifestEntries.Count
    # 记录唯一 Release 资产总数量。
    AssetCount = $assetCount
    # 记录普通 TAR 资产数量。
    TarAssetCount = $tarAssetCount
    # 记录大型文件分片资产数量。
    PartAssetCount = $partAssetCount
    # 记录每个分卷的目标源字节数。
    TargetAssetBytes = $TargetAssetBytes
    # 记录分卷计划完成时间，使用 UTC ISO 8601 格式。
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
}
# 将分卷计划摘要序列化为 JSON 并写入计划旁的摘要文件。
$summary | ConvertTo-Json | Set-Content -LiteralPath ([System.IO.Path]::ChangeExtension($PlanPath, '.summary.json')) -Encoding utf8
# 输出摘要对象，便于调用方直接读取计划结果。
$summary



