# 理论：实测误差形式化参数更新

## 1. 三类输入对象

图纸视觉语义形成结构对象：

\[
\mathcal S=\{L,\;\mathcal B,\;q(x),\;I_d(x),\;\Theta,\;\mathcal X_s\}
\]

其中，\(L\) 为跨度，\(\mathcal B\) 为边界条件，\(q\) 为荷载，\(I_d\) 为图纸截面惯性矩，\(\Theta\) 为允许更新的参数类型，\(\mathcal X_s\) 为测点位置。

点云形成实际几何对象：

\[
\mathcal G^{pc}=\{L^{pc},\;I^{pc}(x),\;z_0^{pc}(x)\}
\]

传感器形成有界观测对象：

\[
y_i\in[\underline y_i,\overline y_i]
=[y_i^m-\varepsilon_i,\;y_i^m+\varepsilon_i]
\]

程序不为 \(\varepsilon_i\) 指定概率分布。

## 2. 几何优先

简支梁静力方程为：

\[
-w''(x)=\frac{M(x)}{E I(x)},
\qquad
w(0)=w(L)=0
\]

静定梁的弯矩 \(M(x)\) 由图纸荷载和边界确定。参数更新前，使用点云的 \(I^{pc}(x)\) 替换图纸名义值 \(I_d(x)\)。因此材料参数不会吸收已被点云直接观测到的几何偏差。

## 3. 参数响应签名

定义参考模量 \(E_r\)，以及无量纲柔度参数：

\[
p=\frac{E_r}{E}
\]

在几何场固定时，线弹性静力响应满足：

\[
w(x;E,I^{pc})=p\,\psi(x;I^{pc})
\]

其中 \(\psi\) 是以 \(E=E_r\) 计算的参考响应。当前模型参数为：

\[
p_k=\frac{E_r}{E_k}
\]

当前计算响应为：

\[
w_k(x_i)=p_k\psi_i
\]

## 4. 从实测误差到参数可行区间

对每个内部测点，真实响应必须落入测量区间：

\[
\underline y_i
\le
(p_k+\Delta p)\psi_i
\le
\overline y_i
\]

因此每个测点直接给出一个参数增量区间：

\[
\mathcal U_i=
\left[
\min\left(
\frac{\underline y_i-p_k\psi_i}{\psi_i},
\frac{\overline y_i-p_k\psi_i}{\psi_i}
\right),
\max\left(
\frac{\underline y_i-p_k\psi_i}{\psi_i},
\frac{\overline y_i-p_k\psi_i}{\psi_i}
\right)
\right]
\]

全局模量更新允许集为：

\[
\mathcal U=\bigcap_i\mathcal U_i
\]

判定规则：

\[
\mathcal U=\varnothing
\quad\Longrightarrow\quad
\text{拒绝全局弹性模量更新}
\]

\[
\mathcal U\neq\varnothing
\quad\Longrightarrow\quad
p_{k+1}\in p_k+\mathcal U
\]

对应的弹性模量区间为：

\[
E_{k+1}
\in
\left[
\frac{E_r}{\overline p_{k+1}},
\frac{E_r}{\underline p_{k+1}}
\right]
\]

程序使用可行区间中点作为可执行代表值，同时保留完整区间。这里不存在残差范数目标函数。

## 5. 误差形式的前置条件

全局弹性模量更新前必须满足：

1. 两个支座测量区间均包含零位移；
2. 图纸与荷载声明镜像对称时，成对测点的测量区间必须相交；
3. 点云截面场必须与该对称关系一致；
4. 点云跨度必须与图纸坐标合同一致；
5. 所有内部测点导出的 \(\mathcal U_i\) 必须具有公共交集。

这些条件将“误差大小”改写为可判定的边界形式、对称形式、几何形式和力学响应签名。

## 6. 后置条件

选择 \(p_{k+1}\) 后，逐测点验证：

\[
\underline y_i
\le
p_{k+1}\psi_i
\le
\overline y_i
\]

全部成立时，目标误差形式已在测量界内被消去。任何一项失败，更新凭证无效。

## 7. 多参数扩展

当参数分区为 \(p_1,\ldots,p_m\) 时：

\[
\mathbf y=\mathbf \Psi\mathbf p
\]

传感器误差带形成线性不等式：

\[
\underline{\mathbf y}
\le
\mathbf \Psi(\mathbf p_k+\Delta\mathbf p)
\le
\overline{\mathbf y}
\]

研究重点转为：如何由图纸构件语义和点云几何生成具有力学含义的 \(\mathbf\Psi\)，以及如何判定可行集为空、唯一、区间化或不可辨识。数值求解器只负责可行性，不负责寻找“误差最小”的参数。
