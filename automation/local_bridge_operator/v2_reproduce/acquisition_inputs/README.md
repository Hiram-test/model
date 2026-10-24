# V2 closed acquisition input snapshot

本包补齐已闭合 8 轮 acquisition 的输入恢复依赖，分类为 **INPUT_ONLY_NOT_FEM_LABELS**。这不是新增训练、FEM 标签、测试集或后台服务，也没有重新执行 prepare。全部原文件保持原字节。

对照 34 份既存 ZIP/member/source 清单：16 个 rebar 候选的 input-only NPZ 未找到原内容覆盖；钢筋候选共有 96 个原路径未覆盖（16 份 prepared 记录及 80 个目录文件）。摩擦输入和记录已有旧包覆盖。本包仍保存全部 32 份原 prepared 记录，使两族输入可独立恢复；每项先前 exact-path 和 equal-content 匹配保存在 manifest，二者不混称。匹配器识别 member/archive_member/relative_path/repo_path；个别仅 path 键的 GitHub source 引用未计入该匹配列表，因此它不是所有既存来源引用的穷尽清单。3 个 adapter 在其他已识别归档中已有覆盖；该限制不改变 16 个钢筋 NPZ 缺口及 96 个候选原路径结论。

| 原始范围 | 文件数 | 含义 |
|---|---:|---|
| `operator/formal/{friction,rebar}/prepared_inputs/v2_*_candidate_00..15.json` | 32 | 冻结的原始输入记录；不是训练 worker 文件 |
| `friction/prepared/v2_friction_candidate_00..15/` | 64 | 每个目录的 fields.npz、metadata、descriptor、input_identity |
| `rebar/native/candidates/v2_rebar_candidate_00..15/` | 80 | 每个目录的 inputs.npz、metadata、model.inp、prepared_row、prepared_receipt |
| 既存摩擦 `native/cases/v2_friction_candidate_*/contact.inp` | 7 | 只复制原输入 deck；未读相邻求解输出/响应 |
| 实际 preparation adapter 源码 | 3 | friction adapter、rebar v3 和 v4 的原字节 |

总计 186 个原文件，22,322,439 B。32 个图保留全部节点/IP/通道，不做 POD 或采样。摩擦文件虽名为 `fields.npz`，其原 quality 是 `INPUT_ONLY_UNSOLVED`；生产源码构建零未来状态占位和已知 controls/prescribed。钢筋原 quality 是 `UNSOLVED_CANDIDATE`，原提交回执为 `COMMITTED_INPUT_ONLY`。**本次只流式读取 NPZ 字节并核 SHA/CRC，未解码数组，未重新数值检查全零状态；input-only 语义依据原记录及已审阅生产源码。**

钢筋 candidate_00 的原 prepared_receipt 绑定 v3 adapter，其他 15 个绑定 v4；保留历史来源，不改成当前版本。所有 32 份 prepared 记录中的 NPZ/metadata SHA、16 份钢筋 card 的 4 个成员 SHA、全部既存 deck SHA 均逐一核对。8 份 acquisition completion 仅用于闭合检查和 SHA/stat 证据，未扩大归档到其引用的 FEM 标签。

摩擦 prepare 从来没有落盘 contact.inp。未求解的 9 个候选没有原 deck 文件可保存，具体 ID 和原 deck SHA 见 `missing_original_friction_decks`；本包不伪造或重生成这些文件。已有 7 个原 deck 与输入身份 SHA 一致。原 descriptor、输入图、identity 和已冻结生成源码保留了输入重放依据。摩擦实际 deck 生成另依赖 V1 `automation/local_bridge_operator/complex_friction.py` 及其原环境；这些既有依赖依照 `V2_REPRODUCE.md` 恢复，不把本包称为完整可安装运行环境。

先在隔离目录解压本包的 helper 和 manifest，并核对外部 `snapshot_receipt.json` 给出的 ZIP SHA。只验证，不写任何候选文件：

```sh
python -E restore_acquisition_inputs.py closed_acquisition_inputs_snapshot.zip
```

恢复至一个**尚不存在、无软链接祖先且没有并发进程使用**的隔离目录：

```sh
python -E restore_acquisition_inputs.py closed_acquisition_inputs_snapshot.zip --restore-root /tmp/bridge-inputs-recovery
```

工具先核所有原 payload SHA/CRC/长度，再创建新目录；目标已存在即拒绝，不覆盖任何源。文件按 manifest 的原相对路径恢复，内嵌绝对路径原样保留。若要重放原 path-bound 锁，应在隔离机器/容器恢复原 `/dev/shm/bridge_complex_v2_20261025` 及完整原 V1 路径并核完整依赖锁，不能覆盖本次运行中的目录。迁移路径、重建任一缺失 deck、改变程序/环境或发起新计算，均应使用新 run 身份和重新冻结；不能将挪路径后旧 hash 锁仍有效当作事实。

此包不含任何新 heldout/sealed 输入或响应，也未读取 live training 权重、日志或事件。每块 I/O 上限 1 MiB、纯标准库、无 Torch/NumPy/solver。逐成员完整解压后的 CRC/SHA/长度以及所有源前后 SHA/stat 稳定性由外部 receipt 记录；actual peak RSS 也在 receipt，不以估计值冒充实测。
