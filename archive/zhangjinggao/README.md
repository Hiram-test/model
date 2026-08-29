# 张靖皋大桥完整归档

本目录记录 `D:\张靖皋大桥` 在 2026-07-29 的完整归档与恢复信息。

## 归档范围

- 源目录中的全部普通文件，包括六个编号主项目、输出目录、工具、缓存、嵌套仓库工作树和根目录文件。
- 空目录不会进入文件分卷；恢复后可根据项目需要重新创建。
- 文件清单记录相对路径、字节数、UTC 修改时间和 SHA-256。
- 大型数据不会直接进入 Git 历史，而是存放在仓库的 `zhangjinggao-full-20260729` GitHub Release 中。

## 文件说明

- `archive-manifest.csv`：全部源文件的逐文件校验清单。
- `manifest-summary.json`：归档文件数、总字节数、哈希失败数和生成时间。
- `package-members.csv`：每个 Release 资产包含或重建哪些源文件。
- `package-members.summary.json`：当前文件数、资产数、分卷分类数量、分卷目标大小、增量文件数、旧路径删除数和完成时间。
- `release-assets.csv`：Release 资产大小与 SHA-256 清单。
- `delta-deletions.csv`：基础分卷完成后必须删除的旧路径；用于准确还原上传期间发生的目录移动和删除。
- `Restore-Zhangjinggao.ps1`：下载并恢复全部分卷的脚本。

CSV 和 JSON 格式本身不支持注释，因此字段含义统一在本文档中说明。

`delta-deletions.csv` 的 `RelativePath` 表示基础快照中的旧相对路径，`BaseLength` 和 `BaseSHA256` 表示旧文件的字节数与摘要，`Reason` 表示进入删除清单的原因。该清单只在恢复副本中使用，不会用于修改作为归档源的当前 `_github\doc`。

## 恢复原则

1. 下载 Release 中全部 `archive-*.tar.zst`、`large-*.part.tar.zst` 和清单文件。
2. 按名称顺序解开基础 TAR 与后续增量 TAR，后解开的增量文件覆盖旧版本。
3. 按 `package-members.csv` 中的偏移顺序拼接大型文件分片。
4. 按 `delta-deletions.csv` 删除基础分卷中已被当前快照移动或删除的旧路径。
5. 使用 `archive-manifest.csv` 对恢复文件执行 SHA-256 校验。
6. 只有远端资产数量、大小和哈希全部通过后，才允许精简源目录。

## 本地保留策略

远端完整归档验证前不删除任何源文件。验证后本地至少保留恢复脚本、全部清单、项目说明、脚本、配置和有限元输入文件；大型可再生成结果、缓存和重复输出才进入候选清理范围。

用户指定以 `_github\doc` 当前新增和重组后的内容为准，因此该目录整体属于本地强制保留范围；归档和精简流程只读取与校验，不修改或删除其中任何文件。

`Finalize-ZhangjinggaoArchive.ps1` 仅在全部计划资产的远端大小与 SHA-256 一致、源目录连续快照无变化、恢复辅助文件上传校验成功、候选删除文件逐文件 SHA-256 与基线一致后发布 Release。启用本地精简时，脚本会在源目录的 `.archive-recovery` 中保留恢复工具包。

`local-retention-plan.csv` 的 `Action` 表示保留或删除计划，`RelativePath` 表示相对源目录路径，`Length` 表示字节数，`LastWriteTimeUtc` 表示冻结修改时间，`SHA256` 表示冻结内容摘要，`Reason` 表示分类原因。`prune-summary.json` 记录公开 Release URL、计划保留数量与容量、实际删除数量与容量、删除失败数量和完成时间；`prune-failures.csv` 仅在文件占用或最后时刻变化等异常发生时生成。
