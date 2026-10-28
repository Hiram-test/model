#!/usr/bin/env python3  # Generate native full-field nonlinear transient research labels with explicit provisional aerodynamic inputs.
import argparse  # Select case identity and time-grid settings.
import hashlib  # Bind datasets to exact source, solver code, and numerical result bytes.
import inspect  # Identify a dynamically selected detailed physical model's actual source implementation.
import json  # Preserve numerical quality and modeling assumptions.
import math  # Generate deterministic spatial gust functions.
import sys  # Import the sibling aerodynamic implementation explicitly.
from pathlib import Path  # Keep all model and result paths reproducible.
from types import SimpleNamespace  # Reuse the audited equilibrium runner interface.
import numpy as np  # Store exact numerical arrays without generating images.
import openseespy.opensees as ops  # Drive actual full-order nonlinear finite elements.
import opensees_bridge as bridge_module  # Preserve the executed bridge implementation alongside each complete case.
from opensees_bridge import run  # Establish the source-backed nonlinear preloaded state before dynamics.
import field_stream  # Bind streaming source identity to every numerical case.
import kinematic_audit  # 冻结本次执行的运动相容性检查源码。
from kinematic_audit import rigid_kinematic_audit  # 每个真实子步同时核对刚臂位移、速度和加速度。
from field_stream import FieldStream,atomic_json,file_sha256  # Persist complete native histories without accumulating them in memory.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'aero'))  # Resolve the common physical aerodynamic API.
from aero_loads import CoefficientTable,quasi_steady_loads  # Use dimensional, motion-relative three-force loading.
DEFAULT_SHELL_ELEMENT='ShellNLDKGQ'  # 保留历史生产公式，尚未通过完整约束验证的ASD候选只能显式试验。
DEFAULT_NATIVE_CONVERGENCE_TEST='NormUnbalance'  # 保留历史生产停止准则，不将候选位移模式未经验证升级为默认。
DEFAULT_INITIAL_DISPLACEMENT_TOLERANCE=1e-9  # 保留历史初始预测阈值，候选ASD试验可显式设置1e-8。
def assemble_constraint_actions(m,nodes,values):  # Apply the exact transpose of declared rigid-arm kinematics to nodal actions without discarding physical response fields.
    result=np.asarray(values,dtype=float).copy()  # Keep the independent unassembled force field unchanged.
    lookup={node:index for index,node in enumerate(nodes)}  # Preserve actual native node identities.
    connections=m.get('rigid_connections',[])  # Use only explicit native multipoint constraints.
    slaves=[connection['slave'] for connection in connections]  # Collect dependent degrees by their physical node.
    slave_set=set(slaves)  # Index the complete dependent-node set once for linear-time validation.
    if len(slave_set)!=len(slaves) or any(connection['master'] in slave_set for connection in connections):  # Require the model generator to flatten constraint chains consistently with its native domain.
        raise ValueError('Dynamic audit requires unique slaves and flattened rigid-arm constraints')  # Refuse order-dependent or double-counted force transfer.
    for connection in connections:  # Each dependent node contributes once to its physical retained master.
        master,slave=connection['master'],connection['slave']  # Read exact native constraint ownership.
        imaster,islave=lookup[master],lookup[slave]  # Resolve corresponding complete-field rows.
        arm=m['nodes'][slave]-m['nodes'][master]  # Use the same reference arm as the declared linearized rigidLink beam constraint.
        result[imaster,:3]+=result[islave,:3]  # Preserve all transferred force resultants.
        result[imaster,3:]+=result[islave,3:]+np.cross(arm,result[islave,:3])  # Preserve moment and virtual work under the reference-arm constraint.
        result[islave]=0.  # This nodal balance is accounted at its retained equation; its physical displacement remains exported.
    return result  # Return assembled independent equation actions in the full native node ordering.
def saddle_interfaces(m,reference=None):  # Export actual adjacent cable actions and compatible local frames for downstream explicit-wire submodels.
    result={}  # Preserve each distinct physical saddle support node.
    for saddle in m['sets'].get('SADDLE_INTERFACES',m['sets']['TOWER_TOPS']):  # Use corrected actual saddle seats while preserving legacy-model compatibility.
        displacement=np.asarray(ops.nodeDisp(saddle),dtype=float)  # Read full physical support translation and rotation.
        origin=m['nodes'][saddle]+displacement[:3]  # Locate the current saddle support in global millimetres.
        adjacent=[]  # Retain both cable sides separately instead of inventing one horizontal tension.
        for tag,(group,conn) in m['elements'].items():  # Search actual native adjacency at this mesh resolution.
            if group!='MAIN_CABLES' or saddle not in conn:  # Restrict transfer actions to directly connected main-cable members.
                continue  # Leave tower, deck and hanger actions outside the cable cut interface.
            other=conn[1] if conn[0]==saddle else conn[0]  # Orient each cut tangent away from the saddle.
            endpoint=m['nodes'][other]+np.asarray(ops.nodeDisp(other)[:3],dtype=float)  # Recover the native adjacent node's current position.
            tangent=endpoint-origin  # Form the physical current cable chord.
            length=float(np.linalg.norm(tangent))  # Preserve the actual adjacent-member length.
            if length<=0:  # Refuse a collapsed member before defining orientation.
                raise RuntimeError('Collapsed main-cable member at saddle interface')  # Prevent undefined local boundary directions.
            tangent/=length  # Normalize the outward cable direction.
            transverse=np.asarray([0.,1.,0.])-tangent*tangent[1]  # Project bridge transverse direction onto the cut plane.
            if np.linalg.norm(transverse)<1.e-10:  # Handle an unexpected near-transverse cable without a singular frame.
                transverse=np.asarray([0.,0.,1.])-tangent*tangent[2]  # Use a documented alternate global reference axis.
            transverse/=np.linalg.norm(transverse)  # Normalize the transverse local cut direction.
            frame=np.column_stack((tangent,transverse,np.cross(tangent,transverse)))  # Construct a proper orthonormal local-to-global matrix.
            tension=float(ops.eleResponse(tag,'axialForce')[0])  # Read the actual native tensile force at this accepted state.
            key=f'{saddle}:{tag}'  # Keep stable case-local identity across temporal frames.
            baseline=frame if reference is None else np.asarray(reference[key],dtype=float)  # Compare orientation to the actual permanent equilibrium frame.
            adjacent.append({'interface_id':key,'native_element_id':tag,'source_element_id':m['source_ids'][tag],'saddle_node_id':saddle,'adjacent_node_id':other,'adjacent_node_position_mm':endpoint.tolist(),'adjacent_node_displacement_mm_rotation_rad':ops.nodeDisp(other),'current_member_length_mm':length,'tension_N':tension,'outward_tangent_global':tangent.tolist(),'cable_force_on_saddle_N':(tension*tangent).tolist(),'local_to_global_frame':frame.tolist(),'rotation_from_initial_global':(frame@baseline.T).tolist()})  # Preserve both physical force vectors and finite orientation change.
        result[str(saddle)]={'saddle_node_id':saddle,'current_position_mm':origin.tolist(),'displacement_mm_rotation_rad':displacement.tolist(),'velocity_mm_s_rad_s':ops.nodeVel(saddle),'acceleration_mm_s2_rad_s2':ops.nodeAccel(saddle),'adjacent_main_cable_members':adjacent,'cut_location_scope':'Native adjacent-member chord; local solid cut location must be mapped explicitly and is not assumed identical to this node.'}  # Keep unresolved cut-placement interpolation explicit.
    return result  # Return actual native support and cable data, never a reused historical horizontal-force constant.
def dynamic_balance(m,nodes,index,applied,alpha,native_test_type='NormUnbalance',native_test_tolerance=None):  # 输入完整模型、已施加力、阻尼及实际原生停止判据；返回独立力残差和带正确单位的审计，不修正状态。
    native_norms=ops.testNorm()  # 保存收敛测试历史；这是提交前测试的范数，不是提交后重新组装的残差。
    iterations=int(ops.testIter())  # 记录实际迭代数，用于截取原生定长历史缓冲区中的有效项。
    last_norm=float(native_norms[iterations-1]) if 0<iterations<=len(native_norms) else None  # 仅在迭代索引有效时读取末次范数；None表示证据不可用。
    internal=np.zeros((len(nodes),6))  # 每节点6列分别为3个N内力和3个Nmm内力矩；零初值用于完整单元累加。
    for tag,(group,conn) in m['elements'].items():  # tag为原生单元号，group为构件组，conn为连接节点；遍历全部真实单元。
        force=np.asarray(ops.eleForce(tag),dtype=float).reshape(len(conn),6)  # 读取提交状态重算的全局抵抗力；每连接节点必须提供6个分量。
        for node,value in zip(conn,force):  # node为原生节点号，value为该单元在该节点的N/Nmm贡献。
            internal[index[node]]+=value  # 按真实连接累加内力，不归一化、不消除残差。
    mass=np.asarray([m['mass'][node] for node in nodes])[:,None]  # 节点集中质量单位为tonne；单元质量为零，列形状便于逐平动分量相乘。
    velocity=np.asarray([ops.nodeVel(node) for node in nodes])  # 读取提交后速度，前3列mm/s，后3列rad/s。
    acceleration=np.asarray([ops.nodeAccel(node) for node in nodes])  # 读取提交后加速度，前3列mm/s²，后3列rad/s²。
    kinematics=rigid_kinematic_audit(m,nodes,np.asarray([ops.nodeDisp(node) for node in nodes]),velocity,acceleration)  # 独立核对全部刚臂的三类原生运动场，防止只看力平衡接受错误状态。
    gravity=np.asarray([m['gravity'][node] for node in nodes])  # 保持预平衡恒载N/Nmm原值，避免与风载混合或重复施加。
    inertia=np.zeros_like(internal)  # 采用与内力相同的6分量形状；未设置旋转质量，旋转惯性项保持零。
    inertia[:,:3]=mass*acceleration[:,:3]  # tonne乘mm/s²直接得到N，无需额外1000倍换算。
    damping=np.zeros_like(internal)  # 单独保留阻尼力，以便审计每个物理项的符号和量纲。
    damping[:,:3]=mass*alpha*velocity[:,:3]  # C=alpha*M，alpha单位1/s，所得平动阻尼力单位N。
    residual=internal-applied-gravity+inertia+damping  # 按R=Fint-Pwind-Pgravity+Ma+Cv形成独立提交后平衡残差。
    ops.reactions('-dynamic')  # 原生引擎在相同提交状态重新计算包含惯性与阻尼的节点反力/残差。
    native=np.asarray([ops.nodeReaction(node) for node in nodes])  # 保存未约束及受约束节点的全部N/Nmm分量。
    residual=assemble_constraint_actions(m,nodes,residual)  # 通过真实刚臂T转置，将从节点力及r叉乘F力矩传递到主节点。
    native=assemble_constraint_actions(m,nodes,native)  # 对原生节点量执行同一个约束变换以保证比较对象一致。
    scales=np.asarray([1.,1.,1.,5500.,5500.,5500.])  # 前3列保持N，后3列除以既有桥宽5500mm得到等效N；不改变原验收定义。
    free=np.asarray([[not value for value in m['fixities'][node]] for node in nodes])  # 排除物理支座及模型标记的依赖自由度，保留独立方程。
    if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(native)):  # 非有限力不能用NaN比较绕过任何物理门槛。
        raise RuntimeError('Non-finite dynamic balance')  # 终止当前算例，保留失败状态而非发布训练数据。
    disagreement=float(np.max(np.abs((residual-native)/scales)))  # 比较全部受约束及自由分量的两套提交后节点组装。
    if disagreement>1.e-4:  # 延用既有1e-4等效N组装一致性门槛，远严于0.02N物理门槛。
        raise RuntimeError(f'Independent/native dynamic balance mismatch {disagreement} equivalent N')  # 不接受力学方程尚未一致的结果。
    rhs=np.asarray(ops.printB('-ret'),dtype=float)  # 注意：printB会调用formUnbalance重新组装提交后RHS，并非读取提交前缓存；RHS符号与R相反。
    if not np.all(np.isfinite(rhs)):  # 检查原生重新组装的方程量，禁止无效数值被写为合格证据。
        raise RuntimeError('Non-finite postcommit dynamic RHS')  # 将失败交由现有算例拒绝流程处理。
    rhs_disagreement=0.  # 初始化独立平衡与原生方程RHS的最大等效N差异。
    for row,node in enumerate(nodes):  # row是物理数组行号，node是原生节点号；只映射实际独立方程。
        if not np.any(free[row]):  # 全约束支座和依赖节点没有需要独立比较的物理方程。
            continue  # 从节点贡献已由T转置计入主节点，避免重复计数。
        equations=ops.nodeDOFs(node)  # 原生RCM重排后的方程编号；不把节点号或物理行号当作方程号。
        for dof in np.flatnonzero(free[row]):  # dof取0到5的自由分量，依次检查力和力矩方程。
            equation=int(equations[dof])  # 读取该独立物理分量对应的原生方程编号。
            if not 0<=equation<len(rhs):  # 自由分量必须映射到合法原生方程，负编号或越界表明模型契约失配。
                raise RuntimeError('Free dynamic DOF has no native equation')  # 禁止用缺失方程制造一致结果。
            rhs_disagreement=max(rhs_disagreement,abs(float(residual[row,dof]+rhs[equation]))/scales[dof])  # 按R+RHS=0比较并将Nmm转为等效N。
    if rhs_disagreement>1.e-4:  # 沿用现有组装一致性精度要求，不改变0.02N独立物理验收值。
        raise RuntimeError(f'Independent/postcommit RHS mismatch {rhs_disagreement} equivalent N')  # 暴露方程映射或重复查询导致的不一致。
    force_max=float(np.max(np.abs(residual[:,:3])[free[:,:3]],initial=0.))  # 提取自由平动力最大N残差；无自由平动时以零表示空集合。
    moment_max=float(np.max(np.abs(residual[:,3:])[free[:,3:]],initial=0.))  # 提取自由旋转力矩最大Nmm残差；无自由旋转时以零表示空集合。
    scaled=np.where(free,np.abs(residual)/scales,-1.)  # 负哨兵只排除受约束量，保持既有分量最大值判据。
    hotspot=np.unravel_index(int(np.argmax(scaled)),scaled.shape)  # 定位全场独立方程的控制节点与0基分量索引。
    terms={'internal':internal,'negative_wind':-applied,'negative_gravity':-gravity,'inertia':inertia,'damping':damping}  # 保存有符号物理项；其和必须等于热点原始N/Nmm残差。
    hotspot_node=nodes[hotspot[0]]  # 当前独立热点节点；从节点已由自由度掩码排除。
    hotspot_connections=[connection for connection in m.get('rigid_connections',[]) if connection['master']==hotspot_node]  # 只收集确实向热点传力的已展平刚臂，避免五次重扫14078条连接。
    hotspot_nodes=[hotspot_node]+[connection['slave'] for connection in hotspot_connections]  # 局部审计子集保持原连接顺序，以保留同样的浮点累加顺序。
    hotspot_rows=[index[node] for node in hotspot_nodes]  # 从完整物理数组精确抽取热点及其从节点。
    hotspot_model={'nodes':m['nodes'],'rigid_connections':hotspot_connections}  # 复用完整参考坐标和原生产T转置函数，不近似刚臂力矩。
    hotspot_terms={name:float(assemble_constraint_actions(hotspot_model,hotspot_nodes,values[hotspot_rows])[0,hotspot[1]]) for name,values in terms.items()}  # 只计算所需分量，结果与全模型逐项装配一致，减少纯审计开销。
    report={'independent_assembly_difference_equivalent_N':disagreement,'free_force_max_N':force_max,'free_moment_max_Nmm':moment_max,'moment_reference_mm':5500.,'hotspot_native_node':int(nodes[hotspot[0]]),'hotspot_dof_1based':int(hotspot[1])+1,'hotspot_residual_N_or_Nmm':float(residual[hotspot]),'native_test_iterations':iterations,'native_last_test_norm_mixed_N_Nmm':last_norm if native_test_type=='NormUnbalance' else None}  # 旧力范数字段仅在确实使用力判据时给值，防止把位移范数误标成N/Nmm。
    report.update(native_test_type=native_test_type,native_test_tolerance=native_test_tolerance,native_last_test_norm=last_norm,native_test_norm_units='mixed_N_Nmm' if native_test_type=='NormUnbalance' else 'mixed_mm_rad')  # 单独记录实际判据和原始单位；独立0.02N力门槛始终负责物理验收。
    report['rigid_kinematics']=kinematics  # 与每个子步残差一起保留完整相容性检查结果。
    report.update(postcommit_rhs_l2_mixed_N_Nmm=float(np.linalg.norm(rhs)),postcommit_rhs_max_mixed_N_Nmm=float(np.max(np.abs(rhs),initial=0.)),postcommit_rhs_agreement_equivalent_N=rhs_disagreement,hotspot_terms_N_or_Nmm=hotspot_terms)  # 新增提交后原生方程范数、组装误差和控制分量证据；混合范数不替代独立门槛。
    return max(force_max,moment_max/5500.),report  # 返回既有等效N最大残差；接受/拒绝仍由原0.02N及正索力门槛决定。
def execute(args):  # Execute one independent whole-history case with a frozen split.
    args.output.mkdir(parents=True,exist_ok=True)  # Save source identity before any potentially long native calculation.
    storage=getattr(args,'storage','hdf5')  # Default to lossless bounded-memory complete-history storage.
    if storage not in ('hdf5','npz') or args.steps<1 or args.dt<=0:  # Reject ambiguous storage and nonphysical time-grid requests.
        raise ValueError('Require hdf5 or npz storage, positive step count, and positive dt')  # Preserve an explicit reproducible history contract.
    if (args.output/'case_manifest.json').exists():  # Protect a previously published case from an accidental same-path rerun.
        raise FileExistsError('Use a new output directory for each native case')  # Preserve immutable complete-case identities.
    if getattr(args,'detailed_model',True):  # Default to actual separate steel panels, channels, stiffeners, and corrected cable planes.
        import detailed_bridge  # Load the source-dimensional full-order model builder.
        detailed_bridge.SHELL_ELEMENT=getattr(args,'shell_element',DEFAULT_SHELL_ELEMENT)  # 将实际非线性壳公式绑定到本次完整模型，程序调用与命令行默认一致。
        bridge_module.model=detailed_bridge.build  # Preserve the same independently audited native solver for detailed geometry.
    stream=None  # Retain ownership of a partial field stream for truthful failure finalization.
    substep_audit_file=None  # Retain an incremental physical audit for every internal native state, including failed histories.
    try:  # Preserve accepted frames and a failed receipt if any native solve or persistence step fails.
        snapshots={}  # Retain exact case-start implementation snapshots rather than hashing mutable files after the solve.
        source_paths={Path(__file__),Path(field_stream.__file__),Path(bridge_module.__file__),Path(kinematic_audit.__file__),Path(__file__).resolve().parents[1]/'aero'/'aero_loads.py',Path(inspect.getsourcefile(bridge_module.model))}  # 冻结真实模型、平衡和运动相容性审计的全部执行源码。
        for path in source_paths:  # Freeze every executed source dependency known at case start.
            content=path.read_bytes()  # Read one immutable byte image at case start.
            (args.output/path.name).write_bytes(content)  # Preserve the actual source snapshot with case evidence.
            snapshots[path.name]=hashlib.sha256(content).hexdigest()  # Bind the receipt to that saved code revision.
        m,eq=run(SimpleNamespace(source=args.source,state=args.state,subdivision=args.subdivision,output=args.output/'prestate',initial_displacement_tolerance=getattr(args,'initial_displacement_tolerance',DEFAULT_INITIAL_DISPLACEMENT_TOLERANCE)))  # 从真实完整预平衡开始；预测阈值与独立0.001N验收分开且全部记录。
        if eq['status']!='VALID_CONVERGED':  # Never generate training labels from an invalid permanent state.
            raise RuntimeError('Permanent equilibrium rejected; transient labels not produced')  # Preserve the decisive numerical blocker.
        nodes=sorted(m['nodes'])  # Freeze full mesh output order.
        index={n:i for i,n in enumerate(nodes)}  # Map stable physical nodes to contiguous array slots.
        coordinates=np.array([m['nodes'][n] for n in nodes])  # Retain every physical mesh point.
        initial=np.array([ops.nodeDisp(n)+ops.nodeVel(n) for n in nodes])  # Save all native displacement/rotation and velocity/angular-velocity components as the true causal initial state.
        initial_saddles=saddle_interfaces(m)  # Capture actual support and cable actions before variable wind loading.
        reference_frames={entry['interface_id']:entry['local_to_global_frame'] for saddle in initial_saddles.values() for entry in saddle['adjacent_main_cable_members']}  # Freeze finite cut-frame references at permanent equilibrium.
        groups=sorted(set(g for g,c in m['elements'].values())|({'RIGID_CONNECTIONS'} if m.get('rigid_connections') else set()))  # Preserve finite-element families and explicit physical joint constraints separately.
        features=np.zeros((len(nodes),len(groups)+7))  # Store member incidence, mass and boundary conditions explicitly.
        for n in nodes:  # Add actual nodal mass and source support semantics.
            features[index[n],0]=m['mass'][n]  # Record physical mass in tonnes.
            features[index[n],1:7]=m['fixities'][n]  # Preserve constrained translations/rotations.
        deckarea=np.zeros(len(nodes))  # Assemble actual shell tributary area for conservative aerodynamic loads.
        native_dof_mask=np.zeros((len(nodes),6))  # Distinguish real rotational outputs from unused pure-truss rotations.
        native_dof_mask[:,:3]=1.  # Every physical node retains all three translations.
        relation={}  # Deduplicate physical directed element-neighbor relations.
        for tag,(group,conn) in m['elements'].items():  # Build graph semantics directly from complete finite-element topology.
            for n in conn:  # Flag physical member classes at shared mesh interfaces.
                features[index[n],7+groups.index(group)]=1.  # Preserve multi-membership at cable/beam/shell connections.
                if group not in ('MAIN_CABLES','HANGERS','WIND_CABLES'):  # Beam and shell attachments carry actual physical rotational degrees.
                    native_dof_mask[index[n],3:]=1.  # Mark rotational outputs observed only where the native element formulation defines them.
            if group in ('DECK_SHELLS','DECK_PLATES'):  # Load both archived screening shells and actual independently meshed steel panels using their actual areas.
                p=[m['nodes'][n] for n in conn]  # Recover exact mesh coordinates.
                area=np.linalg.norm(np.cross(p[1]-p[0],p[3]-p[0]))  # Integrate planar source shell area.
                for n in conn:  # Share a bilinear cell's area among its vertices.
                    deckarea[index[n]]+=area/4  # Preserve exact total loaded deck area.
            for a in conn:  # Keep all local physical cell interactions.
                for b in conn:  # Form directed relations for source integration.
                    if a!=b:  # Exclude duplicate self-relations handled by local operator updates.
                        relation[(index[a],index[b],groups.index(group))]=1.  # Deduplicate incident elements without dropping physical nodes.
        for connection in m.get('rigid_connections',[]):  # Retain every actual rigid-arm interface in the operator's physical relation graph.
            master,slave=connection['master'],connection['slave']  # Read original physical constraint ownership.
            kind=groups.index('RIGID_CONNECTIONS')  # Keep joint constraints distinct from constitutive material relations.
            for node in (master,slave):  # Both native endpoints possess the beam-arm rotational kinematics.
                features[index[node],7+kind]=1.  # Preserve explicit connection membership as an input semantic.
                native_dof_mask[index[node],3:]=1.  # Retain physically constrained rotations rather than masking them as unused truss DOFs.
            relation[(index[master],index[slave],kind)]=1.  # Preserve the actual directed master-to-slave interface.
            relation[(index[slave],index[master],kind)]=1.  # Preserve reciprocal information access without altering native constraints.
        edges=np.array([[a,b] for a,b,t in relation],dtype=np.int64).T  # Export complete element-neighbor and real connection graph.
        edge_types=np.array([t for a,b,t in relation],dtype=np.int64)  # Preserve beam/cable/shell relation ownership.
        quad=np.array([m['mass'][n] for n in nodes])  # Use positive lumped physical mass as quadrature measure.
        if np.any(quad<=0):  # Reject missing physical integration mass instead of filling arbitrary weights.
            raise RuntimeError('Zero nodal mass in full mesh')  # Stop before exporting an ill-defined integral measure.
        evidence={'normalization':'Cd=Fy/(q*B*L);Cl=Fz/(q*B*L);Cm=Mx/(q*B^2*L)','axes':'wind_drag,wind_lift,positive_bridge_x_pitch','geometry_verified':False,'coefficient_validation_passed':False,'reynolds_applicability_verified':False,'status':'ASSUMED_RESEARCH_COEFFICIENTS_NOT_BRIDGE_AERODYNAMIC_DATA','coefficients':[.35,.05,.02]}  # Explicitly prohibit interpreting illustrative coefficients as measured Zhaqing aerodynamics.
        table=CoefficientTable([-45.,45.],[.35,.35],[-.20,.30],[-.05,.09],5.5,evidence,allow_unverified=True)  # Use explicit bounded provisional angular coefficients for numerical workflow development only.
        ops.loadConst('-time',0.)  # Hold converged permanent forces and reset physical dynamic time.
        ops.wipeAnalysis()  # Keep the full solved structural domain while replacing only the analysis procedure.
        ops.constraints('Transformation')  # Preserve exact source constraints.
        ops.numberer('RCM')  # Reorder complete sparse equations without truncating modes.
        ops.system('UmfPack')  # Factor every physical free degree at each nonlinear iteration.
        native_force_tolerance=float(getattr(args,'native_force_tolerance',.002))  # Freeze a positive explicitly declared native stopping threshold without changing the independent physical acceptance gate.
        internal_substeps=int(getattr(args,'internal_substeps',2))  # Use bounded true Newmark substeps inside each exported frame interval to reduce temporal integration residual without changing the output time grid.
        if internal_substeps<1:  # Reject a zero or negative internal time grid before native analysis starts.
            raise ValueError('Internal substeps must be positive')  # Preserve an explicit physical integration contract.
        if not 0<native_force_tolerance<=.01:  # Permit only stricter native solve experiments than the original algorithm.
            raise ValueError('Native force tolerance must be positive and no greater than 0.01')  # Refuse a hidden convergence-threshold relaxation.
        native_test_type=getattr(args,'native_convergence_test',DEFAULT_NATIVE_CONVERGENCE_TEST)  # 默认使用位移停止与独立力验收，原力范数实验仍可显式选择。
        native_displacement_tolerance=float(getattr(args,'native_displacement_tolerance',1e-8))  # 位移预测停止阈值，单位为原生mm/rad混合增量，默认1e-8用于绕过实测舍入底噪。
        if native_test_type not in ('NormUnbalance','NormDispIncr') or not 0<native_displacement_tolerance<=1e-8:  # 仅允许已实现的两种判据及严格正位移阈值。
            raise ValueError('Unsupported native dynamic convergence test')  # 参数不明确时不开始任何动力子步。
        native_test_tolerance=native_force_tolerance if native_test_type=='NormUnbalance' else native_displacement_tolerance  # 按实际判据选择有明确单位的内部阈值。
        ops.test(native_test_type,native_test_tolerance,120,0)  # 原生迭代结束后仍必须通过每一子步的独立力与正索力验收。
        ops.algorithm('NewtonLineSearch',.8)  # Use native Newton line search under motion-dependent wind forcing.
        alpha=.02  # Declare an uncalibrated research mass-damping coefficient in inverse seconds.
        ops.rayleigh(alpha,0.,0.,0.)  # Use directly auditable C=alpha*M damping; no ambiguous postcommit stiffness-damping update enters the force law.
        ops.integrator('Newmark',.5,.25)  # Use implicit average-acceleration time integration without modal reduction.
        ops.analysis('Transient')  # Solve complete physical inertia and structural nonlinearity.
        static=dict(coordinates=coordinates,quadrature=quad,static_features=features,output_mask=np.tile(native_dof_mask,(1,2)),initial_state=initial,relation_edges=edges,relation_types=edge_types,edge_measure=quad[edges[0]],native_entity_ids=np.array(nodes),native_dof_mask=native_dof_mask,aerodynamic_deck_mask=(deckarea>0).astype(float))  # Preserve all complete native mesh, semantics, and initial arrays once.
        cable_ids=sorted(tag for tag,(group,conn) in m['elements'].items() if group in ('MAIN_CABLES','HANGERS','WIND_CABLES'))  # Preserve every actual cable and hanger force identity.
        static['cable_native_element_ids']=np.asarray(cable_ids,dtype=np.int64)  # Store complete stable force-output association once.
        static['cable_relation_types']=np.asarray([groups.index(m['elements'][tag][0]) for tag in cable_ids],dtype=np.int64)  # Preserve force-family semantics independently from motion labels.
        static['rigid_connection_edges']=np.asarray([[index[item['master']],index[item['slave']]] for item in m.get('rigid_connections',[])],dtype=np.int64).reshape(-1,2).T  # Preserve exact master/slave topology for subsequent integration-domain construction.
        initial_cable_force=np.asarray([ops.eleResponse(tag,'axialForce')[0] for tag in cable_ids],dtype=float)  # Read actual complete prestate cable forces from the native solver.
        initial_acceleration=np.asarray([ops.nodeAccel(n) for n in nodes],dtype=float)  # Read actual native initial acceleration without synthesizing a response.
        if storage=='hdf5':  # Keep long full-mesh histories bounded by one time frame in memory.
            stream=FieldStream(args.output/'fields.h5',static,args.steps+1,{'case_id':args.case_id,'split':args.split,'dt_s':args.dt,'internal_substeps':internal_substeps,'native_substep_dt_s':args.dt/internal_substeps,'wind_hold':'piecewise_constant_over_export_frame','wind_sampling':'frame_end_time','export_sampling':'outer_frames_only','acceptance_gate_scope':'all_native_substeps_and_exported_endpoints','source_input_sha256':eq['source_sha256'],'source_snapshots_sha256':snapshots})  # Freeze exact complete-history length, internal native interval, endpoint load-hold contract, and native provenance before transient stepping.
            stream.append(0.,initial,np.zeros((len(nodes),2)),np.zeros((len(nodes),6)),initial_acceleration,{'time_s':0.,'phase':'ACCEPTED_PERMANENT_EQUILIBRIUM','free_residual_equivalent_N':eq['free_residual_max_equivalent_N']},{'time_s':0.,'supports':initial_saddles},initial_cable_force)  # Persist the exact true causal initial state, all cable forces, and actual local-cut conditions.
        else:  # Preserve the explicit small-case legacy interchange option.
            frames,wind_inputs,loads,times,audits,saddles=[initial.copy()],[np.zeros((len(nodes),2))],[np.zeros((len(nodes),6))],[0.],[],[{'time_s':0.,'supports':initial_saddles}]  # Keep the legacy npz channel meanings unchanged.
            accelerations=[initial_acceleration]  # Retain actual acceleration in the explicit legacy in-memory route.
            cable_forces=[initial_cable_force]  # Retain all native cable forces in the explicitly requested legacy route.
        substep_audit_path=args.output/'substep_audits.jsonl'  # Persist every internal gate check independently from the outer exported frame audit.
        substep_audit_file=substep_audit_path.open('w',encoding='utf-8')  # Open the audit before the first native transient increment so partial cases remain inspectable.
        deck=np.flatnonzero(deckarea>0)  # Apply aerodynamic loads to every actual loaded deck node.
        phase=.37*args.seed  # Freeze deterministic phase without random frame-level splitting.
        for step in range(1,args.steps+1):  # Advance one complete independent temporal history.
            t=step*args.dt  # Define actual physical time in seconds.
            if step>1:  # Replace only the previous variable wind load pattern.
                ops.remove('loadPattern',2)  # Keep permanent gravity unchanged.
                ops.remove('timeSeries',2)  # Avoid stale transient load definitions.
            ops.timeSeries('Constant',2)  # Hold the external aerodynamic iterate over one small structural time step.
            ops.pattern('Plain',2,2)  # Apply current full nonlinear relative-flow forces.
            state=np.array([ops.nodeDisp(nodes[i]) for i in deck])  # Read committed physical deck rotations.
            velocity=np.array([ops.nodeVel(nodes[i]) for i in deck])  # Read committed translational and rotational velocity.
            x=coordinates[deck,0]/82000.  # Preserve spatial variation across the real82m main span.
            ramp=min(t/.4,1.)  # Introduce wind gradually to avoid an artificial impulse at prestate time zero.
            speed=ramp*args.speed*(1+.18*np.sin(2*np.pi*.55*t+phase+x*2.3)+.12*np.exp(-((t-.7-.02*args.seed)/.18)**2))  # Generate explicit nonstationary spatial gust input, not measured wind.
            wind=np.column_stack([speed,.08*speed*np.sin(2*np.pi*.7*t+2*x+phase)])  # Supply correlated transverse and vertical wind components.
            prescribed_wind=np.zeros((len(nodes),2))  # Retain one exogenous wind input function on the entire native node set.
            prescribed_wind[deck]=wind  # The declared deck aerodynamic model has no tower/cable direct wind input; the deck mask makes these zeros explicit.
            a=quasi_steady_loads(table,wind,velocity[:,1:3]/1000,state[:,3],velocity[:,3],1.225)  # Include motion-relative velocity, nonlinear squared speed and finite pitch.
            applied=np.zeros((len(nodes),6))  # Preserve every actual external node-force/moment applied this step.
            applied[deck,1]=a['force_y_Npm']*deckarea[deck]/5500/1000  # Convert spanN/m into exact nodalN through shell tributary lengths.
            applied[deck,2]=a['force_z_Npm']*deckarea[deck]/5500/1000  # Apply vertical aerodynamic force consistently.
            applied[deck,3]=a['moment_x_Nm_per_m']*deckarea[deck]/5500  # Convert line moment toNmm using consistent millimetre span tributaries.
            for i in deck:  # Apply loads at every actual deck node.
                ops.load(nodes[i],*applied[i].tolist())  # Pass all physical forces and moments to native dynamic FEM.
            code=0  # Accumulate the requested frame interval from actual implicit nonlinear substeps.
            substep_balance=None  # Retain the final independently audited substep balance for the exported frame.
            for substep in range(internal_substeps):  # Integrate the same physical load hold over smaller native increments while retaining the full nonlinear domain.
                code=ops.analyze(1,args.dt/internal_substeps)  # Solve one true Newmark substep; no field interpolation or postcommit projection is used.
                if code!=0:  # Reject immediately when any internal native increment fails.
                    break  # Preserve the native failure code for the enclosing case receipt.
                substep_residual,substep_balance=dynamic_balance(m,nodes,index,applied,alpha,native_test_type,native_test_tolerance)  # 每个提交子步按同一独立力方程验收，并保留实际内部停止判据及单位。
                substep_tension=min(float(ops.eleResponse(tag,'axialForce')[0]) for tag,(g,c) in m['elements'].items() if g in ('MAIN_CABLES','HANGERS','WIND_CABLES'))  # Require tension-only physical cable applicability at every internal state.
                substep_audit_file.write(json.dumps({'step':step,'substep':substep+1,'time_s':(step-1+(substep+1)/internal_substeps)*args.dt,'free_residual_equivalent_N':substep_residual,'minimum_cable_force_N':substep_tension,**substep_balance},separators=(',',':'))+'\n')  # Preserve the exact internal native balance and convergence-test evidence before any gate decision.
                substep_audit_file.flush()  # Make every accepted or rejected internal state durable during long native runs.
                if substep_residual>.02 or substep_tension<=0 or not substep_balance['rigid_kinematics']['passed']:  # 原力门槛和索力符号保持不变；额外拒绝与声明刚臂约束不相容的状态。
                    atomic_json(args.output/'rejected_step.json',{'step':step,'substep':substep+1,'time_s':(step-1+(substep+1)/internal_substeps)*args.dt,'native_exit_code':code,'free_residual_equivalent_N':substep_residual,'acceptance_tolerance_N':.02,'native_force_tolerance_mixed_N_Nmm':native_force_tolerance,'minimum_cable_force_N':substep_tension,**substep_balance})  # Preserve the exact failing internal physical equation.
                    raise RuntimeError(f'Internal dynamic physical gate failed step{step} substep{substep+1} residual{substep_residual},minimumtension{substep_tension}')  # Do not hide an invalid intermediate state behind an accepted endpoint.
            if code!=0:  # Reject the whole case when an implicit time increment fails.
                raise RuntimeError(f'Native transient failed step{step},code{code}')  # Prevent incomplete history from entering training.
            residual,balance=substep_residual,substep_balance  # Export the last fully audited internal state at the declared outer frame time.
            tension=substep_tension  # Carry the last audited tension into the endpoint receipt and output.
            if residual>.02 or tension<=0:  # Screen numerical equilibrium and invalid compressed cables independently.
                atomic_json(args.output/'rejected_step.json',{'step':step,'time_s':t,'native_exit_code':code,'free_residual_equivalent_N':residual,'acceptance_tolerance_N':.02,'native_force_tolerance_mixed_N_Nmm':native_force_tolerance,'minimum_cable_force_N':tension,**balance})  # Preserve the precise failed physical equation and native stopping result before rejecting the whole history.
                raise RuntimeError(f'Dynamic physical gate failed residual{residual},minimumtension{tension}')  # Do not relabel invalid mechanics as training references.
            frame=np.array([ops.nodeDisp(n)+ops.nodeVel(n) for n in nodes],dtype=float)  # Read every actual native displacement, rotation, velocity, and angular velocity.
            acceleration=np.asarray([ops.nodeAccel(n) for n in nodes],dtype=float)  # Preserve actual native acceleration independently from learned outputs.
            audit={'time_s':t,'free_residual_equivalent_N':residual,'minimum_cable_force_N':tension,**balance}  # Keep the independent force and moment audit at this accepted time.
            saddle={'time_s':t,'supports':saddle_interfaces(m,reference_frames)}  # Keep all actual support motions, cable forces, and finite cut orientations.
            if storage=='hdf5':  # Persist every full native frame immediately without temporal or spatial downsampling.
                stream.append(t,frame,prescribed_wind,applied,acceleration,audit,saddle,np.asarray([ops.eleResponse(tag,'axialForce')[0] for tag in cable_ids],dtype=float))  # Preserve all native motion, external inputs, and cable forces in exact double precision.
            else:  # Retain the explicitly requested legacy small-case format.
                frames.append(frame)  # Preserve all native target components.
                wind_inputs.append(prescribed_wind)  # Preserve only exogenous wind as operator controls.
                loads.append(applied.copy())  # Preserve response-dependent force in a separate audit array.
                accelerations.append(acceleration)  # Retain actual complete acceleration history.
                cable_forces.append(np.asarray([ops.eleResponse(tag,'axialForce')[0] for tag in cable_ids],dtype=float))  # Retain every original cable and hanger response without selecting only extrema.
                times.append(t)  # Preserve every accepted physical time.
                audits.append(audit)  # Preserve every physical-equilibrium audit.
                saddles.append(saddle)  # Preserve every global-to-local interface state.
            print(json.dumps({'case_id':args.case_id,'step':step,'time':t,'residual_N':residual}),flush=True)  # Expose real accepted progress.
        substep_audit_file.close(); substep_audit_file=None  # Close the incremental internal audit before hashing and publishing the complete case.
        if storage=='hdf5':  # Publish a final artifact only after all requested native steps pass.
            dataset=stream.finish()  # Atomically rename the complete validated frame stream.
        else:  # Preserve explicit legacy npz interchange for small diagnostics.
            dataset=args.output/'fields.npz'  # Use the historical complete-case file identity.
            temporary=args.output/'fields.partial.npz'  # Keep interrupted compression distinct from completed labels.
            np.savez_compressed(temporary,**static,controls=np.array(wind_inputs),targets=np.array(frames),times=times,applied_force_moment=np.array(loads),acceleration=np.array(accelerations),cable_axial_force_N=np.array(cable_forces))  # Preserve every actual native value in the legacy route.
            temporary.replace(dataset)  # Publish the completed legacy dataset atomically.
        receipt={'case_id':args.case_id,'split':args.split,'quality':'VALID_CONVERGED','quality_status':'VALID_CONVERGED','dataset':str(dataset.resolve()),'dataset_sha256':file_sha256(dataset),'storage_format':storage,'solver':'OpenSees '+ops.version(),'source_input_sha256':eq['source_sha256'],'source_result_sha256':hashlib.sha256((args.output/'prestate/equilibrium_summary.json').read_bytes()).hexdigest(),'geometry_evidence_status':'DRAWING_DERIVED_ASSUMPTIONS','geometry_evidence_sha256':eq['source_sha256'],'model_assumptions':eq['physical_limitations']+['lagged partitioned quasi-steady loads; timestep sensitivity required','provisional mass-proportional damping C=0.02/s*M; no calibrated site damping data','wind force sampled at each exported frame endpoint and held piecewise constant over internal Newmark substeps'],'aerodynamic_evidence':evidence,'time_steps':args.steps,'dt_s':args.dt,'internal_substeps':internal_substeps,'native_substep_dt_s':args.dt/internal_substeps,'wind_hold':'piecewise_constant_over_export_frame','wind_sampling':'frame_end_time','export_sampling':'outer_frames_only','acceptance_gate_scope':'all_native_substeps_and_exported_endpoints','wind_speed_parameter_m_s':args.speed,'node_count':len(nodes),'source_code_sha256':snapshots[Path(__file__).name],'source_snapshots_sha256':snapshots,'substep_audits_file':str(substep_audit_path.resolve()),'substep_audits_sha256':file_sha256(substep_audit_path),'relation_types':groups,'relation_reference_measures':{str(i):{'measure':'source_nodal_lumped_mass_tonne','reference_value':1.0} for i in range(len(groups))},'control_channels':['external_transverse_wind_m_s','external_vertical_wind_m_s'],'output_channels':['displacement_x_mm','displacement_y_mm','displacement_z_mm','rotation_x_rad','rotation_y_rad','rotation_z_rad','velocity_x_mm_s','velocity_y_mm_s','velocity_z_mm_s','angular_velocity_x_rad_s','angular_velocity_y_rad_s','angular_velocity_z_rad_s'],'force_input_policy':'Response-dependent aerodynamic force/moment stored only in applied_force_moment audit array; never an operator input','output_mask_policy':'Translation and velocity observed on all nodes; rotation and angular velocity observed only on actual shell/beam nodes','step_audits':audits if storage=='npz' else None,'saddle_motion':saddles if storage=='npz' else None,'physical_validation':'NOT_REAL_BRIDGE_WIND_COEFFICIENTS_OR_FATIGUE_LIFE','training_eligible':args.split=='train'}  # Keep numerical success distinct from aerodynamic/engineering validation; integration references are fixed across mesh refinements.
        receipt['shell_element']=eq.get('shell_element','ShellNLDKGQ')  # 将实际完成预平衡和动力的非线性壳公式写入完整回执，旧模型默认名称仅用于兼容。
        receipt.update(native_convergence_test=native_test_type,native_test_tolerance=native_test_tolerance)  # 完整历史明确记录内部停止准则；不能把位移准则当作力收敛证明。
        if storage=='hdf5':  # Bind the streamed interface and independent-balance histories to this complete case.
            receipt.update(step_audits_file=str(stream.audit_path.resolve()),step_audits_sha256=file_sha256(stream.audit_path),saddle_motion_file=str(stream.saddle_path.resolve()),saddle_motion_sha256=file_sha256(stream.saddle_path),expected_frames=args.steps+1,stream_status_file=str(stream.status_path.resolve()))  # Retain complete evidence paths and exact byte identities without huge JSON arrays.
            del receipt['step_audits'],receipt['saddle_motion']  # Keep a single unambiguous location for each streamed history.
        atomic_json(args.output/'case_manifest.json',receipt)  # Publish complete-case metadata atomically only after every requested step passes.
        return receipt  # Return actual case evidence for dataset assembly.
    except BaseException as error:  # Include explicit interruption so partial histories remain clearly rejected.
        if substep_audit_file is not None:  # Close the partial internal audit before publishing failure metadata.
            substep_audit_file.close()  # Flush all observed internal states to disk.
        if stream is not None:  # Preserve already accepted numerical frames when a stream exists.
            stream.abort(error)  # Mark the incomplete artifact failed and close its actual file handles.
        atomic_json(args.output/'case_failure.json',{'case_id':args.case_id,'quality_status':'REJECTED','training_eligible':False,'error':str(error),'accepted_frames':0 if stream is None else stream.frames})  # Preserve observed failure without publishing a successful case manifest.
        raise  # Keep the actual native or I/O failure visible to orchestration.
if __name__=='__main__':  # Run one whole-history experiment from a frozen external configuration.
    p=argparse.ArgumentParser()  # Define explicit case and numerical settings.
    p.add_argument('--source',type=Path,required=True)  # Select authentic whole-bridge source.
    p.add_argument('--state',type=Path,required=True)  # Select authenticated F3 cable state.
    p.add_argument('--output',type=Path,required=True)  # Keep independent-case results isolated.
    p.add_argument('--subdivision',type=int,default=4)  # Default to actual dense spatial refinement.
    p.add_argument('--case-id',required=True)  # Preserve one complete scenario identity.
    p.add_argument('--split',choices=['train','validation','test'],required=True)  # Freeze partitions by complete history.
    p.add_argument('--steps',type=int,default=40)  # Control complete physical history length.
    p.add_argument('--dt',type=float,default=.025)  # Set actual structural integration time step.
    p.add_argument('--speed',type=float,default=15.)  # Set provisional nonstationary wind speed parameter.
    p.add_argument('--seed',type=int,default=0)  # Set deterministic whole-history phase.
    p.add_argument('--storage',choices=['hdf5','npz'],default='hdf5')  # Default to lossless full-mesh streaming for long physical histories.
    p.add_argument('--detailed-model',dest='detailed_model',action='store_true',default=True)  # Default explicitly to actual source-dimensional panels, stiffeners, and corrected cable planes.
    p.add_argument('--shell-element',choices=['ShellNLDKGQ','ASDShellQ4'],default=DEFAULT_SHELL_ELEMENT)  # 默认保留原壳；替代共回转公式必须显式选择，且不能绕过相容性检查。
    p.add_argument('--initial-displacement-tolerance',type=float,default=DEFAULT_INITIAL_DISPLACEMENT_TOLERANCE)  # 与程序接口使用同一个初始预测阈值，最终静力和动力力门槛不变。
    p.add_argument('--native-force-tolerance',type=float,default=.002)  # 保留显式NormUnbalance实验原有默认数值；位移模式不把此值误作位移阈值。
    p.add_argument('--native-convergence-test',choices=['NormUnbalance','NormDispIncr'],default=DEFAULT_NATIVE_CONVERGENCE_TEST)  # 默认保留原力范数；显式位移停止同样需要完整独立物理验收。
    p.add_argument('--native-displacement-tolerance',type=float,default=1e-8)  # 位移准则使用原生mm/rad增量阈值，允许更严值但禁止超过1e-8。
    p.add_argument('--internal-substeps',type=int,default=2)  # Integrate each exported frame interval with two real Newmark substeps while preserving the declared output dt.
    p.add_argument('--legacy-model',dest='detailed_model',action='store_false')  # Require an explicit diagnostic override before using the historical equivalent-deck model.
    args=p.parse_args()  # Parse the complete native experiment contract.
    execute(args)  # Compute actual full-field dynamic FEM labels.
