# 第二章 PDF 成稿错误日志

## E-PDF-001 - 编辑登记脚本相对路径不存在

- 时间：2026-08-30（UTC）
- 动作：首次执行 PDF 编辑登记命令。
- 错误：`<RUN_ROOT>/container_tools/mark_artifact_operation_started.mjs` 不存在，Node 返回 `MODULE_NOT_FOUND`。
- 影响：登记未成功；尚未创建或修改任何 PDF 源文件或成品。
- 处置：已定位 PDF 技能所附脚本的绝对路径，随后仅执行一次成功登记。


## E-PDF-BUILD-20260829T182209Z

- 时间：2026-08-29T18:22:09Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${BUILD_DIR}" "${SCRIPT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-BUILD-20260829T182249Z

- 时间：2026-08-29T18:22:49Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${BUILD_DIR}" "${SCRIPT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-BUILD-20260829T182305Z

- 时间：2026-08-29T18:23:05Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${BUILD_DIR}" "${SCRIPT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-BUILD-20260829T182410Z

- 时间：2026-08-29T18:24:10Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${BUILD_DIR}" "${SCRIPT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-BUILD-20260829T182455Z

- 时间：2026-08-29T18:24:55Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${BUILD_DIR}" "${SCRIPT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-RENDER-001 - 临时渲染目录清理命令被策略拒绝

- 时间：2026-08-30（UTC）
- 动作：准备将 24 页排版骨架渲染为 PNG 联系表。
- 错误：命令含 `rm -rf` 清理临时渲染目录，被执行策略拒绝，未运行 Poppler。
- 影响：PDF 与既有文件均未改变。
- 处置：改用 `mktemp -d` 创建全新临时目录，不执行删除操作。

## E-PDF-QA-001 - PDF 链接注释首次枚举未解引用

- 时间：2026-08-30（UTC）
- 动作：用 pypdf 统计目录书签、命名目标和页面链接注释。
- 错误：页面 `/Annots` 为 `IndirectObject`，直接调用 `len()` 触发 `TypeError`。
- 影响：已成功读取 24 页、7 个顶层书签和 78 个命名目标；链接总数尚未由该次命令得到，PDF 未改变。
- 处置：显式解引用 `/Annots` 后重新统计，并继续验证链接对象。

## E-PDF-BUILD-20260829T182921Z

- 时间：2026-08-29T18:29:21Z
- 退出码：1
- 失败命令：`pdfinfo "${OUTPUT_PDF}" > "${BUILD_DIR}/pdfinfo.txt"`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-I08-PATH-001

- 时间：2026-08-29T19:00:00Z
- 错误：首次批量 SHA 复核将协方差和总账误写为 `I08_CASE_MODAL_COVARIANCE.npy` 与 `I08_POSTPROCESS_SHA256SUMS.txt`；实际冻结文件名为 `I08_43CASE_MODAL_COVARIANCE.npz` 与 `I08_43CASE_SHA256SUMS.txt`。
- 影响：`sha256sum` 对两个不存在路径返回非零，后续 `&&` 读取未执行；未修改任何结果文件。
- 处置：通过只读文件枚举确认真实冻结文件名，并以精确路径重新执行 SHA、总账和 acceptance 复核。

## E-PDF-TEXT-SHA-001

- 时间：2026-08-29T19:10:00Z
- 错误：给 source-basis SHA 添加可换行标记时发生手工转录错误，暂时写入了错误长度的字符串。
- 影响：错误仅存在于未编译的 TeX 工作稿，未进入任何 PDF 或图表。
- 处置：立即按 `FULLMCT_ROM_BUILD_AUDIT.json` 恢复精确 SHA `2465489342b93033c86179b13fe9004a943fe639c3c487ececb9cd87a4f960a2`；最终输入生成器仍需独立校验该锁。

## E-PDF-BUILD-20260829T192548Z

- 时间：2026-08-29T19:25:48Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${TEMP_BUILD_DIR}" "${SOURCE_SNAPSHOT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-PATCH-001

- 时间：2026-08-29T19:27:00Z
- 错误：首次修复终态长字符串时，补丁上下文误用了双反斜杠表示，未匹配 `String.raw` 模板中的源码。
- 影响：补丁原子失败，目标文件未被修改。
- 处置：读取精确源码行后，以单反斜杠上下文重新应用，并改用 `\path{}` 提供可断行终态。

## E-PDF-BUILD-20260829T192727Z

- 时间：2026-08-29T19:27:27Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${TEMP_BUILD_DIR}" "${SOURCE_SNAPSHOT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-BUILD-20260829T192821Z

- 时间：2026-08-29T19:28:21Z
- 退出码：1
- 失败命令：`xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="${TEMP_BUILD_DIR}" "${SOURCE_SNAPSHOT_DIR}/report_main.tex" > "${BUILD_DIR}/xelatex-pass${pass}.log" 2>&1`
- 日志：`<RUN_ROOT>/output/pdf/chapter2_work/build/xelatex-pass*.log`

## E-PDF-QA-20260830T043400Z - qpdf 不可用

- 时间：2026-08-30T04:34:00Z
- 动作：对 30 页最终预检 PDF 执行附加对象结构检查。
- 错误：运行环境未安装 `qpdf`，命令返回 `command not found`；此前的 18--24 页 Poppler 渲染已成功完成。
- 影响：未修改 PDF 或冻结计算产物；该项不是交付门的唯一检查。
- 处置：继续使用 `pdfinfo`、`pdffonts`、`pdftotext`、Poppler 全页渲染及 PDF 解析器完成独立结构与视觉复核。

## E-PDF-QA-TERMINOLOGY-001

- 时间：2026-08-30T04:38:00Z
- 错误：首个已发布版本在否定句中仍出现“容量 PASS”字样，虽用于声明“不属于容量 PASS”，仍不满足最终禁词扫描的零命中要求。
- 影响：冻结数值、图表和计算链未受影响；该版本不作为最终交付件。
- 处置：改写为“不构成规范容量验算结论”，以新版本化文件名 `..._FINAL_R1.pdf` 重新执行完整三遍排版、原子发布及双轮稳定性复核。
