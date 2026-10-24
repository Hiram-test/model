import hashlib  # Bind deliverables and native evidence to exact completed bytes.
import json  # Read actual metrics and write a compact machine-readable delivery index.
import zipfile  # Package reviewable code, weights, references, and original solver evidence.
from pathlib import Path  # Preserve deterministic artifact paths and scientific identities.
import matplotlib  # Generate a standalone scientific evaluation figure.
matplotlib.use('Agg')  # Render reproducibly without a desktop session.
import matplotlib.pyplot as plt  # Plot actual completed validation and test metrics.
ROOT = Path(__file__).resolve().parents[2]  # Resolve the original Git repository.
RUN = ROOT / 'build/zhaqing-md-20261024'  # Locate prior and continued experiments.
OUT = RUN / 'continuation'  # Read the completed continuation evidence only.
DELIVERY = ROOT.parent / 'deliverables'  # Stage user-facing portable artifacts.
def read(path):  # Read one exact JSON artifact.
    return json.loads(Path(path).read_text())  # Preserve saved numerical precision.
def digest(path):  # Compute artifact identity without modifying content.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Return the exact full-byte SHA256.
def main():  # Package only actual completed and independently reviewed work.
    result = read(OUT / 'final-evaluation.json')  # Require the final independent tests to have finished.
    summary = read(OUT / 'continuation-summary.json')  # Require both active-learning iterations to have completed.
    final = result['selected_model_metrics']  # Use the validation-selected checkpoint for the headline comparison.
    previous = result['previous_common_holdout']['splits']  # Use the same complete four-case test denominator for the prior model.
    manifest = read(summary['final_dataset'])  # Read all accepted current labels and split identities.
    rows = [('Previous', previous)]  # Start the scientific figure with the fair restored-holdout baseline.
    for name in ('search-lift0', 'search-lift1', 'search-lift2', 'learning-round3', 'learning-round4'):  # Include every tried configuration and executed active round.
        rows.append((name.replace('search-lift', 'Lift ').replace('learning-round', 'Active '), read(OUT / name / 'metrics.json')['splits']))  # Preserve unselected model outcomes transparently.
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)  # Create one readable comparison with exact common denominators.
    for split, color, marker in (('validation', '#117c83', 'o'), ('test', '#c66b30', 's')):  # Distinguish development selection from independent test reporting.
        ax.plot(range(len(rows)), [100 * r[1][split]['mean_relative_l2'] for r in rows], label=f'{split.title()} (4/4)', color=color, marker=marker, linewidth=2)  # Plot actual relative L2 percentages with no invented interpolation points.
    ax.set(xticks=range(len(rows)), xticklabels=[r[0] for r in rows], ylabel='Mean displacement relative L2 error (%)', yscale='log', title='Zhaqing: repaired references, architecture comparison and active learning')  # Preserve low-error differences without hiding the logarithmic scale.
    ax.grid(axis='y', which='both', alpha=0.2)  # Add restrained numerical reading guides.
    ax.legend(frameon=False)  # Label the two genuine evaluation roles.
    fig.savefig(DELIVERY / 'zhaqing_continuation_metrics.png', dpi=180)  # Save a standalone actual-data scientific figure.
    plt.close(fig)  # Release renderer resources after the completed export.
    lines = ['# 扎青吊桥：收敛修复与神经算子续训', '', '日期：2026-10-24。原模型固定提交：0f5e77e063fe703cabe93305177202ad7fcbd63f。', '', '## 已完成', '', 'LC28、LC42、LC43三个原失败工况已全部通过原阈值及独立物理审查。修复仅调整CalculiX 2.21的位移/反力打印格式，不改变求解器机器指令、模型参数或收敛标准。', '', '同一输入下，589个原生节点的位移和反力按原精度舍入后完全一致。成功对照LC36的全场相对差为1.91845e-7，原有合格验证/测试标签未替换。', '', '修复后比较三种图网络方案，每种3个独立种子、每个300轮；随后实际执行两轮256候选搜索，每轮选4个真实有限元工况补算并重新训练。另完成4个独立荷载域边界测试，均不参与训练、选型或采集。', '', f"最终参考集：训练{manifest['expected_split_counts']['train']}，验证4，测试4；另有独立边界测试4。", '', '## 完整且相同的测试分母', '', '| 分组 | 上一轮冻结模型重新评测 | 本次验证集选定模型 |', '|---|---:|---:|']  # Describe actual executed work and the fair comparison protocol.
    for split, label in (('validation', '验证（4/4）'), ('test', '测试（4/4）')):  # Report exact like-for-like held-out comparisons.
        lines.append(f"| {label} | {100 * previous[split]['mean_relative_l2']:.6f}% | {100 * final['splits'][split]['mean_relative_l2']:.6f}% |")  # Use completed numerical metrics only.
    lines += ['', f"采用权重目录：{Path(result['selected_model']['model_directory']).name}；该检查点使用{final['splits']['train']['case_count']}个训练工况，最新完成轮次使用{manifest['expected_split_counts']['train']}个。选择依据仅为验证集平均相对L2误差，测试误差不参与选型或搜索。上一答复中20.01%的测试误差只覆盖2个可用工况；本表将旧模型也按修复后的4个相同测试工况重新评估。", '', '## 物理与适用范围', '', f"所选模型在其训练、验证和测试集上的最大自由索系节点残差为{max(r['max_free_suspension_residual_N'] for r in final['cases']):.6g} N；原有限元内部残差阈值为1e-4 N。神经预测未经过有限元再求解或平衡投影。", '', '这是单桥、固定几何与材料、均布活载和偏载组合的位移代理。完整梁壳/塔及索系接口残差、跨桥迁移、风缆失效和预测区间校准仍未完成，工程发布保持HOLD。边界测试在原服务荷载三角域内，不代表超出该域的外推已验证。', '', '低阶响应提升项仅以训练样本拟合；图网络保留7类构件关系、局部消息传递与全局交互，并学习其剩余响应。lift-only-ablation.json单独列出关闭图修正时的表现，避免将提升项带来的精度全部归因于神经网络。', '', '## 独立边界测试', '', '| 工况 | q | 偏载系数 | 相对L2误差 | RMSE / mm |', '|---|---:|---:|---:|---:|']  # State physical and scientific scope precisely.
    for row in result['boundary_robustness']['cases']:  # Preserve hard boundary cases individually instead of pooling them away.
        lines.append(f"| {row['case_id']} | {row['factors'][0]:.3f} | {row['factors'][2]:.3f} | {100 * row['relative_l2']:.6f}% | {row['rmse_mm']:.6g} |")  # Report actual independent-reference comparison.
    lines += ['', '## 文件与复现', '', '本结果包含本次新增/修订执行脚本、15组实际训练权重、完整每工况评测、512候选的预测和选择记录、各轮数据身份、有效参考场及审查证据。完整原生求解过程在配套native-evidence归档内。', '', '原始有限元源代码使用固定Git提交，并按原workflow拼接pipeline与adapter；本包不修改原模型。precision_solver.py仅接受记录的原CalculiX二进制SHA，生成明确命名的打印精度变体；不能将该字节偏移补丁用于其他版本。', '', '执行顺序：precision_solver.py → run_scenarios.py修复三个失败及对照 → continue_training.py → 独立boundary计算/审查 → evaluate_continuation.py。代码中保留运行时绝对路径；移机复现需将路径映射到新的工作目录并重新生成运行身份，不能假称改写后的manifest仍具有原SHA。', '', '文件同步临时目录已从证据扫描中排除。损坏/缺失的原生DAT仅通过相同输入真实重放，且必须逐字节匹配原始记录SHA才能恢复；未修改原始收敛回执。历史失败记录和所有试验方案均保留，不以失败工况替换为容易的测试点。', '']  # Provide concrete reproducibility and data-integrity boundaries.
    if result['lift_only_ablation'] is not None:  # Compare the graph correction to the same frozen training-only lift.
        ablation = result['lift_only_ablation']['splits']  # Read actual independently evaluated baseline metrics.
        section = ['', '## 图网络修正的独立贡献', '', '| 方案（相同训练数据） | 验证相对L2 | 测试相对L2 |', '|---|---:|---:|', f"| 仅低阶响应项 | {100 * ablation['validation']['mean_relative_l2']:.6f}% | {100 * ablation['test']['mean_relative_l2']:.6f}% |", f"| 低阶响应项＋图网络 | {100 * final['splits']['validation']['mean_relative_l2']:.6f}% | {100 * final['splits']['test']['mean_relative_l2']:.6f}% |", '', '本次位移精度提升主要来自对单桥二维荷载响应的低阶建模；表中单独检验图网络修正的额外贡献。这不能作为跨桥神经算子泛化能力已经建立的证据。', '']  # Attribute numerical gains to the actual implemented components.
        index = lines.index('## 独立边界测试')  # Place the comparison before robustness details.
        lines[index:index] = section  # Keep the complete human report consistent with the machine evidence.
    (OUT / 'README.md').write_text('\n'.join(lines))  # Save an established experiment README alongside actual results.
    bundle = DELIVERY / 'zhaqing_continued_training_bundle.zip'  # Create a distinct continuation deliverable without replacing the prior run.
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:  # Package completed human and machine review artifacts.
        archive.write(OUT / 'README.md', 'README.md')  # Make the Chinese report the archive entry point.
        archive.write(DELIVERY / 'zhaqing_continuation_metrics.png', 'zhaqing_continuation_metrics.png')  # Include the exact-data evaluation figure.
        for path in sorted((ROOT / 'automation/zhaqing_md_run').glob('*')):  # Include new task-owned implementation rather than duplicating the original Git repository.
            if path.suffix in ('.py', '.txt') and path.is_file():  # Exclude interpreter caches and unrelated files.
                archive.write(path, 'implementation/' + path.name)  # Preserve actual executed scientific code.
        for path in sorted(OUT.rglob('*')):  # Keep models, metrics, native summaries, and audit evidence.
            if path.name == 'delivery.json' or path.name.startswith('packaging') or not path.is_file() or '.rsync-tmp' in path.parts or '__pycache__' in path.parts or path.suffix in ('.zip', '.tmp', '.frd', '.sta', '.cvg') or path.name.endswith('.inp'):  # Leave heavy raw iterative decks and native fields to the separate evidence archive.
                continue  # Exclude transient or duplicated artifacts only.
            if path.suffix == '.dat':  # Retain actual reference fields while separating intermediate solver dumps.
                continue  # Native raw dumps remain in independently verified archives.
            if any(p.endswith('-native-integrity') or p == 'repair-native' for p in path.relative_to(OUT).parts):  # Avoid duplicating replay scratch trees while preserving the archive integrity report separately.
                continue  # Keep compact review size bounded.
            archive.write(path, 'results/' + path.relative_to(OUT).as_posix())  # Preserve the full scientific generation hierarchy.
        for row in manifest['samples'] + read(OUT / 'boundary-final/accepted.json')['samples']:  # Make all actual final training and held-out reference labels available.
            for key in ('canonical_dat', 'summary', 'audit_path'):  # Include truth and both numerical and independent qualification evidence.
                path = Path(row[key])  # Resolve the exact accepted original artifact.
                archive.write(path, f"references/{row['case_id']}/{path.name}")  # Preserve stable source-case ownership.
        for path in (Path(manifest['baseline']), Path(manifest['equilibrium_state']), ROOT.parent / 'solver-runtime/precision-repair-v2.json', *[Path(p) for p in manifest['load_basis_files'] if p], ROOT.parent / 'solver-runtime/apt-cache/calculix-ccx_2.21-1_amd64.deb'):  # Include the exact parent state and repair identity needed for scientific interpretation.
            archive.write(path, 'inputs/' + path.name)  # Preserve the true source bytes without rewriting paths inside historical receipts.
    native = DELIVERY / 'zhaqing_continuation_native_evidence.zip'  # Keep complete verified native computation evidence separate from model review artifacts.
    with zipfile.ZipFile(native, 'w', zipfile.ZIP_STORED) as archive:  # Avoid recompressing already compressed immutable native snapshots.
        for name in ('repair-v2', 'feedback-round3', 'feedback-round4', 'boundary-final'):  # Include all actually used repaired, acquired, and robustness finite-element generations.
            path = OUT / (name + '-verified-native.zip')  # Require each separately verified full native archive.
            assert path.is_file()  # Never claim a missing solver generation was preserved.
            archive.write(path, path.name)  # Store the complete source snapshot unchanged.
    for path in (bundle, native):  # Check both completed user-facing archives once.
        with zipfile.ZipFile(path) as archive:  # Verify actual compressed member CRCs.
            assert archive.testzip() is None  # Refuse corrupted downloadable artifacts.
    delivery = {'files': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in (bundle, native, DELIVERY / 'zhaqing_continuation_metrics.png')]}  # Persist the final exact delivery inventory.
    (OUT / 'delivery.json').write_text(json.dumps(delivery, indent=2))  # Keep packaging identities beside the scientific results.
    print(json.dumps(delivery), flush=True)  # Report actual created artifacts only.
if __name__ == '__main__':  # Keep imports free of packaging side effects.
    main()  # Execute only after completed final evaluation and verified native snapshots.
