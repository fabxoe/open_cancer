# Stop 표기 교란 parser·feature 불변성 감사

## 결론

동일한 stop-gain을 `*`, `X`, `Ter`로 표기만 바꿨을 때 parser v2 adapter가
동일한 Feature Factory 희소 행렬을 생성하는지 검증했다. 대표 fixture와 train
전체 vocabulary 모두 통과했다.

기존 v1에서는 train stop-gain 13,289건을 X로 표기할 경우 전부 `nonsense`에서
`complex`로 바뀐다. canonical adapter에서는 세 표기의 feature vector가 완전히
같다. 이는 현재 annotation blind spot을 코드 수준에서 재현하고 수정 계약을
검증한 결과다.

## 범위

- 상위 Issue: [#360](https://github.com/fabxoe/open_cancer/issues/360)
- 영향 감사: [#353](https://github.com/fabxoe/open_cancer/issues/353)
- Task: [#366](https://github.com/fabxoe/open_cancer/issues/366)
- 분석 전용이며 SUBCLASS·test·Public LB를 사용하지 않음
- 기존 parser v1·과거 Feature Spec·실험 결과는 변경하지 않음

## 실제 train 전수 감사

| 항목 | 결과 |
|---|---:|
| `A숫자*` occurrence | 13,289 |
| 고유 stop token | 6,245 |
| 관련 유전자 | 3,182 |
| v1에서 `*→X` 시 mutation type 변경 occurrence | 13,289 |
| canonical `*`/`X`/`Ter` 동등성 실패 | 0 |
| 음수 위치 표기 | 75 |
| `*숫자*` 표기 | 99 |

원본 환자 행·ID나 교란 CSV는 보관하지 않고 compact 집계만 저장했다.

## Feature Factory metamorphic test

작은 동일 데이터셋을 세 벌 만들어 오직 표기만 변경했다.

```text
R213*
R213X
R213Ter
```

### v1

- `R213*`: `sample__nonsense_count`, `GENE__nonsense`
- `R213X`: `sample__complex_count`, `GENE__complex`
- feature matrix 불일치 확인

### canonical adapter

- 세 입력의 전체 sparse feature matrix가 완전히 동일
- mutation presence·token multiplicity·position·나머지 v1 semantics 유지
- custom parser contract가 없으면 Feature Factory가 실행을 거부

결정적인 모델 함수 `prediction = model(feature_vector)`에서 feature vector가
같으면 예측 확률도 같다. 따라서 표기 차이로 인한 downstream prediction 차이를
feature 경계에서 차단한다.

## Position negative control

- `-287fs`: frameshift type은 유지, residue position은 빈 배열
- `*261*`: complex type은 유지, residue position은 빈 배열
- mutation 존재 자체를 삭제하지 않고 잘못된 숫자 위치만 차단

## 재현

```bash
uv run pytest -q tests/test_mutation_notation_invariance.py
uv run python scripts/audit_stop_notation_invariance.py
```

- compact 결과: [`audit.json`](audit.json)

## 다음 단계

1. 별도 Experiment Issue에서 EXP-223/229 계열에 stop notation adapter만 적용한다.
2. 위치 sanitation은 다른 Experiment Issue로 분리한다.
3. synonymous 제거도 별도 ablation으로 분리한다.
4. 한 번에 여러 parser·feature 규칙을 바꾸지 않는다.
