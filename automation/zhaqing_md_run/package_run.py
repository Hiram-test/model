#!/usr/bin/env python3  # 汇总真实两轮计算并创建可下载的实现与数值证据包。
import hashlib  # 固定交付文件及原始资料身份。
import json  # 读取实际结果并保存机器可核对的结论。
import shutil  # 复制已经验证的真实云图。
import zipfile  # 将新实现和完整原生证据分别归档。
from pathlib import Path  # 以当前仓库和工作目录定位明确产物。
ROOT = Path(__file__).resolve().parents[2]  # 读取本次原模型仓库位置。
WORKSPACE = ROOT.parent  # 读取当前任务的独立目录。
RUN = ROOT / 'build/zhaqing-md-20261024'  # 固定本次运行结果的版本目录。
OUT = WORKSPACE / 'deliverables'  # 将用户交付物与中间文件分离。
def read(path):  # 读取已完成的JSON结果。
    return json.loads(Path(path).read_text(encoding='utf-8'))  # 不从日志猜测或者补造指标。
def digest(path):  # 流式计算大型归档的字节身份。
    value = hashlib.sha256()  # 创建独立哈希状态。
    with Path(path).open('rb') as stream:  # 保留二进制内容原样。
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):  # 限制归档校验时的内存使用。
            value.update(chunk)  # 累积实际文件字节。
    return value.hexdigest()  # 返回完整SHA-256。
def main():  # 仅在两轮真实学习和反馈都结束后生成最终交付。
    OUT.mkdir(parents=True, exist_ok=True)  # 创建用户可下载产物目录。
    first, second = read(RUN / 'learning_round0/metrics.json'), read(RUN / 'learning_round1/metrics.json')  # 要求两个已完成训练世代的实际评测。
    initial = read(RUN / 'learning_initial/dataset_manifest.json')  # 保留最初24个工况的全部成功和失败记录。
    feedback = read(RUN / 'feedback-decision.json')  # 读取真实的模型驱动补算决策。
    extra = read(RUN / 'learning_feedback/dataset_manifest.json')  # 读取实际补算而不是仅拟议的任务。
    accepted = read(RUN / 'learning_combined/accepted_manifest.json')  # 读取第二轮实际采用的独立审查数据。
    for sample in accepted['samples']:  # 在最终归档时再次确认学习真值和审查回执的字节身份。
        if digest(sample['canonical_dat']) != sample['canonical_dat_sha256'] or digest(sample['audit_path']) != sample['audit_sha256']:  # 检测审查之后发生的任何松散文件损坏。
            raise RuntimeError(f'Accepted evidence changed before delivery: {sample["case_id"]}')  # 不将损坏文件封装成看似完整的交付物。
    matrix = read(RUN / 'calculation/case-matrix.json')  # 保留原九工况的数值与工程判定区别。
    original = []  # 收集每个实际原工况的主要响应。
    base = read(RUN / 'calculation/summary.json')  # 读取原恒载切线计算结果。
    original.append({'case_id': 'LC01_G_DEAD', 'status': base['status'], 'maximum_displacement_mm': base['maximumDisplacementMm'], 'analysis': 'F3 tangent retained response'})  # 记录基准位移的真实计算定义。
    for path in sorted((RUN / 'calculation/cases').glob('*/summary.json')):  # 汇总其余已有可信求解结果。
        record = read(path)  # 读取该工况的完整求解摘要。
        original.append({'case_id': path.parent.name, 'status': record.get('status'), 'maximum_displacement_mm': record.get('maximumDisplacementMm'), 'analysis': record.get('analysisMode')})  # 不为预设阻断工况制造位移值。
    before = float(first['splits']['validation']['mean_relative_l2'])  # 用验证集而不是测试误差更新搜索状态。
    after = float(second['splits']['validation']['mean_relative_l2'])  # 读取补算重训后的同一验证集指标。
    comparison = {'round0': first['splits'], 'round1': second['splits'], 'validation_improved': after < before, 'validation_relative_change': (after - before) / max(before, 1e-12), 'trust_radius_previous': 0.35, 'trust_radius_next': 0.35 * (1.25 if after < before else 0.5), 'trust_radius_update_executed': True, 'next_search_executed': False, 'test_used_for_acquisition': False}  # 执行一次明确的信赖域状态更新但不声称已执行第三轮搜索。
    (RUN / 'round-comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')  # 保存实际闭环前后变化与下一轮状态。
    failures = [{'case_id': row['case_id'], 'split': row['split'], 'status': row['quality_status'], 'reason': row.get('error')} for row in initial['samples'] + extra['samples'] if row['quality_status'] != 'VALID_CONVERGED']  # 完整报告数值失败并保留原固定分组。
    physical_residuals = {name: {'minimum_case_maximum_N': min(row['max_free_suspension_residual_N'] for row in record['cases']), 'maximum_case_maximum_N': max(row['max_free_suspension_residual_N'] for row in record['cases'])} for name, record in [('round0', first), ('round1', second)]}  # 单独记录未经再求解校正的代理物理残差。
    summary = {'status': 'SINGLE_BRIDGE_CLOSED_LOOP_EXECUTED_WITH_HOLD', 'date': '2026-10-24', 'repository': 'Hiram-test/model', 'source_commit': '0f5e77e063fe703cabe93305177202ad7fcbd63f', 'design_md_sha256': digest(WORKSPACE / 'inputs/bridge_group_three_module_autoregressive_design.md'), 'solver_version': 'CalculiX 2.21', 'original_workflow_solver_version': '2.17-3', 'original_matrix_status': matrix['status'], 'original_cases': original, 'initial_attempts': len(initial['samples']), 'initial_solver_pass': initial['valid_count'], 'feedback_attempts': len(extra['samples']), 'feedback_solver_pass': extra['valid_count'], 'final_audited_sample_count': len(accepted['samples']), 'failures': failures, 'comparison': comparison, 'training_seconds': {'round0': first['training_seconds'], 'round1': second['training_seconds']}, 'summed_scenario_wall_time_s': initial['total_wall_time_s'] + extra['total_wall_time_s'], 'module_c_action': 'HOLD_MODEL', 'remaining_requirements': ['完整梁壳与索系接口物理残差', '跨桥验证', '全部冻结测试工况可信参考解', '预测区间校准', '多保真误差验证', '有来源的工程安全判据'], 'structural_failure_inferred_from_solver_failure': False}  # 将已执行结果与尚缺证据清晰分开。
    summary['surrogate_case_maximum_internal_residual_range_N'] = physical_residuals  # 明确位移误差与物理一致性是不同验收指标。
    (OUT / 'zhaqing_run_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')  # 保存补齐物理残差的最终结果版本。
    lines = ['# 扎青吊桥三模块运行结果', '', '日期：2026-10-24。上游：Hiram-test/model；固定提交：0f5e77e063fe703cabe93305177202ad7fcbd63f。', '', '本次已执行真实有限元计算、异构图集成训练、128个候选评估、4个反馈工况补算及第二轮训练。模型发布判定为 HOLD_MODEL。', '', '## 实际计算', '', f'原九工况流程：{matrix["status"]}；LC09风缆失效保留原有阻断。新增初始工况{len(initial["samples"])}个、通过{initial["valid_count"]}个；反馈工况{len(extra["samples"])}个、通过{extra["valid_count"]}个。数值失败没有被标记为结构失效。', '', '| 原工况 | 最大位移/mm | 数值状态 |', '|---|---:|---|']  # 按对象、算法与实测结果组织可读说明。
    lines += [f'| {row["case_id"]} | {row["maximum_displacement_mm"]:.6f} | {row["status"]} |' for row in original if row['maximum_displacement_mm'] is not None]  # 使用真实有限元摘要生成数值表。
    lines += ['', '## 训练与反馈', '', '图包含783个源节点、1070个构件、7类关系；使用真实节点荷载、材料与截面信息、局部消息传递和全局交互。三个独立种子17/29/43，各训练200轮；AdamW；验证集选择权重。参数宽度32、消息传递深度3。物理损失覆盖固定L0索系内部平衡及索锚边界。', '', '| 分组 | 第一轮平均相对L2误差 | 第二轮平均相对L2误差 |', '|---|---:|---:|']  # 给出实际实现架构和可比较的两轮评测。
    lines += [f'| {split} | {100 * first["splits"][split]["mean_relative_l2"]:.3f}%（{first["splits"][split]["case_count"]}/{first["splits"][split]["expected_case_count"]}） | {100 * second["splits"][split]["mean_relative_l2"]:.3f}%（{second["splits"][split]["case_count"]}/{second["splits"][split]["expected_case_count"]}） |' for split in ('train', 'validation', 'test')]  # 同时报告误差及有效参考工况数，避免掩盖失败测试工况。
    lines += ['', f'第一轮各工况最大索系内部残差范围：{physical_residuals["round0"]["minimum_case_maximum_N"]:.6g}—{physical_residuals["round0"]["maximum_case_maximum_N"]:.6g} N；第二轮：{physical_residuals["round1"]["minimum_case_maximum_N"]:.6g}—{physical_residuals["round1"]["maximum_case_maximum_N"]:.6g} N。原固定L0有限元内部残差容限为1e-4 N。代理结果没有经过有限元重求解或平衡投影来掩盖误差。']  # 给出维度明确且可检查的物理验收差距。
    lines += ['', '原固定分组为16训练、4验证、4测试；所有被排除的工况、原分组、原因与计划分母保存在manifest及metrics中。测试误差未参与反馈选样。', '', '反馈评分结合独立集成分歧、索系残差、训练域覆盖和基于开发误差的高斯过程期望改进，并按真实求解耗时估计归一化。首批2项在固定半径0.35的局部域选择，其余2项在整个允许域选择；第二轮结束后保存下一轮半径，没有执行第三轮。', '', '## 尚未闭合的验收项', '', '当前为单桥、固定模型的服务荷载组合运行。梁壳及索系接口的全物理残差、跨桥验证、多保真误差、预测区间校准和工程安全判据仍需建立；原模型的工程发布条件仍未满足。不能将本次结果称为已完成桥梁群验证。', '', '三个初始数值失败表现为位移修正量的微小振荡；与DAT有限打印精度的关系目前是待验证推断。原收敛阈值未被放宽。', '', '## 文件与复现', '', 'implementation/仅含本次新增执行代码；inputs/含精确恢复的原始输入和哈希回执；results/含响应场、两轮权重、完整评测和选样记录。大型原生求解过程另见zhaqing_native_evidence.zip。', '', '从上述固定Git提交检出原模型，将implementation中的新增目录复制至仓库。按照原workflow拼接stress_coordination_pipeline.part*及stress_coordination_condensed_adapter.part*；使用run_scenarios.py的--base、--source-cases、--calculation、--generated、--ccx等显式路径参数复算。路径和环境身份在JSON中保留为原运行记录，不修改历史收据冒充新运行。', '', '本次环境：Python3.12.14、NumPy2.3.5、SciPy1.17.0、scikit-learn1.8.0、PyTorch2.5.1+cpu、CalculiX2.21；图使用PyVista0.48.4/VTK9.5.2。原workflow求解器为2.17-3，版本差异已记录。', '']  # 明确复现方法与实际适用范围而不制造完整体系已验收的结论。
    report = '\n'.join(lines)  # 生成可与结果一起阅读的执行说明。
    (ROOT / 'automation/zhaqing_md_run/README.md').write_text(report, encoding='utf-8')  # 将说明保存在本次新增实现目录。
    (OUT / 'README.md').write_text(report, encoding='utf-8')  # 为结果包准备同一份说明。
    shutil.copy2(RUN / 'figures/zhaqing_service_displacement.png', OUT / 'zhaqing_service_displacement.png')  # 保留已经通过视觉检查的真实求解云图。
    bundle = OUT / 'zhaqing_md_run_bundle.zip'  # 定义较小的代码、响应与训练结果交付包。
    selected_names = {'summary.json', 'equilibrium_state.json', 'case-matrix.json', 'canonical-response.dat', 'wind-exclusion.json', 'independent-physics-audit.json', 'label-receipt.json', 'load-ledger.json', 'repair-report.json'}  # 保留足够解读结果的科学产物而避免复制大型原生迭代文件。
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:  # 创建独立可下载的紧凑结果包。
        archive.write(OUT / 'README.md', 'README.md')  # 将执行说明放在归档入口。
        archive.write(OUT / 'zhaqing_run_summary.json', 'zhaqing_run_summary.json')  # 将结论与指标放在归档入口。
        for path in sorted((ROOT / 'automation/zhaqing_md_run').glob('*')):  # 只归档本次新增且尚未远端发布的实现。
            if path.is_file() and path.suffix in ('.py', '.md', '.txt'):  # 排除缓存和既有Git仓库源代码副本。
                archive.write(path, 'implementation/automation/zhaqing_md_run/' + path.name)  # 保留新增模块的仓库相对位置。
        for path in sorted((WORKSPACE / 'zhaqing-inputs/recovered_cases').rglob('*')):  # 收录经过原哈希验证的实际模型输入。
            if path.is_file() and path.suffix in ('.inp', '.csv'):  # 仅收录运行所需输入及工况表。
                archive.write(path, 'inputs/' + str(path.relative_to(WORKSPACE / 'zhaqing-inputs')))  # 保留输入目录结构。
        for name in ('baseline-recovery.json', 'case-recovery.json'):  # 记录恢复输入的逐字节来源证据。
            archive.write(WORKSPACE / 'zhaqing-inputs' / name, 'inputs/' + name)  # 把原SHA核对回执与输入一同交付。
        for path in sorted(RUN.rglob('*')):  # 按确定顺序收录结果和学习证据。
            if not path.is_file() or any(part in ('native-archives', 'generated', '__pycache__') for part in path.relative_to(RUN).parts):  # 大型原生过程和原Git代码使用单独渠道而不重复归档。
                continue  # 跳过无关或重复内容。
            relative = path.relative_to(RUN)  # 保存可复核的原运行相对路径。
            chosen = path.name in selected_names or path.suffix in ('.vtk', '.png', '.pt') or (len(relative.parts) == 1 and path.suffix == '.json') or (relative.parts[0] in ('learning_round0', 'learning_round1', 'candidate_round0', 'validation', 'post', 'learning_combined') and path.suffix == '.json') or (path.name.endswith('manifest.json') or path.name == 'independent-audit-batch.json') or relative.parts[0] == 'logs'  # 保留结果场、权重、评测、审查和根日志。
            if chosen and path.suffix not in ('.pyc', '.tmp'):  # 排除尚未完成的临时文件。
                archive.write(path, 'results/' + str(relative))  # 不改写任何已生成科学结果。
    native = OUT / 'zhaqing_native_evidence.zip'  # 定义原生数值证据的独立大文件。
    native_sources = [RUN / 'native-archives' / name for name in ('original-matrix-native-evidence.zip', 'initial-learning-native-evidence.zip', 'feedback-learning-native-evidence.zip')]  # 仅封装独立复核完成的三个总快照，排除早期或重复的工作进程快照。
    if any(not path.is_file() for path in native_sources):  # 要求原矩阵、初始批次与实际反馈证据全部就绪。
        raise RuntimeError('All three verified native evidence archives are required')  # 不用不完整工作快照替代最终原生数值证据。
    with zipfile.ZipFile(native, 'w', compression=zipfile.ZIP_STORED) as archive:  # 原生快照已经压缩，外层只封装而不重复压缩。
        for index, path in enumerate(native_sources):  # 按确定顺序保留各原生证据快照。
            archive.write(path, f'{index:02d}-' + (path.parent.name + '-' if path.name == 'native-evidence.zip' else '') + path.name)  # 避免反馈工况同名快照发生覆盖。
        archive.writestr('archive-identities.json', json.dumps([{'path': str(path.relative_to(RUN)), 'size_bytes': path.stat().st_size, 'sha256': digest(path)} for path in native_sources], ensure_ascii=False, indent=2))  # 记录每个已封装数值快照的精确字节身份。
    for path in (bundle, native):  # 验证最终两个交付归档内部CRC完整。
        with zipfile.ZipFile(path) as archive:  # 从最终归档读取实际目录而不是仅检查文件存在。
            if archive.testzip() is not None:  # 检测任何归档内容损坏。
                raise RuntimeError(f'Corrupt deliverable archive: {path}')  # 拒绝交付损坏的可下载文件。
    print(json.dumps({'files': [{'path': str(path), 'size_bytes': path.stat().st_size, 'sha256': digest(path)} for path in (bundle, native, OUT / 'zhaqing_service_displacement.png')], 'summary': summary}, ensure_ascii=False))  # 返回真实已验证交付信息。
if __name__ == '__main__':  # 不在导入时创建或覆盖交付文件。
    main()  # 生成两轮已完成运行的结果包。
