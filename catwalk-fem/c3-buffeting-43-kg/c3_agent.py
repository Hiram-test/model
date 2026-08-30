from __future__ import annotations  # 允许现代类型注解且保持 Python 3.10 兼容。
import argparse  # 解析构图、校验和问答命令。
import csv  # 读取工况与模态表并输出扁平图谱表。
import json  # 序列化图谱、追踪和 Demo 结果。
import os  # 从运行环境安全读取 Doubao 配置。
import sys  # 向命令行输出确定性 JSON。
import urllib.error  # 提供火山方舟 HTTP 错误类型。
import urllib.request  # 使用标准库调用 OpenAI 兼容接口。
from collections import Counter  # 汇总节点、边和决策类型计数。
from pathlib import Path  # 构造与当前脚本绑定的稳定路径。
from typing import Any  # 标注结构化事实和图谱属性。

ROOT = Path(__file__).resolve().parent  # 将所有输入输出固定到包目录。
OUTPUT_DIR = ROOT / "generated"  # 保存可复查的图谱与 Demo 产物。
AGENTS = ("AuthorityAgent", "SolverEvidenceAgent", "PhysicsBoundaryAgent", "WarningPolicyAgent")  # 固定四智能体顺序。
KEY_NAMES = ("DOUBAO_API_KEY", "DOUBAO_API", "DOUBAO_KEY", "DOUBAO_TOKEN", "DOUBAO", "DOUBAO_APIKEY", "DOUBAO_API_SECRET", "ARK_API_KEY", "ARK_KEY", "ARK_TOKEN", "VOLCENGINE_API_KEY", "VOLCENGINE_KEY")  # 兼容仓库中常见的 Secret 名称。
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"  # 使用火山方舟官方 v3 Base URL。
DEFAULT_MODEL = "doubao-seed-1-8-251228"  # 使用当前豆包 Seed 1.8 模型 ID。
DESIGN_WIND_MPS = 38.9  # 仅用于无量纲风速平方比，不作为 C3 响应阈值。


def read_json(path: Path) -> dict[str, Any]:  # 读取 UTF-8 JSON 配置。
    return json.loads(path.read_text(encoding="utf-8"))  # 返回结构化字典。


def load_rows(path: Path) -> list[dict[str, str]]:  # 读取 UTF-8 CSV 并保留列名。
    with path.open("r", encoding="utf-8", newline="") as handle:  # 使用 newline 规则避免跨平台空行。
        return list(csv.DictReader(handle))  # 将每一行转换为字典。


def load_cases() -> list[dict[str, Any]]:  # 读取并类型化 43 工况。
    cases: list[dict[str, Any]] = []  # 初始化稳定顺序的工况列表。
    for raw in load_rows(ROOT / "cases_43.csv"):  # 按仓库清单顺序遍历。
        case: dict[str, Any] = dict(raw)  # 复制原始字段以保留数据谱系。
        case["n"] = int(raw["n"])  # 将序号转换为整数。
        case["U10_mps"] = float(raw["U10_mps"])  # 将十米风速转换为浮点数。
        case["gust_mps"] = float(raw["gust_mps"]) if raw["gust_mps"] else None  # 保留缺失阵风为 null。
        case["stationary"] = raw["stationary"].strip().lower() == "true"  # 将平稳标志转换为布尔值。
        case["c3_case_id"] = f"C3-{raw['id']}-S20260830"  # 建立 C3 原生工况标识。
        case["c3_response_state"] = "NOT_MATERIALIZED"  # 明确 C3 抖振响应尚未物化。
        case["wind_pressure_index"] = round((case["U10_mps"] / DESIGN_WIND_MPS) ** 2, 6)  # 计算无量纲风速平方比。
        cases.append(case)  # 追加类型化工况。
    return cases  # 返回全部工况。


def load_modes() -> list[dict[str, Any]]:  # 读取 C3 原生 14 阶模态。
    modes: list[dict[str, Any]] = []  # 初始化模态列表。
    for raw in load_rows(ROOT / "modes_c3_ft14.csv"):  # 遍历冻结模态表。
        mode: dict[str, Any] = dict(raw)  # 复制原始字段。
        mode["mode"] = int(raw["mode"])  # 将阶次转换为整数。
        mode["frequency_hz"] = float(raw["frequency_hz"])  # 将频率转换为浮点数。
        modes.append(mode)  # 追加模态记录。
    return modes  # 返回 14 阶模态。


def make_trace(case: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:  # 对一个工况执行四智能体。
    authority = {  # 构造权威来源决策。
        "agent": "AuthorityAgent",  # 记录执行智能体。
        "status": "PASS",  # 工况存在于锁定清单时通过。
        "facts": {"case_id": case["id"], "source_order": case["n"], "grade": case["grade"]},  # 绑定工况身份事实。
        "decision": "C3_CASE_AUTHORITY_CONFIRMED",  # 输出 C3 工况权威状态。
    }  # 完成权威来源决策。
    solver = {  # 构造求解证据决策。
        "agent": "SolverEvidenceAgent",  # 记录执行智能体。
        "status": "MODAL_EVIDENCE_ONLY",  # 模态证据存在但工况响应不存在。
        "facts": {"deck_sha256": binding["deck"]["sha256"], "modal_modes": binding["modal_receipt"]["requested_modes"], "case_response": case["c3_response_state"]},  # 绑定模型证据。
        "decision": "C3_MODAL_EVIDENCE_BOUND_CASE_RESPONSE_NOT_MATERIALIZED",  # 输出响应证据状态。
    }  # 完成求解证据决策。
    physics_decision = "AWAITING_C3_CASE_RESPONSE" if case["stationary"] else "REFERENCE_ONLY_NONSTATIONARY"  # 根据平稳性选择物理处置。
    physics = {  # 构造物理边界决策。
        "agent": "PhysicsBoundaryAgent",  # 记录执行智能体。
        "status": physics_decision,  # 使用确定性物理状态。
        "facts": {"stationary": case["stationary"], "c3_layer": case["c3_layer"], "claim": case["c3_claim"], "legacy_value_transfer": False},  # 记录边界事实。
        "decision": physics_decision,  # 输出物理状态。
    }  # 完成物理边界决策。
    warning = {  # 构造预警策略决策。
        "agent": "WarningPolicyAgent",  # 记录执行智能体。
        "status": "NOT_ARMED",  # 当前仅为证据推演。
        "facts": {"physics_decision": physics_decision, "dispatch": False, "c3_response": case["c3_response_state"]},  # 记录不派发事实。
        "decision": "NOT_ARMED",  # 输出证据状态。
    }  # 完成预警策略决策。
    return {  # 返回完整追踪。
        "trace_id": f"trace:{case['c3_case_id']}",  # 建立稳定追踪 ID。
        "case_id": case["id"],  # 绑定原始工况 ID。
        "c3_case_id": case["c3_case_id"],  # 绑定 C3 工况 ID。
        "steps": [authority, solver, physics, warning],  # 固定四步顺序。
        "final_status": "NOT_ARMED",  # 固定当前终态。
        "dispatch": False,  # 禁止把 Demo 变成运行指令。
    }  # 完成追踪对象。


def add_node(node_list: list[dict[str, Any]], node_id: str, node_type: str, **properties: Any) -> None:  # 追加唯一图谱节点。
    node_list.append({"id": node_id, "type": node_type, "properties": properties})  # 使用统一节点结构。


def add_edge(edge_list: list[dict[str, Any]], source: str, relation: str, target: str, **properties: Any) -> None:  # 追加有向图谱边。
    edge_id = f"edge:{len(edge_list) + 1:04d}"  # 按稳定顺序生成边 ID。
    edge_list.append({"id": edge_id, "source": source, "relation": relation, "target": target, "properties": properties})  # 使用统一边结构。


def build_graph() -> dict[str, Any]:  # 从冻结输入重建完整 C3 图谱。
    cases = load_cases()  # 载入 43 工况。
    modes = load_modes()  # 载入 14 阶模态。
    binding = read_json(ROOT / "model_binding.json")  # 载入 C3 模型绑定。
    lineage = read_json(ROOT / "legacy_double_mct_lineage.json")  # 载入旧模型谱系。
    nodes: list[dict[str, Any]] = []  # 初始化节点列表。
    edges: list[dict[str, Any]] = []  # 初始化边列表。
    add_node(nodes, "project:C3-43KG", "Project", name="C3 × 43 工况知识图谱智能体", schema="catwalk-c3-kg/v2")  # 添加项目节点。
    add_node(nodes, "model:C3", "C3Model", **binding)  # 添加 C3 模型节点。
    add_node(nodes, "artifact:C3-deck", "EvidenceArtifact", **binding["deck"])  # 添加 deck 证据节点。
    add_node(nodes, "artifact:C3-solver", "EvidenceArtifact", **binding["solver"])  # 添加求解器证据节点。
    add_node(nodes, "run:C3-FT14", "C3ModalRun", **binding["modal_receipt"])  # 添加原生模态运行节点。
    add_node(nodes, "legacy:I08-double-mct", "LegacyResultSet", **lineage)  # 添加旧模型结果集谱系节点。
    add_edge(edges, "project:C3-43KG", "BINDS_MODEL", "model:C3")  # 连接项目与 C3 模型。
    add_edge(edges, "model:C3", "EVIDENCED_BY", "artifact:C3-deck")  # 连接模型与 deck。
    add_edge(edges, "model:C3", "SOLVED_BY", "artifact:C3-solver")  # 连接模型与求解器。
    add_edge(edges, "model:C3", "HAS_MODAL_RUN", "run:C3-FT14")  # 连接模型与模态运行。
    add_edge(edges, "legacy:I08-double-mct", "PROVENANCE_ONLY_FOR", "project:C3-43KG", numerical_value_transfer=False)  # 明确旧结果仅为谱系。
    for agent_name in AGENTS:  # 创建四智能体节点。
        add_node(nodes, f"agent:{agent_name}", "Agent", name=agent_name, deterministic=True)  # 追加智能体节点。
        add_edge(edges, "project:C3-43KG", "USES_AGENT", f"agent:{agent_name}")  # 连接项目与智能体。
    for group in sorted({case["group"] for case in cases}):  # 创建唯一工况组节点。
        add_node(nodes, f"group:{group}", "WindGroup", group=group)  # 追加工况组节点。
        add_edge(edges, "project:C3-43KG", "HAS_WIND_GROUP", f"group:{group}")  # 连接项目与工况组。
    for mode in modes:  # 创建 C3 模态节点。
        mode_id = f"mode:C3-M{mode['mode']:02d}"  # 建立稳定模态 ID。
        add_node(nodes, mode_id, "C3Mode", **mode)  # 追加模态节点。
        add_edge(edges, "run:C3-FT14", "HAS_MODE", mode_id)  # 连接模态运行与模态。
    traces: list[dict[str, Any]] = []  # 初始化 43 条智能体追踪。
    for case in cases:  # 遍历全部工况并重算 C3 状态。
        case_id = f"case:{case['c3_case_id']}"  # 建立 C3 工况节点 ID。
        response_id = f"response:{case['c3_case_id']}"  # 建立 C3 响应节点 ID。
        trace = make_trace(case, binding)  # 执行四智能体。
        traces.append(trace)  # 保存追踪记录。
        add_node(nodes, case_id, "C3WindCase", **case)  # 添加 C3 工况节点。
        add_node(nodes, response_id, "C3CaseResponse", state="NOT_MATERIALIZED", transferred_numeric_values=False)  # 添加空响应状态节点。
        add_node(nodes, trace["trace_id"], "AgentTrace", final_status=trace["final_status"], dispatch=trace["dispatch"])  # 添加追踪节点。
        add_node(nodes, f"legacy-result:{case['id']}", "LegacyResultPointer", source_model="Double-MCT", case_id=case["id"], use_as_c3_truth=False)  # 添加旧结果指针。
        add_edge(edges, "project:C3-43KG", "HAS_CASE", case_id)  # 连接项目与工况。
        add_edge(edges, case_id, "IN_GROUP", f"group:{case['group']}")  # 连接工况与分组。
        add_edge(edges, case_id, "EVALUATED_ON", "model:C3")  # 连接工况与 C3 模型。
        add_edge(edges, case_id, "HAS_RESPONSE_STATE", response_id)  # 连接工况与响应状态。
        add_edge(edges, case_id, "HAS_AGENT_TRACE", trace["trace_id"])  # 连接工况与追踪。
        add_edge(edges, f"legacy-result:{case['id']}", "PROVENANCE_ONLY", case_id, numerical_value_transfer=False)  # 切断旧数值迁移。
        previous_decision_id: str | None = None  # 初始化智能体链前驱。
        for step_number, step in enumerate(trace["steps"], start=1):  # 遍历四步决策。
            decision_id = f"decision:{case['c3_case_id']}:{step_number}"  # 建立决策节点 ID。
            add_node(nodes, decision_id, "AgentDecision", step=step_number, **step)  # 添加决策节点。
            add_edge(edges, trace["trace_id"], "HAS_STEP", decision_id, step=step_number)  # 连接追踪与决策。
            add_edge(edges, decision_id, "EXECUTED_BY", f"agent:{step['agent']}")  # 连接决策与智能体。
            if previous_decision_id is not None:  # 检查是否存在前驱步骤。
                add_edge(edges, previous_decision_id, "NEXT_STEP", decision_id)  # 连接相邻决策。
            previous_decision_id = decision_id  # 更新前驱步骤。
    graph = {"schema_version": "catwalk-c3-kg/v2", "nodes": nodes, "edges": edges, "traces": traces}  # 组装完整图谱。
    return graph  # 返回内存图谱。


def graph_summary(graph: dict[str, Any]) -> dict[str, Any]:  # 汇总图谱验收指标。
    node_counts = Counter(node["type"] for node in graph["nodes"])  # 统计节点类型。
    relation_counts = Counter(edge["relation"] for edge in graph["edges"])  # 统计关系类型。
    decisions = [node for node in graph["nodes"] if node["type"] == "AgentDecision"]  # 提取智能体决策。
    physics_counts = Counter(node["properties"]["decision"] for node in decisions if node["properties"]["agent"] == "PhysicsBoundaryAgent")  # 统计物理状态。
    warning_counts = Counter(node["properties"]["decision"] for node in decisions if node["properties"]["agent"] == "WarningPolicyAgent")  # 统计终态。
    return {  # 返回可序列化汇总。
        "schema_version": graph["schema_version"],  # 记录图谱版本。
        "node_count": len(graph["nodes"]),  # 记录节点总数。
        "edge_count": len(graph["edges"]),  # 记录边总数。
        "node_type_counts": dict(sorted(node_counts.items())),  # 输出稳定节点计数。
        "relation_counts": dict(sorted(relation_counts.items())),  # 输出稳定关系计数。
        "agent_decision_count": len(decisions),  # 记录 43×4 决策数。
        "physics_decision_counts": dict(sorted(physics_counts.items())),  # 输出物理状态计数。
        "warning_counts": dict(sorted(warning_counts.items())),  # 输出终态计数。
        "dispatch_true_count": sum(1 for trace in graph["traces"] if trace["dispatch"]),  # 统计派发真值。
        "case_response_not_materialized": node_counts["C3CaseResponse"],  # 统计未物化响应节点。
    }  # 完成汇总。


def emit_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:  # 输出稳定 UTF-8 CSV。
    with path.open("w", encoding="utf-8", newline="") as handle:  # 打开目标文件。
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")  # 固定列顺序并使用 Git 友好换行。
        writer.writeheader()  # 写入表头。
        writer.writerows(rows)  # 写入全部行。


def emit_outputs(graph: dict[str, Any]) -> dict[str, Any]:  # 将图谱物化为仓库产物。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建输出目录。
    (OUTPUT_DIR / "knowledge_graph_c3.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 输出完整 JSON 图谱。
    node_rows = [{"id": node["id"], "type": node["type"], "properties_json": json.dumps(node["properties"], ensure_ascii=False, sort_keys=True)} for node in graph["nodes"]]  # 扁平化节点。
    edge_rows = [{"id": edge["id"], "source": edge["source"], "relation": edge["relation"], "target": edge["target"], "properties_json": json.dumps(edge["properties"], ensure_ascii=False, sort_keys=True)} for edge in graph["edges"]]  # 扁平化边。
    trace_rows = [{"trace_id": trace["trace_id"], "case_id": trace["case_id"], "c3_case_id": trace["c3_case_id"], "physics_decision": trace["steps"][2]["decision"], "final_status": trace["final_status"], "dispatch": str(trace["dispatch"]).lower(), "trace_json": json.dumps(trace, ensure_ascii=False, sort_keys=True)} for trace in graph["traces"]]  # 扁平化追踪。
    emit_csv(OUTPUT_DIR / "knowledge_graph_c3_nodes.csv", node_rows, ["id", "type", "properties_json"])  # 输出节点表。
    emit_csv(OUTPUT_DIR / "knowledge_graph_c3_edges.csv", edge_rows, ["id", "source", "relation", "target", "properties_json"])  # 输出边表。
    emit_csv(OUTPUT_DIR / "c3_agent_traces_43.csv", trace_rows, ["trace_id", "case_id", "c3_case_id", "physics_decision", "final_status", "dispatch", "trace_json"])  # 输出 43 条追踪。
    summary = graph_summary(graph)  # 计算图谱汇总。
    (OUTPUT_DIR / "graph_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 输出图谱汇总。
    return summary  # 返回汇总供命令行显示。


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:  # 校验完整性和禁止迁移项。
    cases = load_cases()  # 载入输入工况用于比对。
    modes = load_modes()  # 载入输入模态用于比对。
    summary = graph_summary(graph)  # 计算当前图谱汇总。
    node_ids = {node["id"] for node in graph["nodes"]}  # 建立节点 ID 集合。
    missing_endpoints = [edge["id"] for edge in graph["edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids]  # 查找悬空边。
    checks = {  # 汇总所有确定性检查。
        "case_count_43": len(cases) == 43,  # 检查工况总数。
        "unique_case_ids_43": len({case["id"] for case in cases}) == 43,  # 检查工况唯一性。
        "mode_count_14": len(modes) == 14,  # 检查 C3 模态数。
        "agent_count_4": summary["node_type_counts"].get("Agent") == 4,  # 检查智能体数。
        "agent_decisions_172": summary["agent_decision_count"] == 172,  # 检查 43×4 决策。
        "responses_not_materialized_43": summary["case_response_not_materialized"] == 43,  # 检查响应状态数。
        "warning_not_armed_43": summary["warning_counts"].get("NOT_ARMED") == 43,  # 检查终态。
        "dispatch_true_zero": summary["dispatch_true_count"] == 0,  # 检查无派发。
        "nonstationary_reference_10": summary["physics_decision_counts"].get("REFERENCE_ONLY_NONSTATIONARY") == 10,  # 检查 C3 非平稳清单。
        "edge_endpoints_exist": not missing_endpoints,  # 检查所有边端点。
        "no_c3_numeric_response_metrics": all(node["properties"].get("state") == "NOT_MATERIALIZED" for node in graph["nodes"] if node["type"] == "C3CaseResponse"),  # 检查未伪造响应值。
    }  # 完成检查表。
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "missing_edge_ids": missing_endpoints, "summary": summary}  # 组装校验结果。
    return result  # 返回校验结果。


def find_case(case_id: str) -> dict[str, Any]:  # 按原始或 C3 ID 查找工况。
    for case in load_cases():  # 顺序扫描仅 43 行的小表。
        if case_id in (case["id"], case["c3_case_id"]):  # 同时接受两种 ID。
            return case  # 返回匹配工况。
    raise KeyError(f"Unknown case: {case_id}")  # 对未知工况给出明确错误。


def facts_for_case(case: dict[str, Any]) -> dict[str, Any]:  # 构造 Doubao 只读事实包。
    binding = read_json(ROOT / "model_binding.json")  # 读取 C3 模型事实。
    trace = make_trace(case, binding)  # 重算该工况四智能体追踪。
    modes = load_modes()  # 读取 14 阶模态事实。
    pairing_rows = load_rows(ROOT / "table41_c3_pairing.csv")  # 读取附件表 4-1 对照表。
    comparison_pairs = [row for row in pairing_rows if row.get("table41_target")]  # 只保留带目标名的对照行。
    return {  # 返回最小充分事实包。
        "case": case,  # 提供工况事实。
        "c3_model": {"model_id": binding["model_id"], "deck_sha256": binding["deck"]["sha256"], "solver_sha256": binding["solver"]["sha256"], "response_state": binding["response_state"]},  # 提供模型身份。
        "modal_frequencies_hz": binding["modal_receipt"]["frequencies_hz"],  # 提供原生频率。
        "comparison_pairs_not_aligned": comparison_pairs,  # 对照行含 NOT_ALIGNED，不是锁定配对。
        "agent_trace": trace,  # 提供四智能体追踪。
        "hard_facts": ["C3 43-case buffeting response is NOT_MATERIALIZED", "Double-MCT numerical response values are provenance only", "warning status is NOT_ARMED", "dispatch is false", "TA1/VS2 pairing is NOT_ALIGNED; C3 0.07267216 Hz is not attach TA1 0.0996"],  # 固定不可改写事实。
    }  # 完成事实包。


def offline_answer(facts: dict[str, Any], question: str) -> str:  # 在无 API 时生成可复查回答。
    case = facts["case"]  # 提取工况事实。
    physics = facts["agent_trace"]["steps"][2]["decision"]  # 提取物理决策。
    station_text = "可进入后续 C3 平稳抖振映射" if case["stationary"] else "仅作非平稳包络参考"  # 组织平稳性说明。
    return f"{case['name_cn']}（{case['id']}）的 U10 为 {case['U10_mps']:.1f} m/s，阵风为 {case['gust_mps'] if case['gust_mps'] is not None else '未给出'} m/s，风速平方比为 {case['wind_pressure_index']:.3f}。该工况{station_text}。四智能体物理状态为 {physics}，C3 响应仍是 NOT_MATERIALIZED，最终状态为 NOT_ARMED，dispatch=false。当前能引用 C3 的 deck 哈希和 14 阶原生模态，不能引用 Double-MCT 的位移、索力或安全比作为 C3 结果。问题：{question}"  # 返回完整离线回答。


def resolve_api_key() -> tuple[str | None, str | None]:  # 从支持的环境变量中选择 Key。
    for name in KEY_NAMES:  # 按明确优先级遍历。
        value = os.environ.get(name, "").strip()  # 读取并清理环境值。
        if value:  # 检查是否存在非空 Key。
            return value, name  # 返回 Key 与命中的变量名。
    return None, None  # 表示当前运行未注入 Key。


def call_doubao(facts: dict[str, Any], question: str) -> dict[str, Any]:  # 调用火山方舟 Chat API。
    api_key, key_name = resolve_api_key()  # 解析运行时 Key。
    if api_key is None:  # 检查 Key 是否存在。
        raise RuntimeError("No supported Doubao API key environment variable is set")  # 阻止无凭据的伪调用。
    base_url = os.environ.get("DOUBAO_BASE_URL", DEFAULT_BASE_URL).rstrip("/")  # 允许覆盖 Base URL。
    model = os.environ.get("DOUBAO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL  # 允许覆盖模型 ID。
    system = "你是 C3 猫道 43 工况知识图谱智能体。只依据给定 JSON 事实作答。必须保留 NOT_MATERIALIZED、NOT_ARMED、dispatch=false；不得把 Double-MCT 数值写成 C3 响应；风速平方比不是结构响应。用中文简洁回答并列出证据与缺口。"  # 固定系统约束。
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": f"问题：{question}\n事实包：{json.dumps(facts, ensure_ascii=False, sort_keys=True)}"}], "temperature": 0.1}  # 构造兼容请求体。
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")  # 将请求体编码为 UTF-8。
    request = urllib.request.Request(f"{base_url}/chat/completions", data=payload, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")  # 构造鉴权请求且不记录 Key。
    timeout = float(os.environ.get("DOUBAO_TIMEOUT_SECONDS", "60"))  # 读取可覆盖超时。
    with urllib.request.urlopen(request, timeout=timeout) as response:  # 发起 HTTPS 请求。
        result = json.loads(response.read().decode("utf-8"))  # 解析兼容响应。
    answer = result["choices"][0]["message"]["content"]  # 提取助手文本。
    return {"provider": "doubao", "mode": "live", "model": model, "key_env_name": key_name, "request_id": result.get("id"), "answer": answer}  # 返回不含 Key 的调用记录。


def run_ask(case_id: str, question: str, force_offline: bool, require_llm: bool) -> dict[str, Any]:  # 执行一次完整 Demo 问答。
    case = find_case(case_id)  # 查找目标工况。
    facts = facts_for_case(case)  # 构造结构化事实包。
    api_key, _ = resolve_api_key()  # 检查是否可调用 Doubao。
    if force_offline or api_key is None:  # 选择确定性离线路径。
        if require_llm:  # 检查是否明确要求真实模型。
            raise RuntimeError("--require-llm was set but no supported API key was found")  # 对配置缺失返回失败。
        response = {"provider": "deterministic", "mode": "offline", "model": None, "answer": offline_answer(facts, question)}  # 生成离线回答。
    else:  # 进入真实 Doubao 路径。
        try:  # 捕获远端错误并保留可运行 Demo。
            response = call_doubao(facts, question)  # 调用 Doubao。
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError, RuntimeError) as exc:  # 限定预期调用错误。
            if require_llm:  # 检查是否要求真实调用成功。
                raise  # 将错误交给 Actions 显示。
            response = {"provider": "deterministic", "mode": "offline_fallback", "model": None, "error_type": type(exc).__name__, "answer": offline_answer(facts, question)}  # 回退且不泄露凭据。
    return {"schema_version": "catwalk-c3-demo/v1", "question": question, "case_id": case["id"], "facts": facts, "response": response}  # 返回完整 Demo 记录。


def write_result(path_text: str | None, result: dict[str, Any]) -> None:  # 输出问答或校验结果。
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"  # 生成稳定 JSON 文本。
    if path_text:  # 检查是否指定输出文件。
        path = Path(path_text)  # 解析用户路径。
        path.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录。
        path.write_text(rendered, encoding="utf-8")  # 写入 UTF-8 文件。
    sys.stdout.write(rendered)  # 同时输出到标准输出。


def build_parser() -> argparse.ArgumentParser:  # 定义命令行接口。
    parser = argparse.ArgumentParser(description="C3 × 43-case knowledge-graph agent")  # 创建主解析器。
    subparsers = parser.add_subparsers(dest="command", required=True)  # 要求显式子命令。
    subparsers.add_parser("build", help="build deterministic graph outputs")  # 注册构图命令。
    subparsers.add_parser("validate", help="validate graph integrity and boundaries")  # 注册校验命令。
    ask = subparsers.add_parser("ask", help="query one C3 wind case")  # 注册问答命令。
    ask.add_argument("--case", required=True, dest="case_id", help="scenario id or C3 case id")  # 接收工况 ID。
    ask.add_argument("--question", required=True, help="question for the agent")  # 接收自然语言问题。
    ask.add_argument("--offline", action="store_true", help="force deterministic offline response")  # 允许强制离线。
    ask.add_argument("--require-llm", action="store_true", help="fail unless the Doubao call succeeds")  # 允许验收真实调用。
    ask.add_argument("--output", help="optional JSON output path")  # 允许保存结果。
    return parser  # 返回解析器。


def main() -> int:  # 执行命令行入口。
    args = build_parser().parse_args()  # 解析参数。
    if args.command == "build":  # 处理构图命令。
        write_result(None, emit_outputs(build_graph()))  # 构图并输出汇总。
        return 0  # 返回成功。
    if args.command == "validate":  # 处理校验命令。
        graph = build_graph()  # 在内存中重建图谱。
        result = validate_graph(graph)  # 执行完整校验。
        write_result(str(OUTPUT_DIR / "validation.json"), result)  # 保存并显示校验结果。
        return 0 if result["status"] == "PASS" else 1  # 将失败传播给 CI。
    result = run_ask(args.case_id, args.question, args.offline, args.require_llm)  # 执行问答命令。
    write_result(args.output, result)  # 保存并显示 Demo。
    return 0  # 返回成功。


if __name__ == "__main__":  # 仅在直接执行脚本时运行入口。
    raise SystemExit(main())  # 将返回码交给操作系统。
