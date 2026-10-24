#!/usr/bin/env python3  # 生成冻结的同桥工况分组，保持测试工况不参与补样决策。
import argparse  # 解析输出路径与低差异设计规模。
import json  # 保存可复现的工况配置。
from pathlib import Path  # 管理显式输出目录。
import numpy as np  # 使用固定种子的分组排列。
from scipy.stats import qmc  # 使用二维Sobol序列覆盖服务荷载允许域。
def main():  # 创建本次单桥非线性学习工况的不可变初始设计。
    parser = argparse.ArgumentParser()  # 建立命令行入口。
    parser.add_argument('--output', type=Path, required=True)  # 要求调用方给出明确的工况配置路径。
    args = parser.parse_args()  # 读取本次调用参数。
    seed = 20261024  # 固定低差异序列与分组排列的随机种子。
    points = qmc.Sobol(d=2, scramble=True, seed=seed).random_base2(m=5)  # 先生成完整二进制规模的低差异设计。
    points[points.sum(axis=1) > 1.0] = 1.0 - points[points.sum(axis=1) > 1.0]  # 将方形样本反射到q和偏载系数之和不超过1的三角域。
    order = np.random.default_rng(seed).permutation(len(points))[:24]  # 在计算前一次性冻结24个候选及其顺序。
    scenarios = []  # 汇集完整的工况登记记录。
    for index, source_index in enumerate(order):  # 每个工况只登记一次并拥有稳定标识。
        q, asym = map(float, points[source_index])  # 保留两个原始荷载分布的精确缩放系数。
        split = 'train' if index < 16 else ('validation' if index < 20 else 'test')  # 冻结16个训练、4个验证和4个同桥测试工况。
        scenarios.append({'case_id': f'LC{20 + index:02d}_MD_SOBOL', 'q': q, 'asym': asym, 'factors': [q, 0.0, asym], 'split': split})  # 保存原荷载坐标及分组；风载系数固定为零。
    payload = {'schema': 'zhaqing-md-scenario-design-v1', 'seed': seed, 'bridge_id': 'zhaqing', 'source_commit': '0f5e77e063fe703cabe93305177202ad7fcbd63f', 'domain': {'q': [0.0, 1.0], 'asym': [0.0, 1.0], 'constraint': 'q + asym <= 1', 'meaning': 'q*(LC02-LC01) + asym*(LC03-LC01)', 'wind_factor': 0.0}, 'split_scope': 'same_bridge_load_cases_only', 'cross_bridge_test': 'NOT_RUN_SINGLE_BRIDGE', 'scenarios': scenarios}  # 写明每个参数的物理来源与数据划分作用域。
    args.output.parent.mkdir(parents=True, exist_ok=True)  # 创建独立配置目录。
    if args.output.exists():  # 防止在看过结果之后悄然重抽测试工况。
        raise FileExistsError(f'Frozen design already exists: {args.output}')  # 要求显式创建新版本才能修改工况设计。
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')  # 保存完整精度的设计登记。
    print(json.dumps({'output': str(args.output), 'count': len(scenarios), 'train': 16, 'validation': 4, 'test': 4}))  # 报告已冻结设计的数量。
if __name__ == '__main__':  # 仅在直接运行脚本时生成工况文件。
    main()  # 执行可复现的初始工况设计。
