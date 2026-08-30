import unittest  # 使用标准库测试框架避免额外依赖。
from pathlib import Path  # 检查 Python 逐行注释约定。
import c3_agent  # 导入被测 C3 图谱智能体。


class C3AgentTests(unittest.TestCase):  # 定义完整迁移验收测试。
    @classmethod  # 在全部测试前只构图一次。
    def setUpClass(cls) -> None:  # 准备共享图谱。
        cls.graph = c3_agent.build_graph()  # 重建确定性图谱。
        cls.summary = c3_agent.graph_summary(cls.graph)  # 计算图谱汇总。

    def test_case_and_agent_counts(self) -> None:  # 校验 43 工况和四智能体。
        self.assertEqual(len(c3_agent.load_cases()), 43)  # 要求恰好 43 工况。
        self.assertEqual(self.summary["node_type_counts"]["Agent"], 4)  # 要求四智能体。
        self.assertEqual(self.summary["agent_decision_count"], 172)  # 要求 43×4 决策。

    def test_c3_response_boundary(self) -> None:  # 校验 C3 响应未被伪造。
        self.assertEqual(self.summary["case_response_not_materialized"], 43)  # 要求 43 个空响应状态。
        self.assertEqual(self.summary["warning_counts"]["NOT_ARMED"], 43)  # 要求 43 个 NOT_ARMED。
        self.assertEqual(self.summary["dispatch_true_count"], 0)  # 要求无派发。

    def test_nonstationary_reference_count(self) -> None:  # 校验当前 C3 清单的非平稳分类。
        self.assertEqual(self.summary["physics_decision_counts"]["REFERENCE_ONLY_NONSTATIONARY"], 10)  # 要求十个参考工况。
        self.assertEqual(self.summary["physics_decision_counts"]["AWAITING_C3_CASE_RESPONSE"], 33)  # 要求三十三个待算工况。

    def test_edge_endpoints(self) -> None:  # 校验图谱没有悬空边。
        node_ids = {node["id"] for node in self.graph["nodes"]}  # 建立节点集合。
        self.assertTrue(all(edge["source"] in node_ids and edge["target"] in node_ids for edge in self.graph["edges"]))  # 要求所有端点存在。

    def test_model_binding(self) -> None:  # 校验 C3 模型身份。
        binding = c3_agent.read_json(c3_agent.ROOT / "model_binding.json")  # 读取模型绑定。
        self.assertEqual(binding["deck"]["sha256"], "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86")  # 检查 deck 哈希。
        self.assertEqual(binding["solver"]["sha256"], "b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e")  # 检查求解器哈希。
        self.assertEqual(len(binding["modal_receipt"]["frequencies_hz"]), 14)  # 检查频率数。

    def test_offline_demo(self) -> None:  # 校验无 API 也能运行 Demo。
        result = c3_agent.run_ask("site_gb50009_100yr", "说明当前证据", True, False)  # 强制离线问答。
        self.assertEqual(result["response"]["mode"], "offline")  # 检查离线路径。
        self.assertIn("NOT_MATERIALIZED", result["response"]["answer"])  # 检查关键边界。
        self.assertIn("dispatch=false", result["response"]["answer"])  # 检查不派发边界。

    def test_python_nonblank_lines_have_comments(self) -> None:  # 校验用户要求的逐行代码注释。
        for filename in ("c3_agent.py", "test_c3_agent.py"):  # 遍历本包 Python 文件。
            path = Path(__file__).resolve().parent / filename  # 构造源码路径。
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # 遍历源码行。
                if line.strip():  # 仅检查非空行。
                    self.assertIn("#", line, f"{filename}:{line_number} lacks a comment")  # 要求每行包含注释标记。


if __name__ == "__main__":  # 仅在直接执行时运行测试。
    unittest.main()  # 启动测试框架。

