from __future__ import annotations  # 启用延迟类型注解以保持模板接口稳定。
import argparse  # 解析局部预测请求与响应文件路径。
from pathlib import Path  # 管理外部交换文件路径。
import numpy as np  # 读取局部候选请求数据并定义响应接口。
def parser() -> argparse.ArgumentParser:  # 创建局部预测器外部接口参数解析器。
    argument_parser = argparse.ArgumentParser(description="局部预测型AFEM变分问题接口模板")  # 定义模板用途说明。
    argument_parser.add_argument("--request", type=Path, required=True, help="benchmark写出的局部候选请求NPZ")  # 添加请求文件参数。
    argument_parser.add_argument("--response", type=Path, required=True, help="局部变分预测器应写出的JSON响应")  # 添加响应文件参数。
    return argument_parser  # 返回配置完成的解析器。
def main() -> None:  # 演示局部低维问题求解器需要实现的最小文件契约。
    arguments = parser().parse_args()  # 解析请求与响应路径。
    request = np.load(arguments.request, allow_pickle=False)  # 读取当前全局状态、候选区域和候选动作数据。
    region = int(np.asarray(request["region"]).reshape(-1)[0])  # 读取当前局部候选区域编号。
    request.close()  # 关闭NPZ请求文件句柄。
    raise NotImplementedError(f"请在此求解区域{region}的低维局部富集或替换问题，并向{arguments.response}写出predicted_error_reduction")  # 禁止模板用ZZ指标冒充局部预测误差下降。
if __name__ == "__main__":  # 检查模板是否作为独立外部程序执行。
    main()  # 启动局部预测器外部接口模板。
