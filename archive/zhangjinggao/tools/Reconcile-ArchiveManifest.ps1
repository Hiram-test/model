# 声明脚本参数块，用于接收源目录和既有清单路径。
param(
    # 指定需要复核的源目录绝对路径。
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    # 指定需要增量协调的完整 CSV 清单路径。
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
)

# 启用严格模式，以便尽早发现字段和变量错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，避免用不完整结果替换既有清单。
$ErrorActionPreference = 'Stop'

# 验证源目录存在且为目录。
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    # 抛出包含实际源路径的错误。
    throw "源目录不存在：$SourceRoot"
}
# 验证既有清单存在且为文件。
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    # 抛出包含实际清单路径的错误。
    throw "既有清单不存在：$ManifestPath"
}

# 将源目录解析为规范化绝对路径。
$resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path.TrimEnd('\')
# 将既有清单解析为规范化绝对路径。
$resolvedManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
# 解析清单父目录，便于保存临时清单、摘要和失败记录。
$manifestDirectory = Split-Path -Parent $resolvedManifestPath
# 定义增量协调临时清单路径，成功前不覆盖正式清单。
$temporaryManifestPath = Join-Path $manifestDirectory 'archive-manifest.reconciled.csv'
# 定义上一次正式清单备份路径，便于异常回退。
$backupManifestPath = Join-Path $manifestDirectory 'archive-manifest.previous.csv'
# 定义最终摘要路径。
$summaryPath = Join-Path $manifestDirectory 'manifest-summary.json'
# 定义增量协调失败记录路径。
$failurePath = Join-Path $manifestDirectory 'manifest-reconcile-failures.csv'

# 定义 CSV 字段转义函数，确保中文、逗号和双引号路径保持有效。
function ConvertTo-CsvField {
    # 声明函数参数块，用于接收待转义字符串。
    param(
        # 指定待转义的原始文本，允许空字符串。
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )
    # 将内部双引号重复，并在字段两侧添加双引号。
    return '"' + $Value.Replace('"', '""') + '"'
}

# 导入既有完整清单，作为未变化文件的哈希缓存。
$existingEntries = @(Import-Csv -LiteralPath $resolvedManifestPath)
# 创建不区分大小写的路径字典，匹配 Windows 文件系统语义。
$existingEntryMap = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::OrdinalIgnoreCase)
# 将既有清单记录加入路径字典。
foreach ($existingEntry in $existingEntries) {
    # 以相对路径为键保存当前既有记录。
    $existingEntryMap[[string]$existingEntry.RelativePath] = $existingEntry
}
# 创建不区分大小写的当前路径集合，用于识别已删除文件。
$currentPathSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
# 枚举当前全部普通文件并按完整路径排序。
$currentFiles = @(Get-ChildItem -LiteralPath $resolvedSourceRoot -File -Recurse -Force | Sort-Object FullName)
# 初始化复用哈希文件计数。
$reusedFileCount = [int64]0
# 初始化新增文件计数。
$addedFileCount = [int64]0
# 初始化重新哈希文件计数。
$rehashedFileCount = [int64]0
# 初始化哈希失败文件计数。
$failureCount = [int64]0
# 初始化当前文件总字节数。
$totalByteCount = [int64]0
# 创建无 BOM 的 UTF-8 编码，兼顾 Git 和分析工具。
$utf8Encoding = [System.Text.UTF8Encoding]::new($false)
# 创建临时主清单写入器。
$manifestWriter = [System.IO.StreamWriter]::new($temporaryManifestPath, $false, $utf8Encoding)
# 创建增量协调失败清单写入器。
$failureWriter = [System.IO.StreamWriter]::new($failurePath, $false, $utf8Encoding)

# 使用 try/finally 确保异常发生时写入器仍会关闭。
try {
    # 写入主清单字段头。
    $manifestWriter.WriteLine('RelativePath,Length,LastWriteTimeUtc,SHA256,Status')
    # 写入失败清单字段头。
    $failureWriter.WriteLine('RelativePath,Error')
    # 逐个处理当前文件，未变化文件复用哈希，变化文件重新计算。
    foreach ($file in $currentFiles) {
        # 计算当前文件相对源目录路径。
        $relativePath = $file.FullName.Substring($resolvedSourceRoot.Length).TrimStart('\')
        # 将当前路径加入当前路径集合。
        $null = $currentPathSet.Add($relativePath)
        # 将当前文件长度转换为 64 位整数。
        $fileLength = [int64]$file.Length
        # 将当前文件 UTC 修改时间转换为 ISO 8601 格式。
        $lastWriteTimeUtc = $file.LastWriteTimeUtc.ToString('o')
        # 初始化既有记录引用变量。
        $existingEntry = $null
        # 查询当前相对路径是否存在既有清单记录。
        $hasExistingEntry = $existingEntryMap.TryGetValue($relativePath, [ref]$existingEntry)
        # 判断长度、时间、状态和哈希是否允许直接复用。
        $canReuseHash = $hasExistingEntry -and ([string]$existingEntry.Status -eq 'OK') -and ([int64]$existingEntry.Length -eq $fileLength) -and ([string]$existingEntry.LastWriteTimeUtc -eq $lastWriteTimeUtc) -and (-not [string]::IsNullOrWhiteSpace([string]$existingEntry.SHA256))
        # 初始化当前文件哈希字段。
        $sha256 = ''
        # 初始化当前文件状态。
        $status = 'OK'
        # 当文件元数据未变化时复用既有 SHA-256。
        if ($canReuseHash) {
            # 读取既有 SHA-256 并统一转换为小写。
            $sha256 = ([string]$existingEntry.SHA256).ToLowerInvariant()
            # 将复用哈希文件计数增加一。
            $reusedFileCount++
        }
        # 当文件新增或发生变化时重新计算 SHA-256。
        else {
            # 区分新增文件和既有变化文件。
            if ($hasExistingEntry) {
                # 将重新哈希文件计数增加一。
                $rehashedFileCount++
            }
            # 处理既有清单中不存在的新文件。
            else {
                # 将新增文件计数增加一。
                $addedFileCount++
            }
            # 尝试计算当前文件 SHA-256。
            try {
                # 使用系统 SHA-256 实现计算哈希并转换为小写。
                $sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            # 捕获文件被占用、权限不足或介质错误等异常。
            catch {
                # 将当前文件状态改为错误。
                $status = 'ERROR'
                # 将失败计数增加一。
                $failureCount++
                # 提取异常消息文本。
                $errorMessage = $_.Exception.Message
                # 写入经过 CSV 转义的失败路径和错误消息。
                $failureWriter.WriteLine((ConvertTo-CsvField -Value $relativePath) + ',' + (ConvertTo-CsvField -Value $errorMessage))
            }
        }
        # 拼接当前文件的完整 CSV 记录。
        $manifestLine = (ConvertTo-CsvField -Value $relativePath) + ',' + (ConvertTo-CsvField -Value ([string]$fileLength)) + ',' + (ConvertTo-CsvField -Value $lastWriteTimeUtc) + ',' + (ConvertTo-CsvField -Value $sha256) + ',' + (ConvertTo-CsvField -Value $status)
        # 将当前文件记录写入临时清单。
        $manifestWriter.WriteLine($manifestLine)
        # 将当前文件长度加入总字节数。
        $totalByteCount += $fileLength
    }
}
# 无论成功或失败都关闭两个写入器。
finally {
    # 释放临时主清单写入器。
    $manifestWriter.Dispose()
    # 释放失败清单写入器。
    $failureWriter.Dispose()
}

# 统计既有清单中当前已经不存在的文件数。
$removedFileCount = [int64]@($existingEntries | Where-Object { -not $currentPathSet.Contains([string]$_.RelativePath) }).Count
# 在覆盖正式清单前复制一份上次清单作为备份。
Copy-Item -LiteralPath $resolvedManifestPath -Destination $backupManifestPath -Force
# 使用已完整关闭的临时清单覆盖正式清单。
Move-Item -LiteralPath $temporaryManifestPath -Destination $resolvedManifestPath -Force
# 构造增量协调摘要对象。
$summary = [ordered]@{
    # 记录规范化源目录。
    SourceRoot = $resolvedSourceRoot
    # 记录协调后的当前文件总数。
    FileCount = [int64]$currentFiles.Count
    # 记录协调后的当前总字节数。
    TotalBytes = $totalByteCount
    # 记录直接复用既有哈希的文件数。
    ReusedFiles = $reusedFileCount
    # 记录新增并完成哈希的文件数。
    AddedFiles = $addedFileCount
    # 记录元数据变化并重新哈希的文件数。
    RehashedFiles = $rehashedFileCount
    # 记录既有清单中已从源目录移除的文件数。
    RemovedFiles = $removedFileCount
    # 记录哈希失败文件数，必须为零才允许后续本地精简。
    HashFailures = $failureCount
    # 记录协调完成时间，使用 UTC ISO 8601 格式。
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
    # 记录哈希算法名称。
    HashAlgorithm = 'SHA256'
}
# 将协调摘要序列化为 JSON 并覆盖摘要文件。
$summary | ConvertTo-Json | Set-Content -LiteralPath $summaryPath -Encoding utf8
# 输出协调摘要对象。
$summary

