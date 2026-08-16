from __future__ import annotations  # 启用延迟类型注解，保证数据类与返回类型稳定。
import hashlib  # 校验VLM审图留痕对应的粗解图像未被替换。
import json  # 读取人工可审计的视觉观察与动作先验。
from dataclasses import dataclass  # 定义极小PSO配置和VLM留痕对象。
from pathlib import Path  # 管理图像与留痕文件路径。
from typing import Any  # 标注异质审计字典。
import numpy as np  # 执行二维粒子更新和数值排序。
from comparison.common import MeshCompilerCache  # 复用确定性网格编译缓存。
from comparison.common import evaluate_surrogate  # 复用粗解条件化低成本适应度。
from comparison.common import latent_action  # 将二维动作坐标解码为五维网格动作。
from comparison.contracts import BenchmarkContext  # 导入统一比较上下文。
from comparison.contracts import MethodProposal  # 导入统一方法输出对象。
from tbeam_fem_core import Action  # 导入五维网格动作对象。
@dataclass(frozen=True)  # 将极小PSO参数定义为不可变配置。
class MicroPSOConfig:  # 描述五粒子一次更新的二维局部执行器。
    seed: int = 7  # 设置可重复随机种子。
    scale_radius: float = 0.22  # 设置整体尺度轴初始半径。
    contrast_radius: float = 0.30  # 设置热点对比轴初始半径。
    inertia: float = 0.35  # 设置一次更新的惯性权重。
    cognitive: float = 0.80  # 设置个体最优吸引系数。
    social: float = 1.20  # 设置全局最优吸引系数。
    max_velocity: float = 0.18  # 设置二维对数动作最大速度。
@dataclass(frozen=True)  # 将VLM留痕中的可执行部分定义为不可变对象。
class VLMTrace:  # 保存视觉观察、五维中心和二维对比方向。
    source: str  # 保存留痕来源说明。
    image_path: str  # 保存审阅图像相对路径或绝对路径。
    image_sha256: str  # 保存审阅图像哈希。
    goal: str  # 保存审阅时采用的语言任务。
    priorities: np.ndarray  # 保存六区域视觉语义优先级。
    center: Action  # 保存五维连续动作中心。
    contrast_direction: np.ndarray  # 保存二维执行器的五维资源转移方向。
    observations: list[str]  # 保存可公开审计的视觉事实摘要。
    limitations: list[str]  # 保存视觉判断边界与不确定性。
def file_sha256(path: Path) -> str:  # 计算文件SHA256以固定VLM输入证据。
    digest = hashlib.sha256()  # 创建SHA256摘要器。
    with path.open("rb") as handle:  # 以二进制方式打开图像。
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # 分块读取以兼容较大图像。
            digest.update(block)  # 将当前数据块写入摘要器。
    return digest.hexdigest()  # 返回十六进制哈希字符串。
def load_trace(path: Path, project_root: Path) -> VLMTrace:  # 读取并验证人工VLM审图留痕。
    payload = json.loads(path.read_text(encoding="utf-8"))  # 读取UTF-8 JSON留痕。
    image_path = Path(str(payload["input"]["image_path"]))  # 读取留痕中记录的图像路径。
    resolved_image = image_path if image_path.is_absolute() else project_root / image_path  # 将相对图像路径解析到项目根目录。
    if not resolved_image.is_file():  # 检查审阅图像是否存在。
        raise FileNotFoundError(f"VLM trace image not found: {resolved_image}")  # 对缺失输入证据立即失败。
    actual_hash = file_sha256(resolved_image)  # 计算当前图像哈希。
    expected_hash = str(payload["input"]["image_sha256"])  # 读取留痕声明哈希。
    if actual_hash != expected_hash:  # 检查图像是否与留痕一致。
        raise ValueError("VLM trace image hash mismatch")  # 禁止将旧留痕套到新图像。
    priorities = np.asarray(payload["decision"]["region_priority"], dtype=float)  # 读取六区域视觉优先级。
    direction = np.asarray(payload["decision"]["contrast_direction"], dtype=float)  # 读取五维资源转移方向。
    if priorities.shape != (6,):  # 检查六区域优先级长度。
        raise ValueError("VLM trace region_priority must contain six values")  # 对错误留痕模式立即失败。
    if direction.shape != (5,):  # 检查五维对比方向长度。
        raise ValueError("VLM trace contrast_direction must contain five values")  # 对错误动作模式立即失败。
    center = Action(**payload["decision"]["action_center"])  # 将五维中心解析为类型化动作。
    return VLMTrace(str(payload["provenance"]["source"]), str(resolved_image), expected_hash, str(payload["input"]["language_goal"]), priorities, center, direction, [str(item) for item in payload["visual_observations"]], [str(item) for item in payload["limitations"]])  # 返回通过验证的留痕对象。
class VLMMicroPSO:  # 用人工VLM留痕驱动五粒子一次更新执行器。
    name = "vlm_trace_micro_pso"  # 定义统一方法名称。
    def __init__(self, trace_path: Path, project_root: Path, config: MicroPSOConfig | None = None) -> None:  # 初始化留痕路径与极小PSO配置。
        self.trace_path = trace_path  # 保存VLM留痕文件路径。
        self.project_root = project_root  # 保存项目根目录以解析图像路径。
        self.config = config or MicroPSOConfig()  # 使用显式配置或默认五粒子配置。
    def propose(self, context: BenchmarkContext) -> MethodProposal:  # 从同一粗解状态提出终局网格动作。
        trace = load_trace(self.trace_path, self.project_root)  # 读取并验证VLM审图留痕。
        rng = np.random.default_rng(self.config.seed)  # 创建可重复随机数生成器。
        positions = np.array([[0.0, 0.0], [-self.config.scale_radius, 0.0], [self.config.scale_radius, 0.0], [0.0, -self.config.contrast_radius], [0.0, self.config.contrast_radius]], dtype=float)  # 构造中心与四个轴向邻近粒子。
        velocities = rng.normal(0.0, 0.025, size=positions.shape)  # 给五个粒子设置极小初始速度。
        cache = MeshCompilerCache(context)  # 创建当前方法的真实网格编译缓存。
        evaluation_rows: list[dict[str, Any]] = []  # 创建可审计候选历史。
        def evaluate(position: np.ndarray, stage: str, particle: int) -> tuple[float, Any]:  # 定义二维粒子低成本评价器。
            action = latent_action(context, trace.center, trace.contrast_direction, float(position[0]), float(position[1]))  # 解码二维粒子为五维网格动作。
            score = evaluate_surrogate(context, action, trace.priorities, cache)  # 用粗解物理量和真实网格编译评价候选。
            evaluation_rows.append({"stage": stage, "particle": int(particle), "scale": float(position[0]), "contrast": float(position[1]), "objective": float(score.objective), "predicted_zz": float(score.predicted_zz), "dof": int(score.dof), "signature": list(score.signature), "realized_action": {"hx_root": float(score.realized_action.hx_root), "hx_mid": float(score.realized_action.hx_mid), "hx_tip": float(score.realized_action.hx_tip), "h_web": float(score.realized_action.h_web), "h_flange": float(score.realized_action.h_flange)}})  # 记录公开可审计的候选与分量。
            return float(score.objective), score  # 返回排序目标和完整候选评价。
        initial = [evaluate(positions[index], "initial", index) for index in range(len(positions))]  # 评价五个初始轴向粒子。
        personal_best = positions.copy()  # 将初始位置设为个体最优位置。
        personal_scores = np.array([item[0] for item in initial], dtype=float)  # 保存五个个体最优分数。
        personal_details = [item[1] for item in initial]  # 保存五个个体最优评价对象。
        global_index = int(np.argmin(personal_scores))  # 找到初始全局最优粒子。
        global_best = personal_best[global_index].copy()  # 保存初始全局最优二维位置。
        global_score = float(personal_scores[global_index])  # 保存初始全局最优分数。
        global_detail = personal_details[global_index]  # 保存初始全局最优候选详情。
        for index in range(len(positions)):  # 对除全局最优外的四个粒子执行一次标准PSO更新。
            if index == global_index:  # 检查当前粒子是否为全局最优。
                continue  # 保持全局最优母粒子不动。
            r1 = rng.random(2)  # 生成二维个体吸引随机系数。
            r2 = rng.random(2)  # 生成二维全局吸引随机系数。
            velocities[index] = self.config.inertia * velocities[index] + self.config.cognitive * r1 * (personal_best[index] - positions[index]) + self.config.social * r2 * (global_best - positions[index])  # 执行一次标准PSO速度更新。
            velocities[index] = np.clip(velocities[index], -self.config.max_velocity, self.config.max_velocity)  # 限制二维速度幅值。
            positions[index] = positions[index] + velocities[index]  # 执行一次粒子位置更新。
            positions[index, 0] = float(np.clip(positions[index, 0], -0.45, 0.45))  # 限制整体尺度坐标范围。
            positions[index, 1] = float(np.clip(positions[index, 1], -0.60, 0.60))  # 限制热点对比坐标范围。
            score_value, detail = evaluate(positions[index], "one_update", index)  # 评价一次更新后的粒子。
            if score_value < personal_scores[index]:  # 检查更新位置是否改善个体最优。
                personal_best[index] = positions[index].copy()  # 更新个体最优位置。
                personal_scores[index] = score_value  # 更新个体最优分数。
                personal_details[index] = detail  # 更新个体最优候选详情。
            if score_value < global_score:  # 检查更新位置是否改善全局最优。
                global_best = positions[index].copy()  # 更新全局最优二维位置。
                global_score = score_value  # 更新全局最优分数。
                global_detail = detail  # 更新全局最优候选详情。
        audit = {"vlm_trace": {"source": trace.source, "image_path": trace.image_path, "image_sha256": trace.image_sha256, "trace_goal": trace.goal, "visual_observations": trace.observations, "limitations": trace.limitations, "region_priority": trace.priorities.tolist(), "action_center": {"hx_root": trace.center.hx_root, "hx_mid": trace.center.hx_mid, "hx_tip": trace.center.hx_tip, "h_web": trace.center.h_web, "h_flange": trace.center.h_flange}, "contrast_direction": trace.contrast_direction.tolist()}, "executor": {"type": "two-dimensional five-particle one-update PSO", "initial_particles": 5, "updated_particles": 4, "maximum_surrogate_evaluations": 9, "selected_latent": {"scale": float(global_best[0]), "contrast": float(global_best[1])}, "selected_objective": float(global_score), "selected_predicted_zz": float(global_detail.predicted_zz), "selected_dof": int(global_detail.dof)}, "evaluations": evaluation_rows}  # 构造不含隐藏推理的完整审计记录。
        return MethodProposal(self.name, global_detail.action, "ready", audit, len(evaluation_rows), cache.compilations, 0, 0, False, True)  # 返回可进入统一终局求解的动作。
