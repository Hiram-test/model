from __future__ import annotations  # 启用延迟类型注解以保持模板接口稳定。
import argparse  # 解析AMBER请求与响应文件路径。
from pathlib import Path  # 管理外部交换文件路径。
import numpy as np  # 读取请求NPZ并定义响应数组接口。
def parser() -> argparse.ArgumentParser:  # 创建AMBER外部推理模板参数解析器。
    argument_parser = argparse.ArgumentParser(description="AMBER检查点推理接口模板")  # 定义模板用途说明。
    argument_parser.add_argument("--request", type=Path, required=True, help="benchmark写出的AMBER请求NPZ")  # 添加请求文件参数。
    argument_parser.add_argument("--response", type=Path, required=True, help="外部模型应写出的尺寸场NPZ")  # 添加响应文件参数。
    return argument_parser  # 返回配置完成的解析器。
def main() -> None:  # 演示外部AMBER检查点需要实现的最小文件契约。
    arguments = parser().parse_args()  # 解析请求与响应路径。
    request = np.load(arguments.request, allow_pickle=False)  # 读取节点、边、节点特征和当前节点尺寸。
    node_count = int(len(request["nodes"]))  # 读取当前中间网格节点数量。
    request.close()  # 关闭NPZ请求文件句柄。
    raise NotImplementedError(f"请在此加载真实AMBER检查点并写出shape=({node_count},)的node_sizes到{arguments.response}")  # 禁止模板伪造尺寸场结果。
if __name__ == "__main__":  # 检查模板是否作为独立外部程序执行。
    main()  # 启动AMBER外部接口模板。
