# V2 候选输入恢复补包

[下载输入快照](https://chatgpt.com/library?file_id=libfile_f9585c88bbb88191bfe84ec676e0058b&account_id=personal) · [原文件清单](https://chatgpt.com/library?file_id=libfile_fcf96275ed3c8191a8c6bde4154401b6&account_id=personal) · [完整性回执](https://chatgpt.com/library?file_id=libfile_f9811fd993b08191a5beedc07c306142&account_id=personal)

已闭合 acquisition 的输入依赖归档完成，不新增训练、有限元标签或求解。详见 [恢复说明](v2_reproduce/acquisition_inputs/README.md)、[逐文件清单](v2_reproduce/acquisition_inputs/snapshot_manifest.json) 和 [独立复核](v2_reproduce/acquisition_inputs/independent_package_review.json)。

`closed_acquisition_inputs_snapshot.zip`：3,970,999 B；SHA256 `73020bad52b73fa708a1b2749de41f076a37c9b1dc2a2f0e6397271f15bbf21b`。190 个成员完整 CRC/SHA/长度核验通过；原 186 文件及 8 个闭合标记前后 SHA/stat 稳定。打包峰 RSS 16,121,856 B，独立复核峰 13,950,976 B，均为 1 MiB 流式标准库进程。

补齐 16 个钢筋候选原 input-only NPZ 及相关记录的归档缺口；保留两族全部 32 份原 prepared 记录和输入图。摩擦 `fields.npz` 是零未来响应占位的输入容器，不能用作 FEM 标签。原数组本次未解码；input-only 语义由原记录和生产源码支撑。9 个摩擦候选从未落盘独立 deck，缺口如实记录，未重生成。

恢复 helper 已实际完成只读 verify-only（186 文件通过）；未实际恢复到原运行路径。必须使用隔离新目录，保留原字节；路径迁移或新计算需新 run 身份并重新冻结。完整 V1/运行时依赖另见 [V2_REPRODUCE.md](V2_REPRODUCE.md)。
