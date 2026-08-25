# 自评：974211b2 线形叠层方案（送审，不求解）

评估人：Cursor Grok 4.6。未向用户提问。不开新 PR。不合并。不 push main。不改任何 `.inp` 字节。

| 用户句 | 本岗 | 依据 |
|---|---|---|
| 先出方案，体会意图，不是贴词执行 | **成立** | `eval/SCHEME_974211b2_LINE_OVERLAY.md`：八块来自 MCT 组，不是图像格子；PSO 只吃残差 |
| 逻辑主干 + 每步实验设置 | **成立** | N00–N18 顺序未改；每步只加本桥设置 |
| 可改良 | **成立** | 影响矩阵先于 PSO；矩阵够则 PSO=`NOT_APPLICABLE` |
| 只加已给路径 | **成立** | 宿主 / MCT / S10.db / 附件2-3 / 19 skill |
| 主仍 974211b2，线形叠在上面，不换主 | **成立** | 宿主 sha256 仍 `974211b2…e0267fd1`；overlay sidecar 本轮未写 |
| 760c0ee4 不动 | **成立** | `zjg_catwalk_cleared.inp` 仍 `760c0ee4…b0585de9` |
| 不编 | **成立** | S10 索力保持 null；针点从宿主节点表复算，偏差 0 |
| 不扭到 demo-rl-calculix | **成立** | 方案明文禁止 |
| 落到 #19 能读到的路径 | **成立** | `catwalk-fem/eval/SCHEME_974211b2_LINE_OVERLAY.{md,json}` |

当场：

```
python3 catwalk-fem/tests/test_scheme_974211b2_overlay.py
sha256sum catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_cleared.inp
```

本轮不交 CalculiX。不是已求解。
