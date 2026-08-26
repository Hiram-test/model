# 动力后处理单作业强绑定规则

全部历史动力模态结果已永久删除，当前不存在可供本脚本处理的旧作业。只有将来按唯一run_id、唯一jobname和完整manifest产生的新作业才允许进入本流程。

`modal_identification_pipeline.py` 现已实施以下硬检查：

1. 必须且只能提供一次 `--frequency-source`；
2. 禁止自动发现频率表、SET表或模态日志；
3. `raw-dir` 中发现第二份来源立即失败；
4. 必须提供位于 `raw-dir` 内的 `--job-manifest`；
5. manifest必须绑定唯一`run_id`、`job_name`、频率文件及全部向量SHA-256；
6. `--output-dir`必须位于`raw-dir`内，并且在启动时尚不存在；
7. 不允许从其他目录引用频率文件、向量或manifest。

## Manifest最小结构

```json
{
  "schema_version": 1,
  "run_id": "唯一运行编号",
  "job_name": "与本次MAPDL作业名完全一致",
  "raw_dir": ".",
  "frequency_source": "唯一频率文件.txt",
  "frequency_source_sha256": "64位SHA-256",
  "mode_files": [
    {
      "mode_number": 1,
      "path": "mode_01_all_nodes.txt",
      "sha256": "64位SHA-256"
    }
  ]
}
```

在新的独立运行框架和manifest生成器获得明确授权前，不得启动动力求解。
