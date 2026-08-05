# Parser contract v4 계층·fixture catalog

Issue #387은 기존 공식 실험을 소급 변경하지 않고 새 parser 사용 시 필요한 세
계층을 독립적으로 고정한다.

```text
notation normalizer 4.0.0
semantic router 4.0.0
feature adapter 4.0.0-opt-in
```

통합 router의 우선순위는 다음과 같다.

```text
frameshift → delins → deletion → insertion → substitution → range replacement
```

따라서 `SDEL133fs`는 deletion이 아니고, `delins`는 deletion과 insertion에 이중
집계되지 않는다. Insertion을 tandem duplication으로 확정하는 일은 token-only
router가 아니라 fixed-reference adapter가 담당한다.

[`fixtures.json`](fixtures.json)은 팀이 실제 train/test 감사에서 확인한 사례와
팀 검토 사례를 저장한다. raw token, 기대 route/event/position, 확정 수준과 모호성
사유를 보존하며 schema 검증과 회귀 테스트를 거친다. `K176delins<187 aa>` 장문
alternate도 원문 전체를 fixture로 보존해 lossless routing을 검증한다.

새 공식 runner가 이 계약을 사용하려면 resolved config에 다음을 모두 기록한다.

```yaml
parser_contract:
  notation_normalizer_version: 4.0.0
  semantic_parser_version: 4.0.0
  feature_adapter_version: 4.0.0-opt-in
  fixture_catalog_sha256: <실제 fixtures.json SHA-256>
  fixture_schema_version: 1.0.0
```

필드 누락이나 catalog hash 불일치는 `validate_resolved_parser_contract`에서 실패한다.
과거 runner와 Feature Spec v1은 이 opt-in 계약을 사용하지 않으며 변경되지 않는다.

Compact [`audit.json`](audit.json)은 fixture·schema hash, route/module별 수와 robust
v3 대비 v4 의미 차이를 기록한다. 다음 명령을 두 번 실행해 동일 SHA-256인지
확인한다.

```bash
uv run python scripts/audit_parser_contract_v4.py
```
