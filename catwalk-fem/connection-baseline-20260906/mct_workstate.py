from pathlib import Path  # 管理本轮输入输出，不读取历史试算目录。
import json, re, hashlib, subprocess, os, sys, traceback  # 保留真实求解状态及输入摘要。
import numpy as np  # 计算实际几何和杆件轴力。
import scipy.sparse as sp  # 组装独立理论稀疏矩阵。
from scipy.sparse.linalg import spsolve, eigsh  # 独立求平衡及平面诊断模态。
import requests  # 只下载指定的原始MCT。
from urllib.parse import quote  # 正确编码原件中文路径。
ROOT = Path('catwalk-current-run')  # 本轮目录与所有旧结果分离。
ROOT.mkdir(exist_ok=True)  # 创建实际运行目录。
SOURCE_REF = 'cfbf39ef51a5bb86f13372553cee122d02df0f57'  # 固定交接原件所在提交。
SOURCE_PATH = 'catwalk-fem/mct-from-zero/source/01_设计资料与规范/猫道 - 门架索合建模型2.mct'  # 只读取原始联合模型。
url = 'https://raw.githubusercontent.com/Hiram-test/model/' + SOURCE_REF + '/' + quote(SOURCE_PATH, safe='/')  # 构造已核实原件地址。
response = requests.get(url, timeout=90)  # 下载原件而非旧模型生成器。
response.raise_for_status()  # 网络失败不伪装成空输入。
raw = response.content  # 保留原件字节。
(ROOT / 'original.mct').write_bytes(raw)  # 保存本轮真正使用的原件。
try: text = raw.decode('utf-8-sig')  # 优先使用原件的UTF编码。
except UnicodeDecodeError: text = raw.decode('gb18030')  # 兼容原始中文Windows编码。
records, section, loadcase, buffer = [], '', '', ''  # 建立保留荷载工况的原始记录表。
for original_line in text.splitlines():  # 顺序读取原件，不覆盖重复章节。
    line = original_line.split(';', 1)[0].strip()  # 只去除MCT注释。
    if not line: continue  # 空行不是工程数据。
    if line.endswith('\\'): buffer += line[:-1] + ' '; continue  # 合并MCT的续行列表。
    line, buffer = buffer + line, ''  # 完成一条完整原始记录。
    if line.startswith('*'):  # 更新章节及作用工况。
        section = line.split(',')[0].strip().upper()  # 保存准确章节标识。
        if section == '*USE-STLD': loadcase = line.split(',', 1)[1].strip()  # 保留后续荷载的工况归属。
        continue  # 章节名不作为数值行解析。
    records.append((section, loadcase, [s.strip() for s in line.split(',')]))  # 保留按逗号划分的原件字段。
def rows(key): return [(lc, r) for sec, lc, r in records if sec == key]  # 读取指定原件章节。
def ids(value):  # 展开MCT节点与单元范围表达式。
    result = []  # 保存原始编号，不重编号为连续假数据。
    for token in value.split():  # 一条列表可能包含多个范围。
        match = re.fullmatch(r'(\d+)(?:to(\d+))?(?:by(\d+))?', token, re.I)  # 只解释已知MCT编号语法。
        if not match: raise ValueError('Unsupported MCT list: ' + token)  # 不猜测未知编号语法。
        a, b, c = match.groups(); result.extend(range(int(a), int(b or a) + 1, int(c or 1)))  # 正确展开闭区间及步长。
    return result  # 返回原始节点或单元编号。
node_dict = {int(r[0]): np.array(r[1:4], float) / 1000. for _, r in rows('*NODE')}  # 将毫米转换为米。
node_ids = sorted(node_dict); node_index = {n: i for i, n in enumerate(node_ids)}  # 建立不改变原件拓扑的索引。
X = np.array([node_dict[n] for n in node_ids]); nn = len(X)  # 保存原始坐标矩阵。
materials = {int(r[0]): {'E': float(r[10]) * 1.e9, 'weight_density': float(r[13]) * 1.e12} for _, r in rows('*MATERIAL')}  # 将kN/mm²及kN/mm³转为SI。
sections = {}  # 由原件几何截面计算面积。
for _, r in rows('*SECTION'):  # 只使用模型SECTION，不用设计验算章节替换它。
    if r[12] == 'SR': area = np.pi * float(r[14]) ** 2 / 4.e6  # 圆截面等效索束面积，不再乘索根数。
    elif r[12] == 'B': area = (float(r[14]) * float(r[15]) - (float(r[14]) - 2. * float(r[16])) * (float(r[15]) - 2. * float(r[17]))) / 1.e6  # 使用原件箱形截面定义。
    else: raise ValueError('Unsupported original section: ' + repr(r))  # 避免静默替换未知截面。
    sections[int(r[0])] = area  # 记录实际面积。
conn, lengths0, rigidities, weights, tension_only, element_ids, types = [], [], [], [], [], [], []  # 记录逐单元物理参数。
for _, r in rows('*ELEMENT'):  # 逐一保留原件所有单元。
    eid, typ, mat, sec, n1, n2 = int(r[0]), r[1], int(r[2]), int(r[3]), int(r[4]), int(r[5])  # 不按编号区段猜测单元类型。
    ij = [node_index[n1], node_index[n2]]; L = float(np.linalg.norm(X[ij[1]] - X[ij[0]]))  # 计算真实空间弦长。
    if typ == 'TENSTR' and int(r[7]) == 3 and int(r[9]) == 3: Lu = float(r[8]) / 1000.  # 原件本批索采用无应力长度输入。
    elif typ == 'TRUSS': Lu = L  # 原件门架桁架没有另给预应变。
    else: raise ValueError('Unsupported original element record: ' + repr(r))  # 不把其他索选项误当无应力长度。
    conn.append(ij); lengths0.append(Lu); rigidities.append(materials[mat]['E'] * sections[sec])  # 保存原长与EA。
    weights.append(materials[mat]['weight_density'] * sections[sec] * Lu); tension_only.append(typ == 'TENSTR')  # 自重按未伸长材料长度离散。
    element_ids.append(eid); types.append(typ)  # 保存原始单元编号与类型。
conn = np.array(conn); Lu = np.array(lengths0); EA = np.array(rigidities); weight = np.array(weights); unilateral = np.array(tension_only)  # 转为数值数组。
nd = 3 * nn; force = np.zeros((nn, 3)); mass = np.zeros(nn)  # 分开保存荷载与动力质量。
for end in [0, 1]: np.add.at(force[:, 2], conn[:, end], -weight / 2.); np.add.at(mass, conn[:, end], weight / (2. * 9.806))  # 原始自重一致分配给端节点。
for lc, r in rows('*CONLOAD'):  # 只加载原件一次成桥采用的二期工况。
    if lc != '二期': continue  # 不把施工、温降和风工况混入恒载状态。
    for nid in ids(r[0]):  # 保留原件节点荷载列表。
        j = node_index[nid]; force[j] += np.array(r[1:4], float) * 1000.; mass[j] += max(0., -float(r[3]) * 1000. / 9.806)  # 平面诊断质量为恒载质量化，非空间质量审定。
fixed = set(range(1, nd, 3))  # 本阶段是设计院平面联合模型迁移，明确限制全部Y自由度。
for _, r in rows('*CONSTRAINT'):  # 保留原件支点的X、Z约束。
    for nid in ids(r[0]):  # 展开原件支点列表。
        for d, flag in enumerate(r[1][:3]):  # 仅轴向构件的三个平移自由度。
            if flag == '1': fixed.add(3 * node_index[nid] + d)  # 不额外固定原件释放的纵向位移。
free = np.array(sorted(set(range(nd)) - fixed)); flatforce = force.ravel()  # 建立自由方程和外载。
Lref = np.linalg.norm(X[conn[:, 1]] - X[conn[:, 0]], axis=1)  # 计算MCT参考构形的所有弦长。
Nref = EA * (Lref / Lu - 1.); Nref = np.where(unilateral, np.maximum(Nref, 0.), Nref)  # 从原长得到工作初拉力而非复制历史索力。
iniforce = [{'element': r[0], 'direction': r[1], 'force_N': float(r[2]) * 1000.} for _, r in rows('*INIFORCE')]  # 单独保留初力功能原文，防止双重叠加。
provenance = {'scope': 'DESIGN_INSTITUTE_PLANAR_MCT_TRANSFER_ONLY_NOT_SPATIAL_CATWALK', 'source_commit': SOURCE_REF, 'source_path': SOURCE_PATH, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'nodes': nn, 'elements': len(conn), 'units': 'N m kg', 'INIFORCE_records': iniforce, 'initial_force_policy': 'Lu defines cable prestress; the six INIFORCE records are retained for audit, not added to Lu prestress a second time; exact MIDAS stage semantics remain a separate check.', 'mass_policy': 'MCT self-weight and phase-2 vertical loads lumped as gravity mass for planar diagnostic only', 'solver_scope_limit': 'Straight cable subdivisions approximate the elastic-catenary elements; no spatial gantry or passage is claimed.'}  # 不把平面迁移写成整桥正确性结论。
(ROOT / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2))  # 记录实际输入及其限制。
localdofs = np.hstack((3 * conn[:, 0, None] + np.arange(3), 3 * conn[:, 1, None] + np.arange(3)))  # 每根杆的六个平移自由度。
ridx = np.repeat(localdofs, 6, axis=1).ravel(); cidx = np.tile(localdofs, (1, 6)).ravel()  # 固定刚度矩阵装配索引。
def assemble(Y):  # 独立的三维受拉杆与普通桁架切线，不导入CCX矩阵。
    vectors = Y[conn[:, 1]] - Y[conn[:, 0]]; lengths = np.linalg.norm(vectors, axis=1); tangents = vectors / lengths[:, None]  # 计算当前杆向。
    N = EA * (lengths / Lu - 1.); active = (~unilateral) | (N > 0.); N = np.where(active, N, 0.)  # 保留普通桁架受压并去掉松索压力。
    nnmat = tangents[:, :, None] * tangents[:, None, :]; local = (EA / Lu * active)[:, None, None] * nnmat + (N / lengths)[:, None, None] * (np.eye(3) - nnmat)  # 材料刚度与当前轴力几何刚度。
    blocks = np.concatenate((np.concatenate((local, -local), axis=2), np.concatenate((-local, local), axis=2)), axis=1)  # 逐杆两端作用反作用。
    K = sp.coo_matrix((blocks.ravel(), (ridx, cidx)), shape=(nd, nd)).tocsr(); internal = np.zeros_like(Y)  # 装配全局切线。
    np.add.at(internal, conn[:, 0], -N[:, None] * tangents); np.add.at(internal, conn[:, 1], N[:, None] * tangents)  # 装配实际杆力。
    return K, internal.ravel(), N  # 返回平衡与独立模态需要的数据。
Y = X.copy(); history = []  # 从原MCT构形而不是旧变形线开始。
for it in range(60):  # 实际进行非线性平衡迭代并完整保存失败状态。
    K, internal, N = assemble(Y); residual = flatforce - internal; norm = float(np.linalg.norm(residual[free])); history.append({'iteration': it, 'residual_N': norm})  # 记录可复核残差。
    print('NEWTON', it, 'residual_N', norm, flush=True)  # 输出真实迭代而不是预报进度。
    if norm < 1.e-5: break  # 力残差达到数值精度才结束Newton迭代。
    increment = spsolve(K[free][:, free], residual[free]); step = np.zeros(nd); step[free] = increment  # 求自由节点修正。
    if not np.isfinite(increment).all(): raise RuntimeError('Singular planar tangent; no artificial restraints were added.')  # 不为了收敛改结构。
    alpha = 1.  # 初次尝试完整Newton步。
    for trial in range(18):  # 仅用数值线搜索，不改变材料或边界。
        candidate = Y + alpha * step.reshape(nn, 3); _, ci, _ = assemble(candidate)  # 用当前物理模型检验新残差。
        if np.linalg.norm((flatforce - ci)[free]) < norm: break  # 选取减小平衡残差的步长。
        alpha *= .5  # 缩短数值步长而不改变平衡问题。
    Y = candidate  # 更新实际平衡迭代。
K, internal, N = assemble(Y); residual_norm = float(np.linalg.norm((flatforce - internal)[free]))  # 保存最后状态，即使未收敛也不伪造成功。
mass = np.maximum(mass, 1.e-12); M = sp.diags(np.repeat(mass, 3)).tocsr()  # 正的微量原件质量保留在平面诊断中。
np.savez_compressed(ROOT / 'planar_state.npz', node_ids=node_ids, element_ids=element_ids, X=X, Y=Y, conn=conn, Lu=Lu, EA=EA, N=N, Nref=Nref, force=force, mass=mass, free=free)  # 保存新计算状态供后续真实空间展开。
sp.save_npz(ROOT / 'planar_K.npz', K); sp.save_npz(ROOT / 'planar_M.npz', M)  # 保存独立理论矩阵，不读取旧矩阵。
theory = {'scope': provenance['scope'], 'equilibrium_residual_N': residual_norm, 'max_displacement_m': float(np.max(np.linalg.norm(Y-X, axis=1))), 'total_mass_kg': float(mass.sum()), 'min_cable_force_N': float(N[unilateral].min()), 'iterations': history}  # 输出真值及适用范围。
try:  # 平面模态只是迁移诊断，不作为整桥十四阶。
    ev, modes = eigsh(K[free][:, free], k=30, M=M[free][:, free], sigma=0., which='LM', tol=1.e-10)  # 独立提取真实平面特征值。
    order = np.argsort(ev); theory['planar_diagnostic_frequencies_hz'] = (np.sqrt(np.maximum(ev[order], 0.)) / (2. * np.pi)).tolist()  # 不预先匹配附件标签。
except Exception as exc: theory['modal_error'] = repr(exc)  # 保存计算失败而不是补填频率。
(ROOT / 'theory.json').write_text(json.dumps(theory, ensure_ascii=False, indent=2))  # 先保存独立解，避免原生失败时丢失本轮工作。
deck = ['** Original MCT planar transfer; NOT the spatial catwalk frequency answer.', '*NODE,NSET=NALL']  # 明确原生输入的范围。
for nid, xyz in zip(node_ids, X): deck.append(f'{nid},' + ','.join(f'{v:.12e}' for v in xyz))  # 保留每一个原始节点坐标。
for ei, (eid, ij) in enumerate(zip(element_ids, conn)):  # 为每根原始杆写原生轴向力—伸长曲线。
    k = EA[ei] / Lu[ei]; L = Lref[ei]; n0 = EA[ei] * (L / Lu[ei] - 1.)  # 保留原长对应的初力和切线。
    deck.extend([f'*ELEMENT,TYPE=SPRINGA,ELSET=S{eid}', f'{eid},{node_ids[ij[0]]},{node_ids[ij[1]]}', f'*SPRING,ELSET=S{eid},NONLINEAR', ''])  # 不写虚构单元类型。
    if unilateral[ei]: points = [(0., -.99*L), (0., -n0/k), (max(0., n0), 0.), (n0+k*L, L)]  # 保留松索不承压及工作点正拉力。
    else: points = [(-k*L, -L), (0., 0.), (k*L, L)]  # 原件TRUSS同时允许受拉受压。
    unique = {float(delta): float(value) for value, delta in points}  # 避免零初力时重复位移点。
    for delta in sorted(unique): deck.append(f'{unique[delta]:.12e},{delta:.12e}')  # CCX实数全部含小数点。
for j, nid in enumerate(node_ids): deck.extend([f'*ELEMENT,TYPE=MASS,ELSET=M{nid}', f'{200000+j},{nid}', f'*MASS,ELSET=M{nid}', f'{mass[j]:.12e}'])  # 给平面模型写入已说明的恒载质量。
deck.append('*BOUNDARY')  # 按平面联合模型范围写边界。
for dof in sorted(fixed): deck.append(f'{node_ids[dof//3]},{dof%3+1},{dof%3+1}')  # 不新增约束来改变物理答案。
deck.extend(['*STEP,NLGEOM,INC=100', '*STATIC', '1.,1.,1.e-8,1.', '*CLOAD'])  # 从原MCT构形施加完整自重与二期载荷。
for j, nid in enumerate(node_ids):  # 写出实际节点荷载。
    for d in range(3):  # 保留原件三向荷载。
        if force[j,d] != 0.: deck.append(f'{nid},{d+1},{force[j,d]:.12e}')  # 只去掉精确为零的分量。
deck.extend(['*NODE PRINT,NSET=NALL', 'U,RF', '*NODE FILE', 'U', '*END STEP', '*STEP,PERTURBATION', '*FREQUENCY', '30,0.,1.', '*NODE FILE', 'U', '*END STEP'])  # 在实际静力后求原生平面诊断模态。
inp = ROOT / 'mct_planar.inp'; inp.write_text('\n'.join(deck) + '\n')  # 保存完整可复算原生输入。
status = {'scope': provenance['scope'], 'input_sha256': hashlib.sha256(inp.read_bytes()).hexdigest(), 'theory_residual_N': residual_norm, 'spatial_fourteen_modes_completed': False}  # 永不将平面求解包装成整桥求解。
with (ROOT / 'ccx.log').open('w') as log:  # 将真实原生输出流永久保存。
    try: status['ccx_returncode'] = subprocess.run(['ccx', 'mct_planar'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900, env={**os.environ, 'OMP_NUM_THREADS':'2', 'CCX_NPROC_EQUATION_SOLVER':'2'}).returncode  # 实际调用原生求解器。
    except subprocess.TimeoutExpired: status['ccx_timed_out'] = True  # 超时不是成功，不报完成。
logtext = (ROOT / 'ccx.log').read_text(errors='replace'); status['ccx_job_finished'] = 'Job finished' in logtext  # 退出码和完成标志同时记录。
status['ccx_error_lines'] = [line for line in logtext.splitlines() if '*ERROR' in line or '*WARNING' in line][-30:]  # 显示真实求解器诊断。
(ROOT / 'execution.json').write_text(json.dumps(status, ensure_ascii=False, indent=2))  # 保存不可混淆的执行状态。
print('THEORY', json.dumps(theory, ensure_ascii=False), flush=True)  # 在Actions日志中留下可检索结果。
print('EXECUTION', json.dumps(status, ensure_ascii=False), flush=True)  # 在Actions日志中留下是否真正完成的证据。
print('CCX_LOG_TAIL', logtext[-9000:], flush=True)  # 公开实际日志尾部以便当轮核验。
if status.get('ccx_returncode') != 0 or not status.get('ccx_job_finished'): sys.exit(2)  # 数值失败仍已保存全部输入日志，但不标工作流成功。
