#!/usr/bin/env python3  # 用真实图网络评测结果选择下一轮实际有限元工况。
import argparse  # 解析候选生成和反馈选样的输入路径。
import hashlib  # 将反馈决策绑定到同一训练世代和精确输入字节。
import json  # 保存完整候选评分与选择证据。
from pathlib import Path  # 管理不可变的轮次文件。
import numpy as np  # 计算无量纲评分及候选间距。
from scipy.stats import norm, qmc  # 计算期望改进和低差异候选覆盖。
from sklearn.gaussian_process import GaussianProcessRegressor  # 对已知开发误差建立明确的贝叶斯响应面。
from sklearn.gaussian_process.kernels import ConstantKernel, Matern  # 使用固定超参数的误差代理先验。
from sklearn.linear_model import Ridge  # 从已完成求解记录估计正的计算成本。
def read(path):  # 读取显式提供的JSON证据。
    return json.loads(Path(path).read_text(encoding='utf-8'))  # 不搜索或隐式替换任何模型版本。
def write(path, payload):  # 保留每轮不可变的决策产物。
    path = Path(path)  # 统一输出路径类型。
    path.parent.mkdir(parents=True, exist_ok=True)  # 创建本轮独立目录。
    if path.exists():  # 防止覆盖已作出的采集决策。
        raise FileExistsError(str(path))  # 要求新决策使用新版本路径。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')  # 保存有限数值与完整决策依据。
def scaled(values):  # 将不同量纲的指标变为可比较的相对候选评分。
    values = np.asarray(values, dtype=float)  # 统一为数值数组。
    return (values - values.min()) / max(float(np.ptp(values)), 1e-12)  # 保留相对差异并避免常量指标除零。
def features(points):  # 对求解耗时使用简单且明确的二次特征。
    return np.column_stack([points, points[:, 0] ** 2, points[:, 1] ** 2, points[:, 0] * points[:, 1]])  # 表示均布和偏载强度及相互作用。
def main():  # 实施一个有固定预算和来源记录的反馈选样步骤。
    parser = argparse.ArgumentParser()  # 建立两种显式操作模式。
    parser.add_argument('--generate', action='store_true')  # 允许先生成无有限元标签的候选点。
    parser.add_argument('--manifest', type=Path)  # 提供真实已完成工况与成本。
    parser.add_argument('--metrics', type=Path)  # 提供首轮独立评测误差。
    parser.add_argument('--candidate-metrics', type=Path)  # 提供冻结图网络对候选的预测指标。
    parser.add_argument('--output', type=Path, required=True)  # 要求独立的输出文件路径。
    parser.add_argument('--seed', type=int, default=20261025)  # Freeze each new Sobol candidate generation independently.
    parser.add_argument('--candidate-power', type=int, default=7)  # Set an explicit power-of-two search budget.
    parser.add_argument('--case-start', type=int, default=60)  # Keep case identities unique across feedback rounds.
    parser.add_argument('--round', type=int, default=1)  # Preserve the actual acquisition generation.
    parser.add_argument('--radius', type=float, default=0.35)  # Carry the validated trust-region radius into the next executed round.
    args = parser.parse_args()  # 读取全部输入后再作任何决策。
    if args.generate:  # 在没有候选真值的情况下覆盖允许参数域。
        points = qmc.Sobol(d=2, scramble=True, seed=args.seed).random_base2(m=args.candidate_power)  # 按显式预算产生新的二维候选。
        mask = points.sum(axis=1) > 1.0  # 识别超出服务荷载三角域的点。
        points[mask] = 1.0 - points[mask]  # 将候选反射到非负且总系数不超过1的域内。
        write(args.output, {'schema': 'zhaqing-md-candidates-v1', 'candidates': [{'case_id': f'CANDIDATE_{i:03d}', 'factors': [float(p[0]), 0.0, float(p[1])]} for i, p in enumerate(points)]})  # 保存真实将被模型评估的候选而不生成虚假FEM标签。
        return  # 候选生成完成后不作训练或选样。
    manifest, metrics, inferred = read(args.manifest), read(args.metrics), read(args.candidate_metrics)  # 读取三个独立的实际证据源。
    model_directory = Path(inferred['model_directory']).resolve()  # 读取候选推理明确记录的模型目录。
    if model_directory != args.metrics.resolve().parent:  # 防止旧模型误差与新模型候选分歧混合使用。
        raise RuntimeError('Candidate inference and evaluation belong to different model generations')  # 拒绝跨世代证据拼接。
    contract = read(model_directory / 'model_contract.json')  # 读取该训练世代的不可变数据身份。
    input_sha256 = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in [('manifest', args.manifest), ('metrics', args.metrics), ('candidate_metrics', args.candidate_metrics), ('model_contract', model_directory / 'model_contract.json')]}  # 记录参与决策的四份精确证据。
    if input_sha256['manifest'] != contract['dataset_sha256'] or input_sha256['model_contract'] != inferred['model_contract_sha256']:  # 核实候选推理和训练数据来自同一版本。
        raise RuntimeError('Acquisition source hashes do not match the frozen model contract')  # 禁止对漂移数据作无来源的反馈决策。
    developed = [row for row in metrics['cases'] if row['split'] in ('train', 'validation')]  # 严格排除测试响应误差参与采集。
    validation = [row for row in developed if row['split'] == 'validation']  # 使用开发集定位已知最困难区域。
    center_row = max(validation, key=lambda row: row['relative_l2'])  # 冻结误差最大的验证工况作为当前信赖域中心。
    center = np.asarray(center_row['factors'], dtype=float)[[0, 2]]  # 仅保留两种实际变化的荷载坐标。
    observed = np.asarray([row['factors'] for row in developed], dtype=float)[:, [0, 2]]  # 提取开发工况坐标。
    errors = np.asarray([row['relative_l2'] for row in developed], dtype=float)  # 以真实参考解误差作为误差代理的学习目标。
    candidates = inferred['candidate_predictions']  # 读取冻结神经网络输出的候选分歧与物理残差。
    if any(len(row['factors']) != 3 or not np.isfinite(row['factors']).all() or abs(float(row['factors'][1])) > 1e-12 for row in candidates):  # 核对候选与实际求解器使用同一三维坐标且风载严格为零。
        raise RuntimeError('Candidate factors must be finite [q, 0, asym] vectors')  # 不丢弃一个实际参与预测却未参与有限元求解的非零风载。
    points = np.asarray([row['factors'] for row in candidates], dtype=float)[:, [0, 2]]  # 保留所有候选的物理含义。
    kernel = ConstantKernel(1.0, constant_value_bounds='fixed') * Matern(length_scale=[0.3, 0.3], length_scale_bounds='fixed', nu=2.5)  # 明确预先冻结的贝叶斯误差代理核。
    gp = GaussianProcessRegressor(kernel=kernel, alpha=1e-6, normalize_y=True, optimizer=None)  # 固定核尺度以避免在小开发集上无限调参。
    gp.fit(observed, errors)  # 只用已完成开发集的真实预测误差拟合响应面。
    mean, deviation = gp.predict(points, return_std=True)  # 估计候选误差水平及其代理不确定性。
    improvement = mean - float(errors.max())  # 把发现更大误差区域定义为本轮误差搜索的改进。
    z = improvement / np.maximum(deviation, 1e-12)  # 计算有界分母下的标准化改进。
    expected_improvement = improvement * norm.cdf(z) + deviation * norm.pdf(z)  # 使用最大化未知误差的标准期望改进。
    completed = [row for row in manifest['samples'] if row['quality_flag'] == 'VALID_CONVERGED' and row['split'] in ('train', 'validation')]  # 只使用真正成功求解的耗时记录。
    cost_points = np.asarray([row['factors'] for row in completed], dtype=float)[:, [0, 2]]  # 读取对应荷载坐标而不使用其测试响应。
    durations = np.asarray([row['wall_time_s'] for row in completed], dtype=float)  # 保留并发执行条件下的实际墙钟成本。
    cost_model = Ridge(alpha=0.01).fit(features(cost_points), np.log(np.maximum(durations, 1e-3)))  # 对数拟合保证预计成本为正。
    costs = np.clip(np.exp(cost_model.predict(features(points))), durations.min() * 0.5, durations.max() * 2.0)  # 限制小样本成本外推的影响。
    uncertainty = scaled([row['ensemble_rms_std_mm'] for row in candidates])  # 归一化独立神经网络集成分歧。
    residual = scaled(np.log1p([row['rms_free_suspension_residual_N'] for row in candidates]))  # 归一化索系实际几何残差，不冒充全桥残差。
    coverage = scaled([row['nearest_training_distance'] for row in candidates])  # 归一化训练域覆盖不足指标。
    ei = scaled(expected_improvement)  # 归一化贝叶斯误差搜索收益。
    scores = (0.35 * uncertainty + 0.25 * residual + 0.20 * coverage + 0.20 * ei) / (costs / np.median(durations))  # 用预先定义的权重计算单位预计成本的信息指标。
    inside = np.max(np.abs(points - center), axis=1) <= args.radius  # 冻结首轮连续参数信赖域的边长约束。
    available = np.all(points >= 0.0, axis=1) & (points.sum(axis=1) <= 1.0 + 1e-12)  # 显式检查每个候选的物理荷载域约束。
    existing_points = np.asarray([row["factors"] for row in manifest["samples"]], dtype=float)[:, [0, 2]]  # Use only known input coordinates to prevent repeats across every split.
    available &= np.linalg.norm(points[:, None, :] - existing_points[None, :, :], axis=-1).min(axis=1) > 1e-8  # 避免重复计算已经完成的同一工况。
    selected = []  # 逐项保存带空间去重的4个有限元任务。
    for selection_index in range(4):  # 固定本轮新增有限元预算而不观察未来测试改善。
        eligible = available & (inside if selection_index < 2 else True)  # 前两项搜索信赖域，其余保留全局覆盖。
        if not eligible.any():  # 在局部域被去重耗尽时采用剩余可行候选。
            eligible = available.copy()  # 维持真实候选预算但不越过物理参数域。
        if not eligible.any():  # 检查空间去重后候选池是否已经耗尽。
            raise RuntimeError('Candidate pool cannot satisfy the declared diverse batch budget')  # 不用全负无穷argmax制造重复或非法工况。
        index = int(np.argmax(np.where(eligible, scores, -np.inf)))  # 选择当前评分最高的合法候选。
        selected.append(index)  # 记录被选择候选的不可变序号。
        available &= np.linalg.norm(points - points[index], axis=1) >= 0.07  # 防止一个批次集中于几乎相同的荷载点。
    rows = [{**row, 'gp_expected_error': float(mean[i]), 'gp_std_error': float(deviation[i]), 'expected_improvement': float(expected_improvement[i]), 'estimated_cost_s': float(costs[i]), 'score': float(scores[i]), 'within_trust_region': bool(inside[i]), 'selected': i in selected} for i, row in enumerate(candidates)]  # 保存所有候选的可复核评分而非只保留获选项。
    scenarios = [{'case_id': f'LC{args.case_start+i:02d}_MD_FEEDBACK', 'q': float(points[j, 0]), 'asym': float(points[j, 1]), 'factors': [float(points[j, 0]), 0.0, float(points[j, 1])], 'split': 'train', 'round': args.round, 'selection_reason': 'cost_aware_ensemble_physics_coverage_gp_ei', 'candidate_id': candidates[j]['case_id']} for i, j in enumerate(selected)]  # 仅把选中的候选变成待实际计算的新训练工况。
    write(args.output, {'schema': 'zhaqing-md-feedback-v1', 'action': 'RUN_HIGH_FIDELITY_THEN_RETRAIN', 'test_errors_used': False, 'input_sha256': input_sha256, 'model_directory': str(model_directory), 'acquisition_weights': {'ensemble': 0.35, 'supported_physics': 0.25, 'coverage': 0.20, 'gp_error_expected_improvement': 0.20}, 'trust_region': {'center': center.tolist(), 'radius': args.radius, 'center_case': center_row['case_id'], 'executed_scope': 'one fixed-radius local batch with two additional unrestricted feasible selections', 'next_radius_rule': 'multiply by 1.25 if mean validation error improves, else multiply by 0.5'}, 'candidates': rows, 'scenarios': scenarios})  # 保存完整决策以及下一轮真实执行列表。
    print(json.dumps({'selected': scenarios}, ensure_ascii=False))  # 向执行层报告需要计算的四个具体工况。
if __name__ == '__main__':  # 允许作为工具导入而不执行采集。
    main()  # 执行显式指定的候选生成或反馈选样。
