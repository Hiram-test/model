"""把有限构件节点台账转换成模态识别流水线要求的补充节点注册表。"""

from __future__ import annotations

import csv
from pathlib import Path


# SCRIPT_DIR 是 V2.0 根目录；输入与输出都由该目录稳定定位。
SCRIPT_DIR = Path(__file__).resolve().parent
# SOURCE_CSV 是有限门架/横通道生成器的完整节点台账，其中包含物理节点和方向节点。
SOURCE_CSV = SCRIPT_DIR / "builder" / "generated" / "generated_nodes.csv"
# OUTPUT_CSV 采用后处理脚本约定的稳定列名，并放在 run 目录供正式结果直接引用。
OUTPUT_CSV = SCRIPT_DIR / "run" / "v2_component_node_registry.csv"


def main() -> None:
    """读取生成节点、剔除纯方向节点并写出构件节点注册表。

    参数：
        无。

    返回：
        无。结果写入 ``OUTPUT_CSV``。

    说明：
        BEAM188 的第三方向节点只用于定义局部截面轴，不承担结构位移，也不应被
        计入门架/通道局部参与 RMS；因此只输出 ``is_orientation=0`` 的物理节点。
    """

    # 输入缺失意味着有限拓扑尚未封板，此时不能生成与错误节点号对应的注册表。
    if not SOURCE_CSV.is_file():
        raise FileNotFoundError(f"缺少有限构件节点台账：{SOURCE_CSV}")
    # 输出目录允许重复创建；该操作不会删除求解目录中的任何既有结果。
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # rows 保存已经转换为后处理协议的全部物理节点记录。
    rows: list[dict[str, str]] = []
    # utf-8-sig 同时兼容普通 UTF-8 和带 BOM 的 CSV；newline='' 防止 Windows 空行。
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        # reader 通过字段名读取，避免依赖 builder 将来增加审计列后的列序变化。
        reader = csv.DictReader(stream)
        # 逐个生成节点筛选；方向节点必须明确为字符串 ``1`` 才剔除。
        for source_row in reader:
            # 该分支排除只定义梁截面方向、没有独立物理质量/位移意义的 K 节点。
            if source_row["is_orientation"].strip() == "1":
                continue
            # system 只能是 gate 或 passage；其他值表示 builder 协议发生了意外变化。
            component_class = source_row["system"].strip()
            # 未知类别会破坏局部参与分组，因此不允许静默降级为 other。
            if component_class not in {"gate", "passage"}:
                raise ValueError(
                    f"节点 {source_row['apdl_node_id']} 的 system={component_class!r} 非法。"
                )
            # family 同时保留 assembly 和 role，便于定位某一品门架或某一根通道杆节点。
            family = (
                f"{source_row['assembly_name'].strip()}::"
                f"{source_row['role'].strip()}"
            )
            # 坐标已经是 X 顺桥、Y 横桥、Z 竖向，无需再次交换或变号。
            rows.append(
                {
                    "node_id": source_row["apdl_node_id"].strip(),
                    "X_mm": source_row["x_mm"].strip(),
                    "Y_mm": source_row["y_mm"].strip(),
                    "Z_mm": source_row["z_mm"].strip(),
                    "family": family,
                    "component_class": component_class,
                }
            )

    # 空注册表会让后处理误以为局部参与为零，必须在写盘前阻止。
    if not rows:
        raise RuntimeError("有限构件物理节点注册表为空。")
    # 节点号必须唯一；重复号通常表示 builder 编号冲突或 CSV 重复拼接。
    node_ids = [int(row["node_id"]) for row in rows]
    # set 长度与列表长度不等即存在重复节点号。
    if len(set(node_ids)) != len(node_ids):
        raise RuntimeError("有限构件物理节点注册表存在重复 node_id。")

    # 固定字段顺序与 modal_identification_pipeline.py 的公开协议一致。
    fieldnames = ["node_id", "X_mm", "Y_mm", "Z_mm", "family", "component_class"]
    # 写出 UTF-8 BOM，便于 Excel/PowerShell 直接识别中文 family 字段。
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        # writer 负责正确转义 family 中可能出现的标点。
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        # 按 builder 原始稳定节点号顺序写出，方便逐行差异比较。
        writer.writerows(rows)

    # 标准输出只报告路径和数量，供批处理记录快速核对。
    print(f"{OUTPUT_CSV}\nphysical_component_nodes={len(rows)}")


# 作为主程序调用时生成注册表；导入模块不会产生文件副作用。
if __name__ == "__main__":
    main()
