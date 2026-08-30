import copy  # 深拷贝图谱以执行不污染共享夹具的故障注入。
import unittest  # 使用标准库测试框架避免额外依赖。
from pathlib import Path  # 检查冻结文件和 Python 逐行注释约定。
from unittest.mock import patch  # 临时替换模态加载结果以验证跨文件一致性门。
import c3_agent  # 导入被测 C3 图谱智能体。


class C3AgentTests(unittest.TestCase):  # 定义模型迁移完整验收测试。
    @classmethod  # 在全部测试前只构图一次。
    def setUpClass(cls) -> None:  # 准备共享的确定性图谱与冻结输入。
        cls.graph = c3_agent.build_graph()  # 重建确定性图谱。
        cls.summary = c3_agent.graph_summary(cls.graph)  # 计算图谱汇总。
        cls.acceptance = c3_agent.migration_acceptance(cls.graph)  # 计算模型迁移验收收据。
        cls.cases = c3_agent.load_cases()  # 读取 43 个 C3 工况及源映射。
        cls.source_rows = c3_agent.load_source_authority()  # 读取完整源 43×37 权威矩阵。
        cls.migration_rows = c3_agent.load_case_migration()  # 读取逐工况分类迁移表。

    def test_case_agent_and_trace_counts(self) -> None:  # 校验 43 工况、四智能体与 43×4 决策链。
        self.assertEqual(len(self.cases), 43)  # 要求恰好 43 工况。
        self.assertEqual(self.summary["node_type_counts"]["Agent"], 4)  # 要求四智能体。
        self.assertEqual(self.summary["agent_decision_count"], 172)  # 要求 43×4 决策。
        self.assertEqual(len(self.graph["traces"]), 43)  # 要求每个工况恰好一条追踪。
        self.assertTrue(all([step["agent"] for step in trace["steps"]] == list(c3_agent.AGENTS) for trace in self.graph["traces"]))  # 要求每条追踪固定采用四智能体顺序。

    def test_source_authority_hashes_and_43_by_37_shape(self) -> None:  # 校验源权威收据、原始矩阵和归一化迁入矩阵的哈希边界。
        receipt_path = c3_agent.ROOT / "authority" / "I08_AUTHORITY.json"  # 定位逐字节迁入的源权威收据。
        matrix_path = c3_agent.ROOT / "authority" / "I08_GITHUB_43_CASE_MATRIX.csv"  # 定位换行归一化后的完整源矩阵。
        inventory = c3_agent.load_source_inventory()  # 读取记录原始 CRLF 矩阵哈希的资产清单。
        inventory_by_path = {asset["path"]: asset for asset in inventory["assets"]}  # 按源路径索引资产。
        self.assertEqual(c3_agent.file_sha256(receipt_path), "df10da1c759cea9e93c065d9456e583a1944b7b3eb1a730ea048f1821dddc5b7")  # 锁定源权威收据原始字节。
        self.assertEqual(c3_agent.file_sha256(matrix_path), "95fe97e73b3bec61124147b9c29a4ed3abf6217537e8bf082eca707426f3625a")  # 锁定 CRLF 转 LF 后的迁入矩阵。
        self.assertEqual(inventory_by_path["authority/I08_GITHUB_43_CASE_MATRIX.csv"]["sha256"], "12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f")  # 锁定源仓库中 CRLF 原始矩阵哈希。
        self.assertEqual(len(self.source_rows), 43)  # 要求完整保留 43 行权威工况。
        self.assertTrue(all(len(row) == 37 for row in self.source_rows))  # 要求每行完整保留全部 37 列。
        self.assertEqual(len({row["github_scenario_id"] for row in self.source_rows}), 43)  # 要求源工况 ID 唯一。

    def test_source_order_and_values_are_mapped_without_loss(self) -> None:  # 校验源顺序不会被 C3 展示顺序覆盖且关键值逐案一致。
        cases_by_id = {case["id"]: case for case in self.cases}  # 按工况 ID 索引 C3 工况。
        source_ids = {row["github_scenario_id"] for row in self.source_rows}  # 收集源工况身份集合。
        self.assertEqual(source_ids, set(cases_by_id))  # 要求源与 C3 的 43 个身份完全一致。
        self.assertEqual(sorted(case["source_case_index"] for case in self.cases), list(range(1, 44)))  # 要求源序号完整覆盖 1 至 43。
        self.assertEqual(sum(case["source_case_index"] != case["c3_order"] for case in self.cases), 20)  # 固定记录二十项源顺序与 C3 展示顺序差异。
        for source in self.source_rows:  # 逐案核验映射身份和关键值。
            case = cases_by_id[source["github_scenario_id"]]  # 取得对应 C3 工况。
            expected_gust = float(source["gust3s_ms"]) if source["gust3s_ms"] else None  # 类型化源阵风缺失值。
            self.assertEqual(case["source_case_index"], int(source["case_index"]))  # 校验源顺序逐案保留。
            self.assertEqual(case["source_i08_case_id"], source["i08_case_id"])  # 校验原 I08 工况标识逐案保留。
            self.assertEqual(case["source_name_cn"], source["name_cn"])  # 校验源中文名称逐案保留。
            self.assertEqual(case["U10_mps"], float(source["U10_sustained_ms"]))  # 校验 U10 风速未失真。
            self.assertEqual(case["gust_mps"], expected_gust)  # 校验阵风值或缺失状态未失真。
            self.assertEqual(case["grade"], source["confidence"])  # 校验源置信等级未失真。

    def test_source_35_8_and_c3_33_10_are_separate(self) -> None:  # 校验源平稳性分类与 C3 求解适用性不被混写。
        source_stationary = sum(row["stationarity"] == "stationary_ok" for row in self.source_rows)  # 统计源平稳工况。
        source_reference = sum(row["stationarity"] == "reference_only" for row in self.source_rows)  # 统计源参考工况。
        c3_stationary = sum(case["stationary"] for case in self.cases)  # 统计 C3 可进入平稳映射的工况。
        c3_envelope = sum(not case["stationary"] for case in self.cases)  # 统计 C3 仅包络参考工况。
        reclassified = {row["case_id"] for row in self.migration_rows if row["classification_disposition"] == "C3_ENVELOPE_ONLY_RECLASSIFIED"}  # 提取显式重分类工况。
        self.assertEqual((source_stationary, source_reference), (35, 8))  # 要求源权威分类为 35 加 8。
        self.assertEqual((c3_stationary, c3_envelope), (33, 10))  # 要求 C3 策略分类为 33 加 10。
        self.assertEqual(reclassified, {"cape_denison_katabatic", "piteraq_tasiilaq"})  # 要求仅这两项发生 C3 包络重分类。
        for case in self.cases:  # 逐案检查重分类语义。
            if case["id"] in reclassified:  # 仅处理两项重分类工况。
                self.assertEqual(case["source_stationarity"], "stationary_ok")  # 要求保留其源平稳分类。
                self.assertFalse(case["stationary"])  # 要求 C3 层明确仅作包络参考。

    def test_model_migration_acceptance_passes_all_checks(self) -> None:  # 校验模型迁移收据的每一项门均通过。
        self.assertEqual(self.acceptance["scope"], "MODEL_MIGRATION_ONLY")  # 要求收据范围不越界到响应求解。
        self.assertEqual(self.acceptance["status"], "PASS")  # 要求完整迁移验收通过。
        self.assertTrue(all(self.acceptance["checks"].values()))  # 要求没有被总状态掩盖的失败子项。
        self.assertEqual(self.acceptance["source_snapshot"]["excluded_legacy_metric_observations"], 2064)  # 要求明确记录被排除的旧数值指标节点。
        self.assertEqual(self.acceptance["reclassified_case_ids"], ["cape_denison_katabatic", "piteraq_tasiilaq"])  # 要求收据输出精确重分类清单。

    def test_all_36_source_assets_are_accounted_without_numeric_transfer(self) -> None:  # 校验源包逐文件有处置且零旧响应数值迁入。
        inventory = c3_agent.load_source_inventory()  # 读取源资产处置清单。
        source_asset_nodes = [node for node in self.graph["nodes"] if node["type"] == "SourceAsset"]  # 提取图谱中的源资产节点。
        self.assertEqual((inventory["asset_count"], len(inventory["assets"]), inventory["source_total_bytes"]), (36, 36, 6196831))  # 固定源包文件数与总字节数。
        self.assertTrue(inventory["all_assets_accounted"])  # 要求清单声明全部源资产均已处置。
        self.assertFalse(inventory["numeric_value_transfer"])  # 要求包级数值迁移关闭。
        self.assertTrue(all(asset["disposition"] and asset["target"] and not asset["numeric_value_transfer"] for asset in inventory["assets"]))  # 要求逐文件有目标处置且禁用数值迁移。
        self.assertEqual(len(source_asset_nodes), 36)  # 要求 36 项资产均进入图谱语义层。

    def test_c3_response_and_warning_boundary(self) -> None:  # 校验 43 个 C3 响应均为空且预警不可派发。
        response_nodes = [node for node in self.graph["nodes"] if node["type"] == "C3CaseResponse"]  # 提取 C3 响应节点。
        self.assertEqual(len(response_nodes), 43)  # 要求恰好 43 个响应状态节点。
        self.assertTrue(all(node["properties"] == {"state": "NOT_MATERIALIZED", "transferred_numeric_values": False} for node in response_nodes))  # 要求响应节点仅含严格白名单字段。
        self.assertEqual(self.summary["warning_counts"]["NOT_ARMED"], 43)  # 要求全部预警状态均未武装。
        self.assertEqual(self.summary["dispatch_true_count"], 0)  # 要求无真实派发。
        self.assertEqual(self.summary["physics_decision_counts"], {"AWAITING_C3_CASE_RESPONSE": 33, "REFERENCE_ONLY_C3_ENVELOPE": 10})  # 要求物理处置反映 C3 的 33 加 10 策略。

    def test_graph_has_unique_nodes_edges_and_valid_endpoints(self) -> None:  # 校验图谱身份唯一且没有悬空边。
        node_ids = [node["id"] for node in self.graph["nodes"]]  # 收集节点 ID 并保留重复可能性。
        edge_ids = [edge["id"] for edge in self.graph["edges"]]  # 收集边 ID 并保留重复可能性。
        node_id_set = set(node_ids)  # 建立端点查找集合。
        self.assertEqual(len(node_ids), len(node_id_set))  # 要求节点 ID 唯一。
        self.assertEqual(len(edge_ids), len(set(edge_ids)))  # 要求边 ID 唯一。
        self.assertTrue(all(edge["source"] in node_id_set and edge["target"] in node_id_set for edge in self.graph["edges"]))  # 要求所有边端点存在。

    def test_duplicate_node_fault_is_rejected(self) -> None:  # 故障注入验证重复节点不能通过迁移验收。
        damaged = copy.deepcopy(self.graph)  # 复制图谱避免污染其他测试。
        damaged["nodes"].append(copy.deepcopy(damaged["nodes"][0]))  # 注入一个重复 ID 节点。
        receipt = c3_agent.migration_acceptance(damaged)  # 对损坏图谱重新验收。
        self.assertFalse(receipt["checks"]["node_ids_unique"])  # 要求唯一性子门明确失败。
        self.assertEqual(receipt["status"], "FAIL")  # 要求总体迁移验收失败。

    def test_numeric_response_injection_is_rejected(self) -> None:  # 故障注入验证任何伪 C3 响应数值都会被拒绝。
        damaged = copy.deepcopy(self.graph)  # 复制图谱避免污染其他测试。
        response = next(node for node in damaged["nodes"] if node["type"] == "C3CaseResponse")  # 定位一个空响应节点。
        response["properties"]["rms_displacement_m"] = 0.0123  # 注入不允许的伪结构响应数值。
        receipt = c3_agent.migration_acceptance(damaged)  # 对损坏图谱重新验收。
        self.assertFalse(receipt["checks"]["responses_strictly_empty_43"])  # 要求响应白名单子门明确失败。
        self.assertEqual(receipt["status"], "FAIL")  # 要求总体迁移验收失败。

    def test_missing_has_case_edge_is_rejected(self) -> None:  # 故障注入验证缺少任何项目到工况关系都会被拒绝。
        damaged = copy.deepcopy(self.graph)  # 复制图谱避免污染其他测试。
        missing_edge = next(edge for edge in damaged["edges"] if edge["relation"] == "HAS_CASE")  # 定位一个项目到工况关系。
        damaged["edges"].remove(missing_edge)  # 删除该关系模拟迁移漏项。
        receipt = c3_agent.migration_acceptance(damaged)  # 对损坏图谱重新验收。
        self.assertFalse(receipt["checks"]["has_case_43"])  # 要求 43 工况包含关系子门明确失败。
        self.assertEqual(receipt["status"], "FAIL")  # 要求总体迁移验收失败。

    def test_modal_frequency_tampering_is_rejected(self) -> None:  # 故障注入验证模态 CSV 与模型收据不一致时失败。
        tampered_modes = copy.deepcopy(c3_agent.load_modes())  # 复制冻结十四阶模态表。
        tampered_modes[0]["frequency_hz"] += 0.001  # 篡改第一阶频率以模拟跨文件漂移。
        with patch.object(c3_agent, "load_modes", return_value=tampered_modes):  # 仅在本验收调用内注入篡改结果。
            receipt = c3_agent.migration_acceptance(self.graph)  # 对篡改模态重新验收。
        self.assertFalse(receipt["checks"]["modal_receipt_matches_csv_14"])  # 要求模态跨文件一致性子门明确失败。
        self.assertEqual(receipt["status"], "FAIL")  # 要求总体迁移验收失败。

    def test_legacy_pointers_are_complete_linked_and_non_authoritative(self) -> None:  # 校验逐案旧结果指针可定位但绝不充当 C3 真值。
        required = {"source_commit", "source_path", "source_file_sha256", "source_i08_case_id", "source_row_key", "use_as_c3_truth"}  # 定义旧结果指针必需字段。
        pointers = [node for node in self.graph["nodes"] if node["type"] == "LegacyResultPointer"]  # 提取全部旧结果指针。
        set_links = [edge for edge in self.graph["edges"] if edge["relation"] == "PART_OF_LEGACY_RESULT_SET"]  # 提取指回旧结果集的关系。
        provenance_links = [edge for edge in self.graph["edges"] if edge["relation"] == "PROVENANCE_ONLY"]  # 提取只作谱系的关系。
        self.assertEqual((len(pointers), len(set_links), len(provenance_links)), (43, 43, 43))  # 要求每案都有完整的两段谱系链。
        self.assertTrue(all(required.issubset(pointer["properties"]) and pointer["properties"]["use_as_c3_truth"] is False for pointer in pointers))  # 要求指针字段完整且禁止作为 C3 真值。
        self.assertTrue(all(edge["target"] == "legacy:I08-double-mct" for edge in set_links))  # 要求每个逐案指针均接回冻结旧结果集。
        self.assertTrue(all(edge["properties"].get("numerical_value_transfer") is False for edge in provenance_links))  # 要求逐案谱系边显式禁止数值迁移。

    def test_table41_mode_pairings_are_not_aligned_or_accepted(self) -> None:  # 校验 Table4-1 候选没有被误写成已对齐或已验收配对。
        pairings = c3_agent.load_rows(c3_agent.ROOT / "table41_c3_pairing.csv")  # 读取十四阶配对处置表。
        status_by_mode = {int(row["c3_mode"]): row["mapping_status"] for row in pairings}  # 按 C3 阶次索引映射状态。
        self.assertEqual(len(pairings), 14)  # 要求十四阶均有显式处置。
        self.assertTrue(all(status in {"UNRESOLVED", "NOT_ALIGNED"} for status in status_by_mode.values()))  # 要求所有状态只可能未解析或未对齐。
        self.assertFalse(any("WORKING_PAIR" in status or "ACCEPTED" in status for status in status_by_mode.values()))  # 禁止任何工作配对或已验收配对状态。
        self.assertEqual({mode for mode, status in status_by_mode.items() if status == "NOT_ALIGNED"}, {3, 4, 10, 14})  # 锁定四个有候选但未对齐的阶次。

    def test_c3_model_binding_identity(self) -> None:  # 校验 C3 模型、求解器和十四阶模态收据身份。
        binding = c3_agent.read_json(c3_agent.ROOT / "model_binding.json")  # 读取模型绑定。
        self.assertEqual(binding["object"], "张靖皋长江大桥南航道桥施工猫道 C3")  # 校验桥名和 C3 对象没有错别字。
        self.assertEqual(binding["deck"]["sha256"], "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86")  # 检查 deck 哈希。
        self.assertEqual(binding["solver"]["sha256"], "b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e")  # 检查求解器哈希。
        self.assertEqual((binding["modal_receipt"]["nodes"], binding["modal_receipt"]["elements"], binding["modal_receipt"]["active_equations"]), (91415, 172998, 439122))  # 检查求解规模收据。
        self.assertEqual(len(binding["modal_receipt"]["frequencies_hz"]), 14)  # 检查频率数。

    def test_generated_sha_manifest_and_repeat_build_are_stable(self) -> None:  # 校验核心生成物哈希账本与重复构建字节稳定性。
        _, first_validation, first_manifest = c3_agent.materialize_graph(self.graph)  # 第一次物化完整迁移生成物。
        first_records = {record["path"]: record["sha256"] for record in first_manifest["records"]}  # 保存第一次构建的七项哈希。
        _, second_validation, second_manifest = c3_agent.materialize_graph(self.graph)  # 以相同冻结输入再次物化。
        second_records = {record["path"]: record["sha256"] for record in second_manifest["records"]}  # 保存第二次构建的七项哈希。
        ledger_lines = (c3_agent.OUTPUT_DIR / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()  # 读取兼容 sha256sum 的生成物账本。
        self.assertEqual((first_validation["status"], second_validation["status"]), ("PASS", "PASS"))  # 要求两次迁移校验均通过。
        self.assertEqual(first_manifest["artifact_count"], 7)  # 要求账本恰好覆盖七个核心生成物。
        self.assertEqual(first_records, second_records)  # 要求相同输入的两次构建逐文件哈希完全相同。
        self.assertEqual(len(ledger_lines), 7)  # 要求文本账本没有遗漏或额外可变 Demo 文件。
        self.assertTrue(all(line.split("  ", 1)[0] == second_records[line.split("  ", 1)[1]] for line in ledger_lines))  # 要求文本账本每行与实际计算结果一致。

    def test_offline_answer_preserves_model_boundary(self) -> None:  # 校验演示回答不会越过模型迁移边界。
        result = c3_agent.run_ask("site_gb50009_100yr", "说明当前证据", True, False)  # 强制离线问答避免外部依赖。
        self.assertEqual(result["response"]["mode"], "offline")  # 检查确定性离线路径。
        self.assertIn("NOT_MATERIALIZED", result["response"]["answer"])  # 检查 C3 响应缺口声明。
        self.assertIn("dispatch=false", result["response"]["answer"])  # 检查不派发边界。

    def test_python_nonblank_lines_have_comments(self) -> None:  # 校验用户要求的逐行代码注释。
        for filename in ("c3_agent.py", "test_c3_agent.py"):  # 遍历本包 Python 文件。
            path = Path(__file__).resolve().parent / filename  # 构造源码路径。
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # 遍历源码行。
                if line.strip():  # 仅检查非空行。
                    self.assertIn("#", line, f"{filename}:{line_number} lacks a comment")  # 要求每行包含注释标记。


if __name__ == "__main__":  # 仅在直接执行时运行测试。
    unittest.main()  # 启动测试框架。
