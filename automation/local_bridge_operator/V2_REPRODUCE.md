# V2 复现与恢复

本轮是**可复用命令驱动的有限实验闭环**：冻结输入与预算，训练，按优先级或随机策略补算，两轮续训，冻结选中模型，再独立解封测试。它不是永久后台服务。中断后的复用依赖实际阶段提交和事件链，不能把“脚本存在”当作任务已完成。

正式架构为 `v2_complete_graph_physical_head_v1`。摩擦保留 697 个实体、15 通道；钢筋保留 5,232 个实体、3,024 个真实积分点、24 通道。没有 POD、模态截断或节点降采样；TBPTT 4 只截断反向梯度，不重置完整预测历史。独立 hard-decoder 探针是另一架构，结论为 `NOT_PROMOTED`，不替代正式模型。

## 恢复材料与已核覆盖

V1 最终提交为 `f5fd0a7d84a27bf9cb6edec849cffd7ebe5e37e3`。V2 冻结源码检查点为 `654bb21c9f717c47f35359836aadda264c1e3c80`；后续交付应按文件 SHA 核对，不以分支当前名称代替身份。

| 已保存材料 | 用途与限制 |
|---|---|
| [V1 14 分包下载索引](https://chatgpt.com/library?file_id=libfile_8419d7a50080819190b4c06ae6b63585&account_id=personal) | 3,963,490,652 B。逐成员清单确认下述 68 项旧依赖均有对应 SHA；不是只凭压缩包名称判断。 |
| [V2 开发与原生证据](https://chatgpt.com/library?file_id=libfile_12e586ca42748191ae4ae96f3755e911&account_id=personal) | 已闭合开发/原生证据及候选公开输入；不含正式执行锁、controller 配置、trainer，也不含封存新测试输入。 |
| [摩擦训练与获取检查点](https://chatgpt.com/library?file_id=libfile_f9e10dfd0410819198b644ea30ca0b85&account_id=personal) | 已闭合摩擦阶段、权重、实际工作与获取账本；不代表两族最终测试完成。 |
| [钢筋 initial seed 17](https://chatgpt.com/library?file_id=libfile_07fa221d8a1c81918d5bb06abf06f4bc&account_id=personal)、[seed 41](https://chatgpt.com/library?file_id=libfile_b48f243e7cbc819186fc7f5e785f9435&account_id=personal) | 各自已完成的正式初始训练阶段；不能代替后续阶段和最终解封证据。 |
| [热力最终参考包](https://chatgpt.com/library?file_id=libfile_7c61caef23ec8191a5e83cb4e06f5b8d&account_id=personal) | 完整参考研究仍为 `CLOSED_REFERENCE_HOLD`，不含热力神经算子训练。另有[中网格历史包](https://chatgpt.com/library?file_id=libfile_3b982c8645e8819183978de4f528a57a&account_id=personal)。 |
| [独立 decoder 探针](https://chatgpt.com/library?file_id=libfile_8c98987ce0548191b272da4c7c38f30c&account_id=personal) | 2 epoch、96 次额外开发优化，原生/梯度核验通过但 NN 误差未达标；不进入正式选模。 |
| [局部图纸与原生证据](https://chatgpt.com/library?file_id=libfile_92fcf24eb6108191905450ebb3f78fa8&account_id=personal) | 可复查已有图纸，不是桥梁竣工详图认证。 |

旧依赖清单见 `v2_evidence/reproduce_dependency_inventory.json`：两族各原 8 train + 3 validation 的 **44 个 fields/metadata 文件、2 个 index、2 个旧实验合同、4 个 V1 initial 权重、16 份成本 receipt，共 68/68 个身份**，与 V1 分包成员 SHA 完全一致，位于 parts `01/02/03/05/06/07`。此次清单审计未加载模型或大 ZIP 的响应数据。原始数据恢复时按索引中的 SHA 校验；不要用后来的 V2 initial 权重冒充 V1 初始化。

运行时另有 [bridge_v2_native_runtime.zip](https://chatgpt.com/library?file_id=libfile_a742c1abb2188191892934b5059b8922&account_id=personal) 与[校验回执](https://chatgpt.com/library?file_id=libfile_0720fdb6609c8191a40a1a25ef89a300&account_id=personal)：ZIP SHA256 `9c04452746330b8d03e3f59af90750d44bdd6dc10c44ddf3608a63169a4ba584`，14,802,529 B。它保存实际 wrapper/binary、18 项 `ldd` 启动依赖、原 `.deb`、上游源码、v2 精度修改收据与许可证文本。系统库放在隔离快照目录；恢复脚本只复制私有前缀，不安装或覆盖系统库。

[闭合开发依赖补充包](https://chatgpt.com/library?file_id=libfile_b811dff0e21481918148efd3a497860f&account_id=personal)、[完整清单](https://chatgpt.com/library?file_id=libfile_930f4f1c67088191940f4de4ac853929&account_id=personal)和[回执](https://chatgpt.com/library?file_id=libfile_f0368473c3ac8191b2a92fabd96ac2bc&account_id=personal)补齐最早 V2 ZIP 未覆盖的 12 个锁定开发引用及相关 13 个 model/progress 权重。ZIP 为 3,496,900 B，SHA256 `3befbf953ed6b5a9a629222893dad8739bf291ff65bd76af68e00c66b16625b9`。8 个开发训练运行已闭合；3 个历史运行原本没有现代事件链，归档没有补造这些记录。

## 原路径恢复与最小核验

下列命令只用于**从空目录建立、无预置内部符号链接、无并发运行的隔离恢复环境**。恢复脚本的检查使用 `assert`，须使用普通 Python，不能加 `-O`；下面恢复命令的 `-E` 同时避免环境中的 `PYTHONOPTIMIZE` 禁用检查。运行中的工作目录不能被归档解压覆盖。

```bash
BRIDGE_OLD=/workspace/scratch/500ec816102b/model-repo
BRIDGE_V2=/dev/shm/bridge_complex_v2_20261025
BRIDGE_PY=python
BRIDGE_CFG="$BRIDGE_V2/operator/v2_controller_config.json"
export PYTHONPATH="$BRIDGE_OLD/automation/local_bridge_operator${PYTHONPATH:+:$PYTHONPATH}"
```

1. 将已核验的 GitHub 源码恢复到 `BRIDGE_OLD`。V1 分包的 `build/...` 成员相对于此仓库根目录恢复，保留各分包 manifest；V2 包的 `audit/`、`operator/`、`friction/` 等成员相对于 `BRIDGE_V2` 恢复。先分别解压检查，再按清单合并相同 SHA 的成员；遇到同路径不同 SHA 应停止，不用覆盖消除冲突。封存测试输入和最终测试交付只能由对应审计/解封证据恢复，不能由公开候选文件替代。
2. `v2_evidence/runtime_source_mapping.json` 给出 28 个正式源/配置文件的仓库路径、运行时绝对路径和 SHA。以下步骤恢复原绝对路径，已经存在且内容不同的文件会拒绝覆盖。公共合同、执行锁、成本合同与两份已发布开发摘要从仓库证据副本恢复：

```bash
"$BRIDGE_PY" -E - <<'PY'
from pathlib import Path # Restore only already identified files in the isolated historical layout.
import hashlib,json # Use byte identities without importing the neural or native runtime.
repo=Path('/workspace/scratch/500ec816102b/model-repo');v2=Path('/dev/shm/bridge_complex_v2_20261025');base=repo/'automation/local_bridge_operator';evidence=base/'v2_evidence' # Preserve the exact original absolute roots.
mapping=json.loads((evidence/'runtime_source_mapping.json').read_text()) # Read the published source-to-runtime mapping.
pairs=[(repo/x['repository_path'],Path(x['runtime_path']),x['sha256']) for x in mapping] # Bind every restored numerical source to its frozen hash.
for relative in ['audit/v2_public_contract.json','audit/v2_execution_lock.json','acquisition/initial_cost_contracts.json','operator/gradient_calibration/selection.json','operator/development_diagnostics/decomposition.json']: # Restore explicit metadata identities that are not all present in the first evidence ZIP.
    src=evidence/relative.replace('/','__');pairs.append((src,v2/relative,hashlib.sha256(src.read_bytes()).hexdigest())) # The subsequent frozen-lock checks validate these metadata references.
for src,dst,expected in pairs: # Never edit an original file to make a lock appear valid.
    raw=src.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected;assert not dst.exists() or dst.read_bytes()==raw # Reject changed source bytes and conflicting existing destinations.
    if not dst.exists(): dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw) # Materialize only missing files at the original path.
print('Source and metadata copies verified; this is not a training or test run.') # Keep restoration separate from numerical execution.
PY
```

3. 运行时包使用保留 Unix 权限的 `unzip` 解压到独立 staging，再运行 `python -E restore_runtime_prefix.py --destination /workspace/scratch/500ec816102b/solver-runtime`。脚本拒绝已有目的地。ZIP 记录 wrapper/binary 为 `0755`；若提取器丢失执行位，须按 manifest 恢复这两个私有文件的权限后再复制。不要把 `system_dependency_snapshots/` 放进主机 `/lib` 或 `/usr/lib`。本包覆盖冻结 controller 的摩擦/钢筋 v2 求解器；其他历史分支按其自身 receipt 恢复，不据此假定所有求解器变体相同。
4. 将 `closed_development_dependency_supplement.zip` 解压到另一个 staging，从其目录执行下列命令。补充包保存 217 份新唯一内容，用外部引用和内部 alias 恢复 482 个逻辑文件，避免重复旧包；所需外部源码/证据必须已按前述步骤恢复。脚本在写入前核验全部依赖，拒绝同路径不同 SHA，不写 formal 目录：

```bash
"$BRIDGE_PY" -E restore_closed_development.py \
  --destination "$BRIDGE_V2" \
  --external-root "$BRIDGE_V2" \
  --external-root "$BRIDGE_OLD"
```

5. 原始数据和全部锁定开发证据恢复后，先核对身份。下面读取原 train/validation 文件做流式 SHA，不解包数组、不调用求解器、不读取新 heldout 响应：

```bash
"$BRIDGE_PY" -E - <<'PY'
from pathlib import Path # Verify restored historical paths without changing them.
import hashlib,json # Stream reference bytes rather than load scientific arrays.
v2=Path('/dev/shm/bridge_complex_v2_20261025');repo=Path('/workspace/scratch/500ec816102b/model-repo');base=repo/'automation/local_bridge_operator' # Use the original declared layout.
def sha(path): # Bound memory even for full-field files.
    h=hashlib.sha256() # Preserve the full-file identity.
    with Path(path).open('rb') as stream: # Do not interpret response contents.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Read one MiB at a time.
    return h.hexdigest() # Return the exact checksum.
assert sha(v2/'audit/v2_public_contract.json')=='d852227d9abe7a5891856ba1ba7d70488a3d316ff8fa33ed5b1ebbe445e68877' # Bind the historical public contract.
assert sha(v2/'audit/v2_execution_lock.json')=='aa695be955e0037b6ac37b2a407c39c846b555349e29b3a5c7320cb4e017fe54' # Bind the historical execution lock.
assert sha(v2/'operator/v2_controller_config.json')=='61e78dd599dba5e2cd1c9fab2ade51b250f4092b05697582c3b2128ed7b34eb3' # Bind the complete frozen controller config.
lock=json.loads((v2/'audit/v2_execution_lock.json').read_text());old=json.loads((base/'v2_evidence/reproduce_dependency_inventory.json').read_text()) # Use the actual locked source and archived old-input identities.
def references(node): # Include nested calibration and verification evidence rather than checking source names alone.
    if isinstance(node,dict): # Traverse only the already public frozen lock metadata.
        if 'path' in node and 'sha256' in node: yield node # Preserve each exact source or evidence reference.
        for value in node.values(): yield from references(value) # Check nested development prerequisites too.
    elif isinstance(node,list): # Preserve all listed source and evidence identities.
        for value in node: yield from references(value) # Avoid selecting only convenient successful records.
locked=list(references(lock)) # This lock traversal contains no new heldout response fields.
for item in locked+old['required_files']: assert sha(item['path'])==item['sha256'],item['path'] # A missing or changed dependency fails rather than being silently regenerated.
print(json.dumps({'locked_references_verified':len(locked),'old_input_identities_verified':len(old['required_files'])})) # This check does not certify runtime ABI, model accuracy or new-test release.
PY
"$BRIDGE_PY" "$BRIDGE_V2/operator/v2_controller.py" preflight --config "$BRIDGE_CFG"
```

`preflight` 核验公开输入与配置，不等于完整执行锁或测试解封批准。实际旧环境通过安装元数据观察为 Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Torch 2.5.1+cpu；x86-64 Linux/glibc 2.39。它们不是完整、可安装、逐位重现的环境 lock。

## 能重放什么，何时必须新冻结

已有 ZIP 的 CRC/SHA、事件链、阶段提交和模型张量身份可离线复核。原训练数据上的新进程重载、未来标签毒化、实体置换检查会实际导入 Torch，需要计算资源窗口；示例是已闭合的钢筋初始阶段：

```bash
"$BRIDGE_PY" "$BRIDGE_V2/operator/v2_controller_invariants.py" \
  --trainer "$BRIDGE_V2/operator/v2_operator_training.py" \
  --checkpoint "$BRIDGE_V2/operator/formal/rebar/initial/seed_17/model.pt" \
  --family rebar --development \
  --output "$BRIDGE_V2/operator/replay_checks/rebar_initial_seed17"
```

只有原路径、源/数据/初始化/配置身份保持一致、且尚未解封新测试时，才可用 `v2_controller.py run --config "$BRIDGE_CFG" --family friction` 或 `--family rebar` 继续原 campaign。这是会训练、获取和产生真实费用的命令。完整 stage commit 校验后复用；closed-epoch resume 要求保存的事件字节完全一致。部分 epoch 的未匹配事件尾必须保留为实际失败/中断证据，不能删除后冒充无损续跑。

20 stages 和 8 acquisition rounds 全部完成后，运行 `v2_controller.py freeze --config "$BRIDGE_CFG"`，生成六个选中模型的 `frozen_models.json` 和 `completion_manifest.json`。**freeze 本身不放行测试**；随后由独立的 `v2_selected_weight_support_audit.py --final` 与 `v2_release_completion_audit.py` 核对实际选中权重、训练支持、事件和费用，再调用新版 `v2_test_release_guard.issue_release(...)` 签发许可。该 guard **没有 CLI main**；旧 `v2_experiment_contract.py release-tests` 不能替代当前新版验证收据。最终重放还需要经许可生成、同时包含两族完整 test/OOD 身份和失败参考记录的 released index；不能拿 sealed descriptors 当结果索引。最终状态以交付的 completion/release/final receipts 为准。

修改路径字符串、wrapper、架构、物理实现、损失、归一化、训练支持、初始化、预算、选模规则或正式 config，均应建立独立实验目录，重新验证并冻结设计/config/源码锁/阶段 specs。`BRIDGE_V1_REPO` 只覆盖 trainer 与部分物理模块，`BRIDGE_V2_REBAR_ROOT` 只覆盖钢筋 native 输出；它们不能让整个 campaign 任意迁移。**挪目录或改路径后，旧 hash 锁不会自动继续有效。** 新测试暴露后也不能继续原实验拟合或选模。

## 仍需明确保留的边界

- 运行时包补齐了实际二进制及已解析启动库。对应 Debian `.dsc`、`.debian.tar`/`.diff`、完整构建工具链和条件 `dlopen`/MPI/hwloc provider 插件尚未形成完整复现链；没有宣称逐位源码重建或任意主机 ABI 一致。
- 原执行锁引用的一组已闭合开发校准、worker 和 controller 验证证据，不在最早的 V2 开发 ZIP 中；恢复必须包含单列的 `closed_development_dependency_supplement.zip` 及其清单。不能只恢复 28 份源码就宣称完整执行证据齐全。
- 补充包没有 formal payload 或恢复目标。其中 9 个开发逻辑文件通过相同 SHA 引用已保存 formal stage ZIP 的小型 JSON/源码副本；这是已有闭合归档的内容引用，不是读取运行中的正式树或新增正式结果。
- 原生参考的网格/离散资格、算子误差和物理残差是不同检查。本文件不把 native 或梯度 PASS 写成神经算子准确，也不把热力 HOLD、局部验证试件或独立探针改称正式整桥结论。
