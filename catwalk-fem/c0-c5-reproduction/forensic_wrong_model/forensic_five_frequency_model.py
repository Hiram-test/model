#!/usr/bin/env python3  # 使用当前 Python 解释器运行五频率取证模型。
from __future__ import annotations  # 允许类型注解独立于定义顺序。
import csv  # 写出逐分支复现结果表。
import json  # 写出完整机器可读记录。
import math  # 计算模态重叠和 Rayleigh 频率修正。
from pathlib import Path  # 管理脚本旁的输出路径。

ROOT = Path(__file__).resolve().parent  # 将全部结果写入本脚本所在目录。
XI = (0.07739130434782608, 0.1517391304347826, 0.22608695652173913, 0.30043478260869565, 0.36609099999999994, 0.4343515217391304, 0.5, 0.5656558695652174, 0.6339170869565218, 0.6995652173913044, 0.7739130434782608, 0.8482608695652174, 0.9226086956521739)  # 主跨十三道横向通道的归一化站位。
BASE_STRICT = {"TA1": 0.07109342845263997, "TS1": 0.10113532460650478, "TS2": 0.14291348747210253}  # 严格自动标签下的三个 T 基线。
BASE_CLEAN = {"TA1": 0.07109342845263997, "TS1": 0.10113532460650478, "TS2": 0.146576212135106}  # 采用 clean n=4 T 分支作为附件 TS2 的物理前身。
TARGET_T = {"TA1": 0.0996, "TS1": 0.1147, "TS2": 0.1571}  # 附件表 4-1 的三个 T 目标。
BASE_HIGH = {"SIDE3": 0.16590792974776788, "VS2": 0.18677370918342245}  # SIDE3 与真实第二正对称竖弯基线。
TARGET_HIGH = {"SIDE3": 0.1557, "VS2": 0.1744}  # 附件表 4-1 的两个高阶目标。
ORDER = {"TA1": 2, "TS1": 3, "TS2_CLEAN": 4, "TS2_STRICT": 1}  # 四个候选纵向半波指纹。
MASS21_T = 963.811380787273  # 经审计的 MASS21 总质量池。
PASSAGE_T = 10.134611462369978  # 一道通道对应两幅猫道的完整质量。
TOTAL_MASS_T = 4108.46690758  # 经审计的全系统动力质量。
TOTAL_LENGTH_M = 4180.0  # 四跨总长。
MAIN_LENGTH_M = 2300.0  # 主跨长度。
B_M = 42.9  # 两幅猫道中心距。
G = 9.80665  # 标准重力加速度。


def overlap(order: int) -> float:  # 计算一个纵向振型与十三道通道站的离散重叠。
    return sum(math.sin(order * math.pi * x) ** 2 for x in XI)  # 累加各通道站的振型幅值平方。


def balance_shared(base_ts2: float, order_ts2: int) -> float:  # 反求使 TS1 和 TS2 等幅正负偏差的共享错误系数。
    lo, hi = 0.0, 0.002  # 给出足够覆盖目标的系数区间。
    for _ in range(120):  # 使用二分法获得稳定且可重复的结果。
        a = 0.5 * (lo + hi)  # 取当前区间中点。
        r1 = math.sqrt(BASE_CLEAN["TS1"] ** 2 + a * overlap(ORDER["TS1"])) / TARGET_T["TS1"]  # 计算 TS1 预测目标比。
        r2 = math.sqrt(base_ts2 ** 2 + a * overlap(order_ts2)) / TARGET_T["TS2"]  # 计算 TS2 候选预测目标比。
        lo, hi = (lo, a) if r1 + r2 > 2.0 else (a, hi)  # 根据平均比值更新二分区间。
    return 0.5 * (lo + hi)  # 返回共享错误系数。


def torsion_prediction(base: dict[str, float], order_ts2: int) -> tuple[dict[str, float], float, float]:  # 计算一个 TS2 分支解释下的三个 T 预测。
    a = balance_shared(base["TS2"], order_ts2)  # 用 TS1 与 TS2 候选反求共享高位主节点错误。
    b = TARGET_T["TA1"] ** 2 - base["TA1"] ** 2 - a * overlap(ORDER["TA1"])  # 反求仅作用于 TA1 的塔端主节点错误。
    pred = {"TA1": math.sqrt(base["TA1"] ** 2 + a * overlap(ORDER["TA1"]) + b), "TS1": math.sqrt(base["TS1"] ** 2 + a * overlap(ORDER["TS1"])), "TS2": math.sqrt(base["TS2"] ** 2 + a * overlap(order_ts2))}  # 计算三个 T 频率。
    return pred, a, b  # 返回频率及两个错误系数。


def high_prediction(eta: float) -> dict[str, float]:  # 计算有效模态质量膨胀后的两个高阶频率。
    scale = math.sqrt(1.0 + eta)  # 将质量增量换成频率缩放因子。
    return {name: value / scale for name, value in BASE_HIGH.items()}  # 对 SIDE3 与 VS2 施加相同有效质量投影。


def error_percent(value: float, target: float) -> float:  # 计算相对附件目标的有符号百分比误差。
    return 100.0 * (value / target - 1.0)  # 保留偏高或偏低方向。


def stats(values: list[float]) -> dict[str, float]:  # 汇总五个频率误差。
    return {"mae_percent": sum(abs(x) for x in values) / len(values), "rms_percent": math.sqrt(sum(x * x for x in values) / len(values)), "max_abs_percent": max(abs(x) for x in values)}  # 返回 MAE、RMS 和最大绝对误差。


def rows_for(name: str, base: dict[str, float], t_pred: dict[str, float], h_pred: dict[str, float], branch_note: str, mass_note: str) -> list[dict[str, object]]:  # 构造一个模型层级的五行结果。
    rows: list[dict[str, object]] = []  # 初始化结果行列表。
    for label in ("TA1", "TS1", "TS2"):  # 依次写入三个 T 分支。
        mechanism = "高位平动 master + NLGEOM 重力平衡产生伪摆式滚转约束"  # 记录共享的 T 族错误机制。
        mechanism += "；塔顶/下拉 master 增加反对称端部约束" if label == "TA1" else ""  # 仅 TA1 具有额外端部项。
        mechanism += "；clean n=4 T 分支被报告为 TS2" if label == "TS2" and branch_note == "clean_n4_mode16" else ""  # 标记 TS2 的分支错标假设。
        rows.append({"model": name, "label": label, "physical_baseline_hz": base[label], "attachment_target_hz": TARGET_T[label], "wrong_model_hz": t_pred[label], "relative_error_percent": error_percent(t_pred[label], TARGET_T[label]), "interpretation": branch_note, "mechanism": mechanism})  # 保存当前 T 行。
    for label in ("SIDE3", "VS2"):  # 依次写入两个高阶分支。
        mechanism = "横向通道 MASS21 的 full/half 重复记账增加有效模态质量"  # 记录高阶频率下降机制。
        mechanism += "；VS2 取 mode21 n=5 而非自动 mode13 n=1" if label == "VS2" else ""  # 标记 VS2 分支重识别。
        rows.append({"model": name, "label": label, "physical_baseline_hz": BASE_HIGH[label], "attachment_target_hz": TARGET_HIGH[label], "wrong_model_hz": h_pred[label], "relative_error_percent": error_percent(h_pred[label], TARGET_HIGH[label]), "interpretation": mass_note, "mechanism": mechanism})  # 保存当前高阶行。
    return rows  # 返回五行结果。


def main() -> None:  # 执行严格标签与最可能分支重识别两条路径。
    strict_t, strict_a, strict_b = torsion_prediction(BASE_STRICT, ORDER["TS2_STRICT"])  # 计算坚持自动 TS2 标签的保守路径。
    clean_t, clean_a, clean_b = torsion_prediction(BASE_CLEAN, ORDER["TS2_CLEAN"])  # 计算采用 clean n=4 T 分支的主路径。
    eta_inverse = (0.5 * (BASE_HIGH["SIDE3"] / TARGET_HIGH["SIDE3"] + BASE_HIGH["VS2"] / TARGET_HIGH["VS2"])) ** 2 - 1.0  # 反求两个高阶目标的共同有效质量增量。
    eta_book = 13.0 * PASSAGE_T / MASS21_T  # 用十三道通道 full/half 重复记账定义非拟合质量预算下界。
    high_inverse = high_prediction(eta_inverse)  # 计算质量逆拟合结果。
    high_book = high_prediction(eta_book)  # 计算固定记账错误结果。
    rows = rows_for("W0_strict_label", BASE_STRICT, strict_t, high_inverse, "auto_TS2_mode10", "inverse_effective_mass")  # 组装严格标签路径。
    rows += rows_for("W1_relabel_inverse_mass", BASE_CLEAN, clean_t, high_inverse, "clean_n4_mode16", "inverse_effective_mass")  # 组装近最优逆向路径。
    rows += rows_for("W2_relabel_bookkeeping", BASE_CLEAN, clean_t, high_book, "clean_n4_mode16", "fixed_full_half_bookkeeping")  # 组装主取证路径。
    model_stats = {name: stats([float(row["relative_error_percent"]) for row in rows if row["model"] == name]) for name in ("W0_strict_label", "W1_relabel_inverse_mass", "W2_relabel_bookkeeping")}  # 统计三个模型层级的五行误差。
    mean_overlap = 0.5 * (overlap(ORDER["TS1"]) + overlap(ORDER["TS2_CLEAN"]))  # 计算共享 T 分支的平均站位重叠。
    shared_height = (2.0 * math.pi) ** 2 * clean_a * mean_overlap * (0.5 * B_M) ** 2 / G  # 将共享错误项换算为有效虚假摆高。
    extra_height = (2.0 * math.pi) ** 2 * clean_b * (0.5 * B_M) ** 2 / G  # 将 TA1 端部项换算为额外虚假摆高。
    modal_mass = TOTAL_MASS_T * 1000.0 / TOTAL_LENGTH_M * MAIN_LENGTH_M / 2.0  # 估算两幅猫道主跨谐波模态质量。
    shared_kz = math.pi ** 2 * clean_a * modal_mass  # 将共享错误系数换算为每道相对竖向弹簧量级。
    extra_kz = math.pi ** 2 * clean_b * modal_mass  # 将 TA1 端部错误换算为局部弹簧量级。
    record = {"source_branch": "feat/catwalk-c0-c5-physical-reproduction", "source_head_at_design": "527dcd704a9625f3799a36c3ad527e0af3a1d1e1", "operator": "f_T,w^2=f_T,0^2+a*sum(phi_j^2)+b*I_TA1; f_H,w=f_H,0/sqrt(1+eta)", "W0_strict_label": {"a": strict_a, "b": strict_b, "prediction_hz": strict_t, "statistics": model_stats["W0_strict_label"]}, "W1_relabel_inverse_mass": {"a": clean_a, "b": clean_b, "eta": eta_inverse, "prediction_t_hz": clean_t, "prediction_high_hz": high_inverse, "statistics": model_stats["W1_relabel_inverse_mass"]}, "W2_relabel_bookkeeping": {"a": clean_a, "b": clean_b, "eta_fixed": eta_book, "prediction_t_hz": clean_t, "prediction_high_hz": high_book, "statistics": model_stats["W2_relabel_bookkeeping"]}, "mass_budget": {"inverse_effective_eta": eta_inverse, "duplicate_13_over_mass21": eta_book, "duplicate_21_over_mass21": 21.0 * PASSAGE_T / MASS21_T}, "mechanism_translation": {"shared_effective_pendulum_height_m": shared_height, "ta1_extra_effective_height_m": extra_height, "ta1_total_effective_height_m": shared_height + extra_height, "shared_kz_per_passage_N_per_m": shared_kz, "shared_kroll_per_passage_Nm_per_rad": shared_kz * B_M ** 2, "ta1_extra_kz_N_per_m": extra_kz, "ta1_extra_kroll_Nm_per_rad": extra_kz * B_M ** 2}, "mode_identification": {"auto_TS2_mode10": {"frequency_hz": BASE_STRICT["TS2"], "half_wave": 1, "template_mac": 0.6579286921367938}, "clean_T_mode16": {"frequency_hz": BASE_CLEAN["TS2"], "half_wave": 4, "template_mac": 0.9925879412497127, "physical_label": "TA2"}, "auto_VS2_mode13": {"frequency_hz": 0.14442351076238347, "half_wave": 1, "template_mac": 0.6523081554425327}, "true_VS2_mode21": {"frequency_hz": BASE_HIGH["VS2"], "half_wave": 5, "template_mac": 0.9388442018714379}}, "independent_wrong_3d_check_hz": {"TA1": 0.09809481, "TS1": 0.1087891, "clean_n4_T": 0.1517195}, "rows": rows}  # 汇总完整取证记录。
    fields = ("model", "label", "physical_baseline_hz", "attachment_target_hz", "wrong_model_hz", "relative_error_percent", "interpretation", "mechanism")  # 固定 CSV 列顺序。
    with (ROOT / "five_frequency_reproduction.csv").open("w", encoding="utf-8", newline="") as handle:  # 打开 CSV 输出文件。
        writer = csv.DictWriter(handle, fieldnames=fields)  # 创建字典式写入器。
        writer.writeheader()  # 写入列名。
        writer.writerows(rows)  # 写入全部逐分支结果。
    (ROOT / "forensic_fit.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 写入机器可读取证记录。
    print(json.dumps({"W0": record["W0_strict_label"], "W1": record["W1_relabel_inverse_mass"], "W2": record["W2_relabel_bookkeeping"], "mechanism": record["mechanism_translation"]}, ensure_ascii=False, indent=2))  # 打印精简执行收据。


if __name__ == "__main__":  # 仅直接执行时运行完整取证流程。
    main()  # 启动模型并生成 CSV 与 JSON。
