# 声明脚本参数块，用于接收源目录和清单输出目录。
param(
    # 指定需要归档的源目录绝对路径，目录必须已存在且可读。
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    # 指定清单输出目录绝对路径，目录不存在时由脚本创建。
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

# 启用严格模式，以便尽早发现未初始化变量和属性拼写错误。
Set-StrictMode -Version Latest
# 将所有非终止错误提升为终止错误，确保失败不会被静默忽略。
$ErrorActionPreference = 'Stop'

# 验证源目录是否存在，防止对错误路径生成空清单。
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    # 抛出包含实际输入路径的错误，便于定位配置问题。
    throw "源目录不存在：$SourceRoot"
}

# 将源目录解析为规范化绝对路径，保证相对路径计算稳定。
$resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path.TrimEnd('\')
# 在输出目录不存在时创建目录，以便保存清单和进度文件。
if (-not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
    # 创建输出目录并丢弃目录对象，避免污染脚本标准输出。
    $null = New-Item -ItemType Directory -Path $OutputDirectory -Force
}
# 将输出目录解析为规范化绝对路径，保证后续路径拼接稳定。
$resolvedOutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path.TrimEnd('\')
# 定义逐文件归档清单路径，CSV 便于机器读取和人工审计。
$manifestPath = Join-Path $resolvedOutputDirectory 'archive-manifest.csv'
# 定义归档摘要路径，JSON 用于快速读取总数和总容量。
$summaryPath = Join-Path $resolvedOutputDirectory 'manifest-summary.json'
# 定义生成进度路径，便于后台运行时检查完成度。
$progressPath = Join-Path $resolvedOutputDirectory 'manifest-progress.json'
# 定义哈希失败日志路径，便于对被占用或损坏文件单独重试。
$failurePath = Join-Path $resolvedOutputDirectory 'manifest-failures.csv'

# 定义 CSV 字段转义函数，确保中文、逗号和双引号路径保持有效。
function ConvertTo-CsvField {
    # 声明函数参数块，用于接收待转义字符串。
    param(
        # 指定待转义的原始文本，允许传入空字符串但不允许省略。
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )
    # 将内部双引号重复，并在字段两侧添加双引号以满足 RFC 4180 规则。
    return '"' + $Value.Replace('"', '""') + '"'
}

# 枚举全部普通文件并按完整路径排序，使清单顺序可重复生成。
$files = @(Get-ChildItem -LiteralPath $resolvedSourceRoot -File -Recurse -Force | Sort-Object FullName)
# 记录待处理文件总数，供进度和摘要使用。
$totalFileCount = [int64]$files.Count
# 初始化已处理文件计数，初始值为零个文件。
$processedFileCount = [int64]0
# 初始化累计字节数，初始值为零字节。
$totalByteCount = [int64]0
# 初始化哈希失败计数，初始值为零个文件。
$failureCount = [int64]0
# 创建无 BOM 的 UTF-8 编码，兼顾 Git 和常用分析工具。
$utf8Encoding = [System.Text.UTF8Encoding]::new($false)
# 创建主清单流写入器，避免在内存中保存全部哈希对象。
$manifestWriter = [System.IO.StreamWriter]::new($manifestPath, $false, $utf8Encoding)
# 创建失败清单流写入器，单独记录无法读取的文件。
$failureWriter = [System.IO.StreamWriter]::new($failurePath, $false, $utf8Encoding)

# 使用 try/finally 确保异常发生时两个写入器仍会被正确关闭。
try {
    # 写入主清单字段头，明确相对路径、大小、时间、哈希和状态列。
    $manifestWriter.WriteLine('RelativePath,Length,LastWriteTimeUtc,SHA256,Status')
    # 写入失败清单字段头，明确失败文件路径和错误原因列。
    $failureWriter.WriteLine('RelativePath,Error')
    # 逐个处理文件，以便对每个文件计算独立 SHA-256。
    foreach ($file in $files) {
        # 将完整路径转换为相对源目录路径，恢复时以此重建目录结构。
        $relativePath = $file.FullName.Substring($resolvedSourceRoot.Length).TrimStart('\')
        # 将当前文件长度转换为 64 位整数，避免大文件溢出。
        $fileLength = [int64]$file.Length
        # 将修改时间统一转换为 UTC 的 ISO 8601 格式，避免时区歧义。
        $lastWriteTimeUtc = $file.LastWriteTimeUtc.ToString('o')
        # 初始化当前文件哈希字段为空字符串，成功后再写入实际值。
        $sha256 = ''
        # 初始化当前文件状态为成功，异常路径会改为错误。
        $status = 'OK'
        # 尝试读取并计算文件哈希，单文件失败不阻断其他文件清单生成。
        try {
            # 使用系统 SHA-256 实现计算文件内容哈希，并统一转换为小写。
            $sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        # 捕获文件被占用、权限不足或介质错误等读取异常。
        catch {
            # 将当前文件状态改为错误，防止误认为已完成校验。
            $status = 'ERROR'
            # 将失败计数增加一个文件，用于最终质量门判断。
            $failureCount++
            # 提取异常消息文本，作为后续重试和诊断依据。
            $errorMessage = $_.Exception.Message
            # 写入经过 CSV 转义的相对路径和错误消息。
            $failureWriter.WriteLine((ConvertTo-CsvField -Value $relativePath) + ',' + (ConvertTo-CsvField -Value $errorMessage))
        }
        # 将五个主清单字段分别执行 CSV 转义并拼接成一行。
        $manifestLine = (ConvertTo-CsvField -Value $relativePath) + ',' + (ConvertTo-CsvField -Value ([string]$fileLength)) + ',' + (ConvertTo-CsvField -Value $lastWriteTimeUtc) + ',' + (ConvertTo-CsvField -Value $sha256) + ',' + (ConvertTo-CsvField -Value $status)
        # 将当前文件记录写入主清单。
        $manifestWriter.WriteLine($manifestLine)
        # 将累计字节数增加当前文件长度。
        $totalByteCount += $fileLength
        # 将已处理文件计数增加一个文件。
        $processedFileCount++
        # 每处理一百个文件刷新一次清单和进度，降低异常中断时的数据损失。
        if (($processedFileCount % 100) -eq 0) {
            # 将主清单缓冲区刷新到磁盘。
            $manifestWriter.Flush()
            # 将失败清单缓冲区刷新到磁盘。
            $failureWriter.Flush()
            # 构造当前进度对象，包含文件计数、字节数和失败数。
            $progress = [ordered]@{
                # 记录待处理文件总数，单位为个。
                TotalFiles = $totalFileCount
                # 记录已经完成哈希的文件数，单位为个。
                ProcessedFiles = $processedFileCount
                # 记录已处理文件的累计逻辑字节数，单位为字节。
                ProcessedBytes = $totalByteCount
                # 记录当前哈希失败文件数，单位为个。
                Failures = $failureCount
                # 记录进度更新时间，使用 UTC ISO 8601 格式。
                UpdatedAtUtc = [DateTime]::UtcNow.ToString('o')
            }
            # 将进度对象序列化为 JSON 并覆盖进度文件。
            $progress | ConvertTo-Json | Set-Content -LiteralPath $progressPath -Encoding utf8
        }
    }
}
# 无论成功或失败都执行资源释放，防止文件句柄长期占用。
finally {
    # 刷新并关闭主清单写入器，确保末尾内容完整落盘。
    $manifestWriter.Dispose()
    # 刷新并关闭失败清单写入器，确保异常记录完整落盘。
    $failureWriter.Dispose()
}

# 构造最终摘要对象，记录完整清单质量和规模。
$summary = [ordered]@{
    # 记录规范化源目录，说明清单对应的数据来源。
    SourceRoot = $resolvedSourceRoot
    # 记录实际完成清单的文件总数，单位为个。
    FileCount = $processedFileCount
    # 记录全部文件的累计逻辑大小，单位为字节。
    TotalBytes = $totalByteCount
    # 记录哈希失败文件总数，必须为零才允许后续本地精简。
    HashFailures = $failureCount
    # 记录清单完成时间，使用 UTC ISO 8601 格式。
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
    # 记录哈希算法名称，恢复校验必须使用相同算法。
    HashAlgorithm = 'SHA256'
}
# 将最终摘要序列化为 JSON 并写入摘要文件。
$summary | ConvertTo-Json | Set-Content -LiteralPath $summaryPath -Encoding utf8
# 将最终摘要同时覆盖进度文件，表示后台任务已经完成。
$summary | ConvertTo-Json | Set-Content -LiteralPath $progressPath -Encoding utf8
# 输出摘要对象，便于调用方直接读取处理结果。
$summary

