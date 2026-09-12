# 初应力词法门（交独立回读）

评估人：Cursor Grok 4.6。未向用户提问。  
门：新哈希的 `*INITIAL CONDITIONS` 必须是单元号+积分点+六 PK2，不能再是 ELSET+单轴。  
`82548e6a` 当失败现场不动。

## 两份文件

| 角色 | 路径 | SHA-256 | 词法 |
|---|---|---|---|
| 失败现场（不改） | `catwalk-fem/artifacts/zjg_catwalk_coarsened.inp` | `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da` | ELSET+单轴 |
| 新主 deck | `catwalk-fem/artifacts/zjg_catwalk_ccx221.inp` | `41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a` | 单元号+积分点+六 PK2 |

写入器：`catwalk-fem/pipeline/write_inp.py`（`format_pk2_stress_rows`）。不再发射 `E_FLOOR_ROPE, σ`。

## 独立回读命令

```bash
sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
python3 - << 'PY'
from pathlib import Path
for name in (
    "catwalk-fem/artifacts/zjg_catwalk_coarsened.inp",
    "catwalk-fem/artifacts/zjg_catwalk_ccx221.inp",
):
    lines = Path(name).read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("*INITIAL CONDITIONS") and "STRESS" in ln)
    print(name)
    for ln in lines[i:i+4]:
        print(" ", ln)
    print()
PY
```

本机刚跑过的结果（`eval/IC_GATE_INDEPENDENT_REREAD.json`）：

**82548e6a 第 90863–90865 行（未改）**

```
*INITIAL CONDITIONS, TYPE=STRESS
E_FLOOR_ROPE, 3.549611e+08
E_PORTAL_ROPE, 2.426295e+08
```

2 行，ELSET+单轴，0 行 §7.76。

**41fb3222 第 90873 行起**

```
*INITIAL CONDITIONS, TYPE=STRESS
1, 1, 1.439957e+08, 0.000000e+00, 2.109655e+08, 0.000000e+00, 1.742932e+08, 0.000000e+00
```

204 208 行全部是 8 字段；首字段为单元号；积分点 1–8；ELSET+单轴 0 行。  
25526 个索单元 × 8 积分点。首行迹 `tr(S)=3.549612e+08` = \(\sigma_{\mathrm{floor}}\)。  
回读前后冻结哈希仍是 `82548e6a…276ab6da`。

## 判定

| 项 | 结果 |
|---|---|
| 82548e6a 未改 | 成立 |
| 82548e6a 仍是 ELSET+单轴 | 成立（失败现场） |
| 新哈希 ≠ 82548e6a | 成立 |
| 新哈希全是单元号+积分点+六 PK2 | 成立 |
| 新哈希还有 ELSET+单轴 | 不成立（0 行） |

这道门只核词法。不把切线奇异或未收敛静力写进这道门。
