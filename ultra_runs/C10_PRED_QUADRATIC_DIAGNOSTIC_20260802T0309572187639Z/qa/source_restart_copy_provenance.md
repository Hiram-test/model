# 冻结重启源复制对账

| 类型 | 来源 SHA-256 | 副本 SHA-256 | 字节数 | 对账 |
|:---|:---|:---|---:|:---:|
| R001 | `a1aa905c2393daddb0e0885cd0e4bbda8b3b6b9729617508942989f4cffe4218` | `a1aa905c2393daddb0e0885cd0e4bbda8b3b6b9729617508942989f4cffe4218` | 867,893,248 | PASS |
| R002 | `8ac2cc008f8020d5cd0e15abfe4d0f7f23d5f3b315d3f44a4433777270ac324f` | `8ac2cc008f8020d5cd0e15abfe4d0f7f23d5f3b315d3f44a4433777270ac324f` | 878,837,760 | PASS |
| RDB | `f1cbbdad9ced630e967030c670780f7b36568218330836fa9ce51df39e2c168a` | `f1cbbdad9ced630e967030c670780f7b36568218330836fa9ce51df39e2c168a` | 205,389,824 | PASS |
| LDHI | `9ff90084693388cc33232d19b17d9ef8f0183aabce77be3bc6b1f0869a19de3d` | `9ff90084693388cc33232d19b17d9ef8f0183aabce77be3bc6b1f0869a19de3d` | 1,873,942 | PASS |
| RST | `66d595e30e9c4dffcc85927cb972e4409bccbd381b9eb6a1c4c11dfcbf3570ee` | `66d595e30e9c4dffcc85927cb972e4409bccbd381b9eb6a1c4c11dfcbf3570ee` | 531,628,032 | PASS |

五项来源哈希均与冻结来源运行的 `artifact_hashes_diagnostic_sufficiency_final.sha256` 一致；复制后逐项重新读取全部字节计算 SHA-256，五项全部闭合。
