from __future__ import annotations  # 允许现代类型注解且保持 Python 3.10 兼容。
import argparse  # 解析构图、校验和问答命令。
import csv  # 读取工况与模态表并输出扁平图谱表。
import hashlib  # 校验迁入权威文件与源冻结哈希一致。
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
SOURCE_AUTHORITY_SHA256 = "df10da1c759cea9e93c065d9456e583a1944b7b3eb1a730ea048f1821dddc5b7"  # 锁定源 AUTHORITY.json 哈希。
SOURCE_MATRIX_SHA256 = "12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f"  # 锁定源 43 工况矩阵哈希。
MIGRATED_MATRIX_SHA256 = "95fe97e73b3bec61124147b9c29a4ed3abf6217537e8bf082eca707426f3625a"  # 锁定 CRLF 转 LF 后的迁入矩阵哈希。


def read_json(path: Path) -> dict[str, Any]:  # 读取 UTF-8 JSON 配置。
    return json.loads(path.read_text(encoding="utf-8"))  # 返回结构化字典。


def load_rows(path: Path) -> list[dict[str, str]]:  # 读取 UTF-8 CSV 并保留列名。
    with path.open("r", encoding="utf-8", newline="") as handle:  # 使用 newline 规则避免跨平台空行。
        return list(csv.DictReader(handle))  # 将每一行转换为字典。


def file_sha256(path: Path) -> str:  # 计算冻结文件的 SHA-256。
    return hashlib.sha256(path.read_bytes()).hexdigest()  # 对原始字节计算哈希以避免文本归一化歧义。


def load_source_authority() -> list[dict[str, str]]:  # 读取完整 37 列 Double-MCT 权威工况矩阵。
    return load_rows(ROOT / "authority" / "I08_GITHUB_43_CASE_MATRIX.csv")  # 返回源冻结顺序与全部风场配方字段。


def load_case_migration() -> list[dict[str, str]]:  # 读取逐工况源到 C3 迁移矩阵。
    return load_rows(ROOT / "case_migration_matrix.csv")  # 返回源顺序、C3 顺序和分类处置。


def load_source_inventory() -> dict[str, Any]:  # 读取 36 项源资产逐文件处置清单。
    return read_json(ROOT / "source_asset_inventory.json")  # 返回哈希、大小和迁移处置。


def load_agent_policy() -> dict[str, Any]:  # 读取四智能体迁移后的政策合同。
    return read_json(ROOT / "agent_policy_c3.json")  # 返回每个智能体的输入、决策和禁止声明。


def load_cases() -> list[dict[str, Any]]:  # 读取并类型化 43 工况。
    cases: list[dict[str, Any]] = []  # 初始化稳定顺序的工况列表。
    source_by_id = {row["github_scenario_id"]: row for row in load_source_authority()}  # 按权威工况 ID 建立完整源记录索引。
    migration_by_id = {row["case_id"]: row for row in load_case_migration()}  # 按工况 ID 建立分类迁移索引。
    for raw in load_rows(ROOT / "cases_43.csv"):  # 按仓库清单顺序遍历。
        case: dict[str, Any] = dict(raw)  # 复制原始字段以保留数据谱系。
        source = source_by_id[raw["id"]]  # 取得源冻结权威记录。
        migration = migration_by_id[raw["id"]]  # 取得逐工况迁移处置。
        case["n"] = int(raw["n"])  # 保留兼容字段并将 C3 序号转换为整数。
        case["c3_order"] = int(raw["n"])  # 明确该序号仅为 C3 展示顺序。
        case["source_case_index"] = int(source["case_index"])  # 恢复 Double-MCT 权威源顺序。
        case["source_i08_case_id"] = source["i08_case_id"]  # 绑定原 I08 工况标识。
        case["source_stationarity"] = source["stationarity"]  # 保留源平稳性判断而不被 C3 分类覆盖。
        case["source_name_cn"] = source["name_cn"]  # 保留源权威中文名称。
        case["classification_disposition"] = migration["classification_disposition"]  # 记录 C3 分类是否发生变化。
        case["U10_mps"] = float(raw["U10_mps"])  # 将十米风速转换为浮点数。
        case["gust_mps"] = float(raw["gust_mps"]) if raw["gust_mps"] else None  # 保留缺失阵风为 null。
        case["stationary"] = raw["stationary"].strip().lower() == "true"  # 将 C3 平稳求解适用性标志转换为布尔值。
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
        "facts": {"case_id": case["id"], "source_case_index": case["source_case_index"], "c3_order": case["c3_order"], "source_i08_case_id": case["source_i08_case_id"], "grade": case["grade"]},  # 分开绑定源顺序与 C3 顺序。
        "decision": "C3_CASE_AUTHORITY_CONFIRMED",  # 输出 C3 工况权威状态。
    }  # 完成权威来源决策。
    solver = {  # 构造求解证据决策。
        "agent": "SolverEvidenceAgent",  # 记录执行智能体。
        "status": "MODAL_EVIDENCE_ONLY",  # 模态证据存在但工况响应不存在。
        "facts": {"deck_sha256": binding["deck"]["sha256"], "modal_modes": binding["modal_receipt"]["requested_modes"], "case_response": case["c3_response_state"]},  # 绑定模型证据。
        "decision": "C3_MODAL_EVIDENCE_BOUND_CASE_RESPONSE_NOT_MATERIALIZED",  # 输出响应证据状态。
    }  # 完成求解证据决策。
    physics_decision = "AWAITING_C3_CASE_RESPONSE" if case["stationary"] else "REFERENCE_ONLY_C3_ENVELOPE"  # 根据 C3 适用性选择物理处置而不改写源平稳性。
    physics = {  # 构造物理边界决策。
        "agent": "PhysicsBoundaryAgent",  # 记录执行智能体。
        "status": physics_decision,  # 使用确定性物理状态。
        "facts": {"c3_stationary_eligible": case["stationary"], "source_stationarity": case["source_stationarity"], "classification_disposition": case["classification_disposition"], "c3_layer": case["c3_layer"], "claim": case["c3_claim"], "legacy_value_transfer": False},  # 同时记录源分类与 C3 处置。
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
    source_authority = load_source_authority()  # 载入完整源权威工况矩阵。
    source_authority_by_id = {row["github_scenario_id"]: row for row in source_authority}  # 按工况 ID 索引源权威记录。
    authority_receipt = read_json(ROOT / "authority" / "I08_AUTHORITY.json")  # 载入权威矩阵来源收据。
    source_inventory = load_source_inventory()  # 载入源包 36 项资产清单。
    legacy_master_asset = next(asset for asset in source_inventory["assets"] if asset["path"] == "results/I08_43CASE_MASTER.csv")  # 定位旧 43 工况主结果表哈希。
    migration_rules = load_rows(ROOT / "wmct_to_c3_mapping.csv")  # 载入实体级迁移规则。
    agent_policy = load_agent_policy()  # 载入四智能体政策合同。
    policy_by_name = {row["name"]: row for row in agent_policy["agents"]}  # 按智能体名称索引政策。
    nodes: list[dict[str, Any]] = []  # 初始化节点列表。
    edges: list[dict[str, Any]] = []  # 初始化边列表。
    add_node(nodes, "project:C3-43KG", "Project", name="C3 × 43 工况知识图谱智能体", schema="catwalk-c3-kg/v2")  # 添加项目节点。
    add_node(nodes, "model:C3", "C3Model", **binding)  # 添加 C3 模型节点。
    add_node(nodes, "artifact:C3-deck", "EvidenceArtifact", **binding["deck"])  # 添加 deck 证据节点。
    add_node(nodes, "artifact:C3-solver", "EvidenceArtifact", **binding["solver"])  # 添加求解器证据节点。
    add_node(nodes, "run:C3-FT14", "C3ModalRun", **binding["modal_receipt"])  # 添加原生模态运行节点。
    add_node(nodes, "legacy:I08-double-mct", "LegacyResultSet", **lineage)  # 添加旧模型结果集谱系节点。
    add_node(nodes, "authority:I08-GITHUB43", "SourceAuthority", receipt=authority_receipt, source_matrix_sha256=SOURCE_MATRIX_SHA256, migrated_matrix_sha256=MIGRATED_MATRIX_SHA256, newline_normalization="CRLF_TO_LF", use_as_c3_load_approval=False, case_count=len(source_authority))  # 添加源权威矩阵节点并声明仅作谱系。
    add_node(nodes, "evidence-source:github-extreme-library", "EvidenceSource", repository=authority_receipt["repository"], commit=authority_receipt["commit"], source_path=authority_receipt["source_path"], source_blob_sha1=authority_receipt["source_blob_sha1_from_github_api"])  # 添加 43 事件库的上游证据源。
    add_node(nodes, "event-library:github43", "GitHubEventLibrary", ordered_case_count=43, authority_status=authority_receipt["authority_status"])  # 添加冻结 43 事件库节点。
    add_node(nodes, "method:I08-Kaimal-Davenport", "LegacySpectralMethod", wind_spectrum="Kaimal", coherence_model="Davenport_exp", use_as_c3_approved_load=False)  # 添加旧风场方法节点且不批准为 C3 输入。
    add_node(nodes, "boundary:C3-native-response", "PhysicsBoundary", c3_wind_load_state="NOT_MATERIALIZED", c3_response_state="NOT_MATERIALIZED", legacy_numeric_value_transfer=False)  # 添加 C3 原生响应物理边界。
    add_node(nodes, "gate:C3-model-migration", "ValidationGate", scope="MODEL_MIGRATION_ONLY", status="PASS_WHEN_ACCEPTANCE_CHECKS_PASS", response_execution_enabled=False)  # 添加独立模型迁移门。
    add_node(nodes, "policy:warning-not-armed", "WarningPolicy", **agent_policy["global_output_contract"])  # 添加迁移后的预警输出合同。
    add_edge(edges, "project:C3-43KG", "BINDS_MODEL", "model:C3")  # 连接项目与 C3 模型。
    add_edge(edges, "model:C3", "EVIDENCED_BY", "artifact:C3-deck")  # 连接模型与 deck。
    add_edge(edges, "model:C3", "SOLVED_BY", "artifact:C3-solver")  # 连接模型与求解器。
    add_edge(edges, "model:C3", "HAS_MODAL_RUN", "run:C3-FT14")  # 连接模型与模态运行。
    add_edge(edges, "legacy:I08-double-mct", "PROVENANCE_ONLY_FOR", "project:C3-43KG", numerical_value_transfer=False)  # 明确旧结果仅为谱系。
    add_edge(edges, "project:C3-43KG", "DERIVES_CASES_FROM", "authority:I08-GITHUB43")  # 连接 C3 项目与完整源权威矩阵。
    add_edge(edges, "event-library:github43", "EVIDENCED_BY", "evidence-source:github-extreme-library")  # 连接事件库与上游证据源。
    add_edge(edges, "authority:I08-GITHUB43", "MATERIALIZES", "event-library:github43")  # 连接权威矩阵与事件库。
    add_edge(edges, "legacy:I08-double-mct", "USED_SPECTRAL_METHOD", "method:I08-Kaimal-Davenport")  # 连接旧结果集与旧风场方法。
    add_edge(edges, "project:C3-43KG", "SUBJECT_TO", "boundary:C3-native-response")  # 连接项目与物理边界。
    add_edge(edges, "project:C3-43KG", "SUBJECT_TO", "gate:C3-model-migration")  # 连接项目与模型迁移门。
    add_edge(edges, "project:C3-43KG", "SUBJECT_TO", "policy:warning-not-armed")  # 连接项目与预警政策。
    for limitation_number, limitation in enumerate(agent_policy["carried_source_limitations"], start=1):  # 迁入三个源限制语义。
        limitation_id = f"limitation:{limitation_number:02d}"  # 建立稳定限制节点 ID。
        add_node(nodes, limitation_id, "Limitation", statement=limitation, applies_to_c3_as="PROVENANCE_BOUNDARY")  # 添加限制节点。
        add_edge(edges, "legacy:I08-double-mct", "RESTRICTED_BY", limitation_id)  # 连接旧结果集与限制。
        add_edge(edges, "project:C3-43KG", "INHERITS_BOUNDARY", limitation_id)  # 连接 C3 项目与继承边界。
    for agent_name in AGENTS:  # 创建四智能体节点。
        add_node(nodes, f"agent:{agent_name}", "Agent", name=agent_name, deterministic=True, policy=policy_by_name[agent_name])  # 追加带迁移政策合同的智能体节点。
        add_edge(edges, "project:C3-43KG", "USES_AGENT", f"agent:{agent_name}")  # 连接项目与智能体。
    for asset_number, asset in enumerate(source_inventory["assets"], start=1):  # 逐项登记源包全部资产。
        asset_id = f"source-asset:I08:{asset_number:02d}"  # 使用稳定序号建立源资产节点 ID。
        add_node(nodes, asset_id, "SourceAsset", **asset)  # 添加带哈希与处置的源资产节点。
        add_edge(edges, "legacy:I08-double-mct", "HAS_SOURCE_ASSET", asset_id, disposition=asset["disposition"], numerical_value_transfer=False)  # 连接源结果集与逐文件资产。
    for rule_number, rule in enumerate(migration_rules, start=1):  # 逐项登记实体迁移规则。
        rule_id = f"migration-rule:{rule_number:02d}"  # 建立稳定迁移规则节点 ID。
        add_node(nodes, rule_id, "MigrationRule", **rule)  # 添加迁移规则节点。
        add_edge(edges, "project:C3-43KG", "USES_MIGRATION_RULE", rule_id)  # 连接项目与迁移规则。
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
        authority_record_id = f"authority-record:{case['id']}"  # 建立源权威记录节点 ID。
        github_event_id = f"github-event:{case['id']}"  # 建立源 GitHub 事件节点 ID。
        evidence_bundle_id = f"evidence-bundle:{case['c3_case_id']}"  # 建立 C3 迁移证据包节点 ID。
        trace = make_trace(case, binding)  # 执行四智能体。
        traces.append(trace)  # 保存追踪记录。
        add_node(nodes, case_id, "C3WindCase", **case)  # 添加 C3 工况节点。
        add_node(nodes, authority_record_id, "SourceAuthorityRecord", **source_authority_by_id[case["id"]])  # 添加完整 37 列源权威记录。
        add_node(nodes, github_event_id, "GitHubEvent", scenario_id=case["id"], source_case_index=case["source_case_index"], source_stationarity=case["source_stationarity"])  # 添加源事件语义节点。
        add_node(nodes, evidence_bundle_id, "ResultEvidenceBundle", scope="C3_MODEL_MIGRATION", authority_bound=True, modal_receipt_bound=True, c3_response_state="NOT_MATERIALIZED", numerical_response_metrics=False)  # 添加不含响应数值的迁移证据包。
        add_node(nodes, response_id, "C3CaseResponse", state="NOT_MATERIALIZED", transferred_numeric_values=False)  # 添加空响应状态节点。
        add_node(nodes, trace["trace_id"], "AgentTrace", final_status=trace["final_status"], dispatch=trace["dispatch"])  # 添加追踪节点。
        add_node(nodes, f"legacy-result:{case['id']}", "LegacyResultPointer", source_model="Double-MCT", source_commit=lineage["source_commit"], source_path=f"{lineage['source_package']}/results/I08_43CASE_MASTER.csv", source_file_sha256=legacy_master_asset["sha256"], source_i08_case_id=case["source_i08_case_id"], source_row_key=case["source_i08_case_id"], case_id=case["id"], use_as_c3_truth=False)  # 添加可定位但不可取值的旧结果指针。
        add_edge(edges, "project:C3-43KG", "HAS_CASE", case_id)  # 连接项目与工况。
        add_edge(edges, "authority:I08-GITHUB43", "CONTAINS_AUTHORITY_RECORD", authority_record_id)  # 连接权威矩阵与源记录。
        add_edge(edges, case_id, "DERIVED_FROM_AUTHORITY", authority_record_id, source_case_index=case["source_case_index"], c3_order=case["c3_order"])  # 显式记录源顺序与 C3 顺序。
        add_edge(edges, "event-library:github43", "CONTAINS_EVENT", github_event_id)  # 连接事件库与源事件。
        add_edge(edges, github_event_id, "MAPPED_TO", case_id, classification_disposition=case["classification_disposition"])  # 连接源事件与 C3 工况。
        add_edge(edges, case_id, "EVIDENCED_BY", evidence_bundle_id)  # 连接工况与迁移证据包。
        add_edge(edges, evidence_bundle_id, "BINDS_AUTHORITY", authority_record_id)  # 连接证据包与源权威记录。
        add_edge(edges, evidence_bundle_id, "BINDS_MODAL_RUN", "run:C3-FT14")  # 连接证据包与 C3 原生模态收据。
        add_edge(edges, case_id, "IN_GROUP", f"group:{case['group']}")  # 连接工况与分组。
        add_edge(edges, case_id, "TARGETS_MODEL", "model:C3", response_state="NOT_MATERIALIZED")  # 连接工况与目标 C3 模型且不声称已求解。
        add_edge(edges, case_id, "HAS_RESPONSE_STATE", response_id)  # 连接工况与响应状态。
        add_edge(edges, case_id, "HAS_AGENT_TRACE", trace["trace_id"])  # 连接工况与追踪。
        add_edge(edges, f"legacy-result:{case['id']}", "PART_OF_LEGACY_RESULT_SET", "legacy:I08-double-mct")  # 将逐案旧结果指针接回旧结果集。
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
    response_nodes = [node for node in graph["nodes"] if node["type"] == "C3CaseResponse"]  # 提取 C3 响应状态节点。
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
        "case_response_not_materialized": sum(node["properties"].get("state") == "NOT_MATERIALIZED" for node in response_nodes),  # 仅统计状态确为未物化的响应节点。
    }  # 完成汇总。


def migration_acceptance(graph: dict[str, Any]) -> dict[str, Any]:  # 验收源资产到 C3 模型语义的完整迁移。
    cases = load_cases()  # 读取类型化 C3 工况。
    source_rows = load_source_authority()  # 读取 37 列源权威矩阵。
    migration_rows = load_case_migration()  # 读取逐工况迁移处置。
    inventory = load_source_inventory()  # 读取 36 项源资产清单。
    policy = load_agent_policy()  # 读取四智能体政策合同。
    binding = read_json(ROOT / "model_binding.json")  # 读取 C3 模型绑定。
    modes = load_modes()  # 读取 C3 14 阶模态。
    pairings = load_rows(ROOT / "table41_c3_pairing.csv")  # 读取模态配对状态。
    rules = load_rows(ROOT / "wmct_to_c3_mapping.csv")  # 读取实体级迁移规则。
    source_by_id = {row["github_scenario_id"]: row for row in source_rows}  # 建立源工况索引。
    case_by_id = {case["id"]: case for case in cases}  # 建立 C3 工况索引。
    inventory_by_path = {asset["path"]: asset for asset in inventory["assets"]}  # 建立源资产索引。
    node_ids = [node["id"] for node in graph["nodes"]]  # 收集全部节点 ID。
    edge_ids = [edge["id"] for edge in graph["edges"]]  # 收集全部边 ID。
    node_counts = Counter(node["type"] for node in graph["nodes"])  # 统计节点类型。
    relation_counts = Counter(edge["relation"] for edge in graph["edges"])  # 统计关系类型。
    response_nodes = [node for node in graph["nodes"] if node["type"] == "C3CaseResponse"]  # 提取 C3 响应节点。
    case_nodes = [node for node in graph["nodes"] if node["type"] == "C3WindCase"]  # 提取 C3 工况节点。
    authority_record_nodes = [node for node in graph["nodes"] if node["type"] == "SourceAuthorityRecord"]  # 提取完整源权威记录节点。
    graph_mode_nodes = [node for node in graph["nodes"] if node["type"] == "C3Mode"]  # 提取图谱中的 C3 模态节点。
    legacy_pointers = [node for node in graph["nodes"] if node["type"] == "LegacyResultPointer"]  # 提取旧结果指针。
    provenance_edges = [edge for edge in graph["edges"] if edge["relation"] == "PROVENANCE_ONLY"]  # 提取旧结果谱系边。
    has_case_edges = [edge for edge in graph["edges"] if edge["relation"] == "HAS_CASE"]  # 提取项目到工况的包含边。
    source_reference_count = sum(row["stationarity"] == "reference_only" for row in source_rows)  # 统计源参考工况。
    c3_envelope_count = sum(not case["stationary"] for case in cases)  # 统计 C3 包络参考工况。
    reclassified_ids = sorted(row["case_id"] for row in migration_rows if row["classification_disposition"] == "C3_ENVELOPE_ONLY_RECLASSIFIED")  # 提取 C3 重分类工况。
    expected_reclassified_ids = ["cape_denison_katabatic", "piteraq_tasiilaq"]  # 锁定两项显式 C3 重分类。
    source_values_match = all(float(source_by_id[case_id]["U10_sustained_ms"]) == case_by_id[case_id]["U10_mps"] and (float(source_by_id[case_id]["gust3s_ms"]) if source_by_id[case_id]["gust3s_ms"] else None) == case_by_id[case_id]["gust_mps"] and source_by_id[case_id]["confidence"] == case_by_id[case_id]["grade"] for case_id in source_by_id)  # 校验 43 案风速、阵风和等级不失真。
    pointer_required = {"source_commit", "source_path", "source_file_sha256", "source_i08_case_id", "source_row_key", "use_as_c3_truth"}  # 定义旧结果指针必需字段。
    response_allowed = {"state", "transferred_numeric_values"}  # 定义 C3 空响应节点字段白名单。
    trace_order_ok = all([step["agent"] for step in trace["steps"]] == list(AGENTS) and len(trace["steps"]) == 4 for trace in graph["traces"])  # 校验每案固定四步顺序。
    modal_frequencies_match = [mode["frequency_hz"] for mode in modes] == binding["modal_receipt"]["frequencies_hz"]  # 校验 CSV 与模型收据频率逐项一致。
    graph_modes_match = [node["properties"] for node in sorted(graph_mode_nodes, key=lambda item: item["properties"]["mode"])] == modes  # 校验图谱模态节点与冻结 CSV 完全一致。
    authority_records_match = {node["properties"]["github_scenario_id"]: node["properties"] for node in authority_record_nodes} == source_by_id  # 校验图谱内 43 条记录保留全部 37 列原值。
    expected_case_node_ids = {f"case:{case['c3_case_id']}" for case in cases}  # 建立全部 C3 工况节点 ID 集合。
    has_case_targets_match = len(has_case_edges) == 43 and {edge["target"] for edge in has_case_edges} == expected_case_node_ids and all(edge["source"] == "project:C3-43KG" for edge in has_case_edges)  # 校验每个工况恰由项目包含一次。
    global_numeric_transfer_blocked = all(edge["properties"].get("numerical_value_transfer") is not True for edge in graph["edges"])  # 禁止任一图谱边开启旧数值迁移。
    pairing_unverified = all(row["mapping_status"] in {"UNRESOLVED", "NOT_ALIGNED"} for row in pairings)  # 禁止把未绑定证据的比较候选写成已验收配对。
    checks = {  # 组装模型迁移验收检查。
        "source_authority_receipt_hash_exact": file_sha256(ROOT / "authority" / "I08_AUTHORITY.json") == SOURCE_AUTHORITY_SHA256,  # 校验权威收据原字节哈希。
        "source_matrix_normalized_hash_locked": file_sha256(ROOT / "authority" / "I08_GITHUB_43_CASE_MATRIX.csv") == MIGRATED_MATRIX_SHA256,  # 校验迁入矩阵归一化字节哈希。
        "source_matrix_original_hash_recorded": inventory_by_path["authority/I08_GITHUB_43_CASE_MATRIX.csv"]["sha256"] == SOURCE_MATRIX_SHA256,  # 校验源原始哈希仍被记录。
        "authority_copy_dispositions_exact": inventory_by_path["authority/AUTHORITY.json"]["disposition"] == "VENDORED_EXACT_AUTHORITY" and inventory_by_path["authority/I08_GITHUB_43_CASE_MATRIX.csv"]["disposition"] == "VENDORED_NORMALIZED_AUTHORITY",  # 校验权威收据为逐字节副本而矩阵明确记录换行归一化。
        "source_authority_43_by_37": len(source_rows) == 43 and len(source_rows[0]) == 37,  # 校验完整 43×37 权威矩阵。
        "source_and_c3_case_ids_exact": set(source_by_id) == set(case_by_id) and len(case_by_id) == 43,  # 校验 43 工况身份集合完全一致。
        "source_order_preserved": sorted(case["source_case_index"] for case in cases) == list(range(1, 44)) and all(case_by_id[row["github_scenario_id"]]["source_case_index"] == int(row["case_index"]) for row in source_rows),  # 校验源顺序未被 C3 顺序覆盖。
        "source_values_match_43": source_values_match,  # 校验 U10、阵风和等级不失真。
        "source_stationarity_35_8": len(source_rows) - source_reference_count == 35 and source_reference_count == 8,  # 校验源分类为 35 加 8。
        "c3_policy_33_10": len(cases) - c3_envelope_count == 33 and c3_envelope_count == 10,  # 校验 C3 策略为 33 加 10。
        "c3_reclassification_exact_two": reclassified_ids == expected_reclassified_ids,  # 校验两项重分类显式可追溯。
        "source_asset_inventory_36": inventory["asset_count"] == 36 and len(inventory["assets"]) == 36 and inventory["source_total_bytes"] == 6196831,  # 校验源包逐文件清单与总字节数。
        "source_assets_unique_and_accounted": len(inventory_by_path) == 36 and inventory["all_assets_accounted"] and all(asset["disposition"] and asset["target"] for asset in inventory["assets"]),  # 校验零未映射源资产。
        "source_assets_zero_numeric_transfer": not inventory["numeric_value_transfer"] and all(not asset["numeric_value_transfer"] for asset in inventory["assets"]),  # 校验资产级旧数值迁移全部禁止。
        "migration_rules_12": len(rules) == 12,  # 校验十二项实体迁移规则。
        "agent_policy_4": policy["source_agent_count"] == 4 and [row["name"] for row in policy["agents"]] == list(AGENTS),  # 校验四智能体政策合同。
        "node_ids_unique": len(node_ids) == len(set(node_ids)),  # 校验节点 ID 唯一。
        "edge_ids_unique": len(edge_ids) == len(set(edge_ids)),  # 校验边 ID 唯一。
        "source_asset_nodes_36": node_counts["SourceAsset"] == 36 and relation_counts["HAS_SOURCE_ASSET"] == 36,  # 校验 36 项源资产进入图谱。
        "source_authority_records_43": node_counts["SourceAuthorityRecord"] == 43 and relation_counts["DERIVED_FROM_AUTHORITY"] == 43,  # 校验 43 条完整权威记录进入图谱。
        "source_authority_record_values_exact": authority_records_match,  # 校验完整 37 列权威值未在图谱中被压缩或改写。
        "github_events_43": node_counts["GitHubEvent"] == 43 and relation_counts["MAPPED_TO"] == 43,  # 校验源事件到 C3 工况一对一映射。
        "evidence_bundles_43": node_counts["ResultEvidenceBundle"] == 43 and relation_counts["BINDS_MODAL_RUN"] == 43,  # 校验每案迁移证据包绑定 C3 模态收据。
        "c3_case_nodes_43": len(case_nodes) == 43 and {node["id"] for node in case_nodes} == expected_case_node_ids,  # 校验 C3 工况节点集合精确。
        "has_case_43": relation_counts["HAS_CASE"] == 43 and has_case_targets_match,  # 校验项目一对一包含全部 43 工况。
        "targets_model_43": relation_counts["TARGETS_MODEL"] == 43 and relation_counts["EVALUATED_ON"] == 0,  # 校验只声明目标模型而不声称已求解。
        "trace_order_43_by_4": len(graph["traces"]) == 43 and trace_order_ok,  # 校验 43 条四步智能体链。
        "responses_strictly_empty_43": len(response_nodes) == 43 and all(set(node["properties"]) == response_allowed and node["properties"]["state"] == "NOT_MATERIALIZED" and not node["properties"]["transferred_numeric_values"] for node in response_nodes),  # 校验空响应字段白名单并阻止伪数值。
        "legacy_pointers_complete_43": len(legacy_pointers) == 43 and all(pointer_required.issubset(node["properties"]) and node["properties"]["use_as_c3_truth"] is False for node in legacy_pointers),  # 校验逐案旧结果指针可定位且不可作 C3 真值。
        "legacy_pointers_linked_43": relation_counts["PART_OF_LEGACY_RESULT_SET"] == 43 and len(provenance_edges) == 43 and all(edge["properties"].get("numerical_value_transfer") is False for edge in provenance_edges),  # 校验旧结果谱系链完整且禁值传递。
        "global_numeric_transfer_blocked": global_numeric_transfer_blocked,  # 校验全图没有边允许旧响应数值进入 C3。
        "modal_receipt_matches_csv_14": len(modes) == 14 and modal_frequencies_match,  # 校验十四阶频率跨文件一致。
        "graph_modes_match_csv_14": len(graph_mode_nodes) == 14 and graph_modes_match,  # 校验图谱内十四阶模态没有被篡改。
        "mode_pairings_not_accepted": len(pairings) == 14 and pairing_unverified,  # 校验 Table4-1 比较候选明确未对齐且未验收。
        "c3_binding_identity_locked": binding["deck"]["sha256"] == "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86" and binding["solver"]["sha256"] == "b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e" and binding["modal_receipt"]["nodes"] == 91415 and binding["modal_receipt"]["elements"] == 172998 and binding["modal_receipt"]["active_equations"] == 439122,  # 校验 C3 模型与求解器身份。
    }  # 完成检查表。
    return {"schema_version": "catwalk-c3-model-migration-acceptance/v1", "scope": "MODEL_MIGRATION_ONLY", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "source_snapshot": {"commit": inventory["source_commit"], "asset_count": inventory["asset_count"], "bytes": inventory["source_total_bytes"], "graph_nodes": 2520, "graph_edges": 2953, "excluded_legacy_metric_observations": 2064}, "c3_snapshot": {"model_id": binding["model_id"], "modal_modes": len(modes), "case_count": len(cases), "response_state": binding["response_state"]}, "reclassified_case_ids": reclassified_ids, "excluded_from_c3_truth": binding["not_transferred_as_c3_truth"]}  # 返回完整迁移验收收据。


def emit_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:  # 输出稳定 UTF-8 CSV。
    with path.open("w", encoding="utf-8", newline="") as handle:  # 打开目标文件。
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")  # 固定列顺序并使用 Git 友好换行。
        writer.writeheader()  # 写入表头。
        writer.writerows(rows)  # 写入全部行。


def emit_json(path: Path, payload: dict[str, Any]) -> None:  # 输出稳定格式的 UTF-8 JSON。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 固定缩进、结尾换行与字符编码。


def emit_outputs(graph: dict[str, Any]) -> dict[str, Any]:  # 将图谱物化为仓库产物。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建输出目录。
    emit_json(OUTPUT_DIR / "knowledge_graph_c3.json", graph)  # 输出完整 JSON 图谱。
    node_rows = [{"id": node["id"], "type": node["type"], "properties_json": json.dumps(node["properties"], ensure_ascii=False, sort_keys=True)} for node in graph["nodes"]]  # 扁平化节点。
    edge_rows = [{"id": edge["id"], "source": edge["source"], "relation": edge["relation"], "target": edge["target"], "properties_json": json.dumps(edge["properties"], ensure_ascii=False, sort_keys=True)} for edge in graph["edges"]]  # 扁平化边。
    trace_rows = [{"trace_id": trace["trace_id"], "case_id": trace["case_id"], "c3_case_id": trace["c3_case_id"], "physics_decision": trace["steps"][2]["decision"], "final_status": trace["final_status"], "dispatch": str(trace["dispatch"]).lower(), "trace_json": json.dumps(trace, ensure_ascii=False, sort_keys=True)} for trace in graph["traces"]]  # 扁平化追踪。
    emit_csv(OUTPUT_DIR / "knowledge_graph_c3_nodes.csv", node_rows, ["id", "type", "properties_json"])  # 输出节点表。
    emit_csv(OUTPUT_DIR / "knowledge_graph_c3_edges.csv", edge_rows, ["id", "source", "relation", "target", "properties_json"])  # 输出边表。
    emit_csv(OUTPUT_DIR / "c3_agent_traces_43.csv", trace_rows, ["trace_id", "case_id", "c3_case_id", "physics_decision", "final_status", "dispatch", "trace_json"])  # 输出 43 条追踪。
    summary = graph_summary(graph)  # 计算图谱汇总。
    emit_json(OUTPUT_DIR / "graph_summary.json", summary)  # 输出图谱汇总。
    emit_json(OUTPUT_DIR / "migration_acceptance.json", migration_acceptance(graph))  # 输出模型迁移独立验收收据。
    return summary  # 返回汇总供命令行显示。


def emit_generated_sha_manifest() -> dict[str, Any]:  # 为模型迁移核心生成物建立可复查哈希账本。
    artifact_names = ("c3_agent_traces_43.csv", "graph_summary.json", "knowledge_graph_c3.json", "knowledge_graph_c3_edges.csv", "knowledge_graph_c3_nodes.csv", "migration_acceptance.json", "validation.json")  # 固定纳入账本且排除可变 Demo 文件。
    missing = [name for name in artifact_names if not (OUTPUT_DIR / name).is_file()]  # 查找尚未物化的核心文件。
    if missing:  # 检查账本输入是否完整。
        raise FileNotFoundError(f"Missing generated artifacts: {missing}")  # 阻止生成不完整哈希账本。
    records = [{"path": name, "sha256": file_sha256(OUTPUT_DIR / name), "bytes": (OUTPUT_DIR / name).stat().st_size} for name in artifact_names]  # 计算稳定顺序的哈希与大小。
    lines = [f"{record['sha256']}  {record['path']}" for record in records]  # 生成兼容 sha256sum 的文本行。
    (OUTPUT_DIR / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")  # 写入核心生成物哈希账本。
    return {"artifact_count": len(records), "records": records}  # 返回账本摘要供测试使用。


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:  # 校验完整性和禁止迁移项。
    cases = load_cases()  # 载入输入工况用于比对。
    modes = load_modes()  # 载入输入模态用于比对。
    summary = graph_summary(graph)  # 计算当前图谱汇总。
    acceptance = migration_acceptance(graph)  # 执行完整模型迁移验收。
    node_id_list = [node["id"] for node in graph["nodes"]]  # 收集节点 ID 并保留重复项。
    edge_id_list = [edge["id"] for edge in graph["edges"]]  # 收集边 ID 并保留重复项。
    node_ids = set(node_id_list)  # 建立端点查找集合。
    response_nodes = [node for node in graph["nodes"] if node["type"] == "C3CaseResponse"]  # 提取全部 C3 响应节点。
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
        "c3_envelope_reference_10": summary["physics_decision_counts"].get("REFERENCE_ONLY_C3_ENVELOPE") == 10,  # 检查 C3 包络参考清单。
        "node_ids_unique": len(node_id_list) == len(node_ids),  # 检查节点 ID 没有重复。
        "edge_ids_unique": len(edge_id_list) == len(set(edge_id_list)),  # 检查边 ID 没有重复。
        "edge_endpoints_exist": not missing_endpoints,  # 检查所有边端点。
        "responses_strictly_empty_43": len(response_nodes) == 43 and all(set(node["properties"]) == {"state", "transferred_numeric_values"} and node["properties"]["state"] == "NOT_MATERIALIZED" and node["properties"]["transferred_numeric_values"] is False for node in response_nodes),  # 检查响应字段白名单并阻止伪造数值。
        "legacy_numeric_transfer_blocked": all(edge["properties"].get("numerical_value_transfer") is not True for edge in graph["edges"]),  # 检查任一图谱边均未开启旧数值迁移。
        "migration_acceptance_pass": acceptance["status"] == "PASS",  # 检查完整迁移验收全部通过。
    }  # 完成检查表。
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "missing_edge_ids": missing_endpoints, "summary": summary, "migration_acceptance_status": acceptance["status"]}  # 组装校验结果。
    return result  # 返回校验结果。


def materialize_graph(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:  # 一次性物化图谱、验收、校验与哈希账本。
    summary = emit_outputs(graph)  # 输出图谱表、汇总和迁移验收收据。
    validation = validate_graph(graph)  # 执行防篡改校验。
    emit_json(OUTPUT_DIR / "validation.json", validation)  # 输出确定性校验收据。
    manifest = emit_generated_sha_manifest()  # 最后计算全部核心生成物哈希。
    return summary, validation, manifest  # 返回三类结果供命令行选择显示。


def find_case(case_id: str) -> dict[str, Any]:  # 按原始或 C3 ID 查找工况。
    for case in load_cases():  # 顺序扫描仅 43 行的小表。
        if case_id in (case["id"], case["c3_case_id"]):  # 同时接受两种 ID。
            return case  # 返回匹配工况。
    raise KeyError(f"Unknown case: {case_id}")  # 对未知工况给出明确错误。


def facts_for_case(case: dict[str, Any]) -> dict[str, Any]:  # 构造 Doubao 只读事实包。
    binding = read_json(ROOT / "model_binding.json")  # 读取 C3 模型事实。
    trace = make_trace(case, binding)  # 重算该工况四智能体追踪。
    modes = load_modes()  # 读取 14 阶模态事实。
    comparison_pairs_not_aligned = [mode for mode in modes if "not_aligned" in mode["interpretation"]]  # 提取明确未对齐的 Table4-1 比较候选。
    return {  # 返回最小充分事实包。
        "case": case,  # 提供工况事实。
        "c3_model": {"model_id": binding["model_id"], "deck_sha256": binding["deck"]["sha256"], "solver_sha256": binding["solver"]["sha256"], "response_state": binding["response_state"]},  # 提供模型身份。
        "modal_frequencies_hz": binding["modal_receipt"]["frequencies_hz"],  # 提供原生频率。
        "comparison_pairs_not_aligned": comparison_pairs_not_aligned,  # 提供明确标为未对齐且未验收的比较候选。
        "agent_trace": trace,  # 提供四智能体追踪。
        "hard_facts": ["C3 43-case buffeting response is NOT_MATERIALIZED", "Double-MCT numerical response values are provenance only", "Table4-1 comparison candidates are NOT_ALIGNED", "warning status is NOT_ARMED", "dispatch is false"],  # 固定不可改写事实。
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
        summary, validation, _ = materialize_graph(build_graph())  # 构图并物化全部模型迁移收据。
        write_result(None, summary)  # 显示图谱汇总。
        return 0 if validation["status"] == "PASS" else 1  # 将迁移验收失败传播给 CI。
    if args.command == "validate":  # 处理校验命令。
        graph = build_graph()  # 在内存中重建图谱。
        _, result, _ = materialize_graph(graph)  # 物化并执行完整防篡改校验。
        write_result(None, result)  # 显示已保存的校验结果。
        return 0 if result["status"] == "PASS" else 1  # 将失败传播给 CI。
    result = run_ask(args.case_id, args.question, args.offline, args.require_llm)  # 执行问答命令。
    write_result(args.output, result)  # 保存并显示 Demo。
    return 0  # 返回成功。


if __name__ == "__main__":  # 仅在直接执行脚本时运行入口。
    raise SystemExit(main())  # 将返回码交给操作系统。
