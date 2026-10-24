# 最终下载索引生成器

当前交付的是生成器、明确未完成的真实身份输入例和接口验证。没有生成最终下载页、最终结果索引或科学报告，也没有读取封存参数、新测试响应数组，或调用 Torch、Matplotlib、VTK、原生求解器。

输入例 `download_inputs.incomplete.example.json` 从实际已成功保存的收据复制路径和 `library_file_id`，没有根据文件名推测远端 ID。它保持 `ready_for_final: false`、非空 `pending` 和未知字段 `null`；因此不能被接受为最终输入。`local_path` 优先于提供方的虚拟 `path`，例如 `/supplement_receipt.json` 不会被误当作本地源文件位置。

## 最终输入约定

所有 `ref` 都是 `{ "path": "绝对路径", "sha256": "完整64位SHA256", "bytes": 123 }`，`bytes` 对元数据引用可省，对下载文件必填。文件没有真实完成时保留 `null`；不得用脚本现场算出的新值覆盖原先不匹配的预期 SHA。

| 输入字段 | 要求 |
|---|---|
| `audits` | 固定 audit 路径的 release verification、20-stage / 8-round completion、V2 full fields、原生身份、6 个最终选中权重 support、V1 同 case 比较、热最终资格。必须引用实际闭合 JSON 及精确 SHA。 |
| `report_receipt` | 冻结 `db652…` 报告生成器真实输出的 `report_receipt.json`。其 HTML、summary 与 generator 字节必须一致；summary.sources 必须包括每份当前独立审计的精确 SHA。 |
| `artifacts[]` | 每项有唯一 `id`、中文 `label`、`group`、`role`、`status: CLOSED_SAVED`、`artifact` 和原始 `save_receipt` 引用。`artifact` 含实际本地 path、完整 SHA、精确 bytes、已返回 `library_file_id`。每个 ID 只能对应它实际保存的路径。 |
| ZIP 项 | 必须另有真实 `package_receipt`，有外部成员清单时再加 `package_manifest`。已关闭、已保存并已清理的重复本地 ZIP 可引用原始 SHA/大小/完整性收据；页面会明确标注没有再次校验不存在的本地副本。普通元数据/报告/图像仍须存在以校验字节。 |
| `archive_sets[]` | 正式摩擦训练、正式 rebar 训练、新测试原始场三个完整集合。`single` 使用完整原始 source manifest；`parts` 引用全部 part artifact IDs、固定 `plan` 与完全重建验证 `reassembly`。缺一份 part 即拒绝。 |
| 分包元数据 | 每份 part receipt、完整 plan、最终 reassembly receipt 也须成为已成功保存的 artifact。仅留瞬态本地路径不能支持最终下载后重建。 |
| `intermediate` | 为 true 时折叠。只有 `superseded_by_sets` 所指最终包中包含每个早期原始成员的同路径/同 SHA，才标为已覆盖；否则可留空并明确标为独立历史快照。 |
| `github` | `repository: Hiram-test/model`、完整 40 位不可变 commit、实际 blob 核对收据。收据必须包含下述固定 schema，并证明该 commit 内报告和索引生成器的真实源字节。不能仅用分支名或缩写 commit。 |
| `v1_archive_index` | 旧 V1 archive index 的真实 Library ID、保存该 ID 的确切原始观察 ref、该 JSON 的显式 `id_key_path`，以及已完成旧数据/权重逐项 SHA 匹配的 dependency inventory。 |

GitHub blob 验证收据由发布者根据实际读取结果写入，不能预填尚未核实的 PASS：

```json
{
  "status": "PASS_GITHUB_COMMIT_AND_ALL_PUBLISHED_BLOBS",
  "repository": "Hiram-test/model",
  "commit": "实际完整40位提交",
  "mismatches": [],
  "verified_files": [
    {
      "repo_path": "automation/local_bridge_operator/v2_delivery/download_index/v2_download_index.py",
      "sha256": "实际完整SHA256",
      "git_blob_sha1": "实际完整Git blob SHA1",
      "bytes": 123
    }
  ]
}
```

其中必须同时包含输入所指 `report_generator_repository_path` 的确切 blob，不只有此示意的一条。Git blob SHA1 包含 `blob <长度>\0` 对象头，不等于只对内容做普通 SHA1。若后续确需改冻结报告版本，必须另行版本化该索引接口及验证，不能绕过既有 SHA 门。

## 生成与验证

准备阶段仅运行接口验证：

```bash
python /dev/shm/bridge_complex_v2_20261025/delivery/download_index/verify_download_index.py
```

待实际原始证据、全部 part 与报告都保存，且 GitHub 固定 commit 的 blob 核对完成后，另存填写完毕的输入 JSON，保留本 incomplete 例不变。确认每项真实闭合后才设置 `ready_for_final: true`、`pending: []`，由 root 明确运行：

```bash
python /dev/shm/bridge_complex_v2_20261025/delivery/download_index/v2_download_index.py --inputs /dev/shm/bridge_complex_v2_20261025/delivery/download_index/download_inputs.final.json --output-directory /dev/shm/bridge_complex_v2_20261025/delivery/download_index/final --final
```

成功输出自包含 `v2_download_index.html`、同内容机器可读 `v2_download_index.json`、二者与输入/源码身份绑定的 `download_index_receipt.json`；然后由 root 保存这三件成品并使用真实返回 ID 交付。最终索引不需要预先猜出自己的保存 ID。任何失败/未知保存、缺 part、缺 original field、缺正式 stage 文件、伪覆盖、旧报告或不完整审计都会拒绝 final，最多写出明确的 blocked 收据，不写最终 HTML/JSON。

## 页面语义

页面分为正式全场训练、新 test/OOD 与误差证据、物理开发、图纸、运行时与再现依赖。每个下载保留精确字节数、SHA256、返回链接及保存收据；每个 part 与其 reconstruction map、全解压/CRC/重建 SHA 收据相连。重建是字节级无损恢复，不是 POD、图粗化或物理简化。

闭合执行与科学资格严格分离：热 `CLOSED_REFERENCE_HOLD` 不因完整性 PASS 而变为热 NN 已训练；decoder `NOT_PROMOTED` 不进入正式 6 个模型；工程放行仍为 `NOT_ESTABLISHED`。索引不会重新计算、修改或夸大任何场误差。

FEM 冷算、回调和训练进程时间是已测分项；候选评分没有独立完整墙钟计量，因此不能把这些分项相加声称端到端总时间或加速比。固定路径科研快照依赖明确归档中的 V1 数据、权重、原生运行时与开发补充内容，不能声称 clone 即可无依赖运行。
