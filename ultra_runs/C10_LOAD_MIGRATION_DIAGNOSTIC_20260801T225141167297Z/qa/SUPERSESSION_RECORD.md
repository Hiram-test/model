# 未启动运行包作废记录

该目录从未启动 MAPDL。原准备账本 `artifact_hashes.sha256` 保留为当时 27 项准备态的原始快照，其 SHA-256 为 `9408f4c44c43e83fc7a93cd4e17e1963330bc5b10deb7eeb16637fc4584f81dd`；它不再代表目录当前全部字节，也不得再作为“当前准备账本通过”的启动依据。

作废原因：准备器命令行帮助中 `%` 未转义导致 `--help` 崩溃，且自适应模式帮助文字错误描述了 K5。数值输入本身未被执行，现已由新的准备器源码替代。根状态与清单明确设置 `launch_allowed_for_diagnostic=false`，本目录永久禁止启动。

为保留原封存事实，原账本没有被覆盖。作废时仅显式改写了下列三项权限/说明工件：

| 工件 | 原准备账本 SHA-256 | 当前作废态 SHA-256 |
|---|---|---|
| `C10_static_status.json` | `af65d0934fa72d57043d2ef2b614a94dcc32f252b945d9bbcdff275cf78c91dd` | `733cb1562a0dc5821e339ddc7ed242458f1be2d1a4c7776c3b772259f382fabd` |
| `manifest.json` | `eb72956e51fcd6f46df29f534b0cb586cb960b9acaacf25dc20ee8d5664f31fc` | `c94c3dcebf2e22c8171c09f97f6e195e461394a386b98680860ca6713c460e47` |
| `result_packet.md` | `dabcc8d7b32d95798a46091114245f4fee5a2d66912507f69c79859f8ffb0012` | `888a21b75303909c2b71db84fe6b1c4237e3a1a9f0f060265e103849f3c52d75` |

本记录只解释作废后的双状态，不恢复启动权限，也不改变任何求解输入或历史结果。
