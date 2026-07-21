# 工件统一封装契约

所有节点输出采用同一 envelope。节点可以在 `data` 中放置自身业务结构，envelope 字段保持一致。

```json
{
  "artifactType": "component_inventory",
  "schemaVersion": "1.0.0",
  "projectId": "PRJ-001",
  "runId": "RUN-20260721-001",
  "artifactId": "ART-000031",
  "createdAt": "2026-07-21T10:00:00Z",
  "createdBy": {
    "skill": "bridge-structural-semantic-inventory",
    "skillVersion": "1.0.0",
    "toolchain": []
  },
  "inputArtifacts": [
    {"artifactId": "ART-000025", "sha256": "..."}
  ],
  "status": "PASS",
  "gateId": "G4",
  "unitsPolicy": "UNIT-POLICY-001",
  "coordinateSystemId": "CS-GLOBAL",
  "sourceRefs": [],
  "assumptionRefs": [],
  "issueRefs": [],
  "approvals": [],
  "data": {}
}
```

## 强制规则

1. `projectId` 和 `runId` 在整个 run 内保持一致。
2. `artifactId` 永久唯一，修订产生新 ID。
3. `inputArtifacts` 保存直接上游工件的哈希；禁止只保存文件名。
4. `status` 只能取 `PASS`、`PASS_WITH_BOUNDS`、`BLOCKED`、`NOT_APPLICABLE`。
5. `data` 中每个模型对象使用稳定 ID，并带 `sourceRefs` 或 `assumptionRefs`。
6. 工件不可原位修改。修订通过 `supersedesArtifactId` 建立版本链。
7. 时间使用 ISO 8601 UTC。
8. 工具、求解器、解析器和脚本版本写入 `createdBy.toolchain`。
9. `approvals` 记录角色、人员、时间、范围和签名哈希。
10. 下游只读取已通过 schema 校验且 gate 允许继续的工件。
