# 변이 표기 정규화·의미 동등성 parser contract 감사

## 한 문장 정의

문자열 표기가 달라도 같은 생물학적 변이 사건이면 하나의 canonical event로
정규화하고, 다른 사건은 분리하며, 의미가 불명확한 표기는 정상 단백질 잔기
위치로 억지 해석하지 않는다.

영문 명칭은 **mutation notation normalization and semantic equivalence
validation**이다.

## 자동 fixture 계약

| 목적 | 입력 사례 | 기대 결과 |
|---|---|---|
| 같은 stop-gain 통합 | `R213X`, `R213*`, `R213Ter` | 모두 `R213*`, `stop_gain` |
| 다른 사건 분리 | `R213H`, `R213X`, `R213del` | missense·stop_gain·deletion 별도 유지 |
| missense | `R132H`, `V600E` | reference·position·alternate 보존 |
| synonymous | `D623D`, `G592G` | synonymous 유지 |
| frameshift | `K16fs`, `P700fs` | frameshift, 시작 residue 사용 가능 |
| range replacement | `91_92NH>KY` | range_replacement, position은 일반 단일 residue로 사용하지 않음 |
| deletion | `249del`, `R649del` | inframe_deletion, 기능 효과는 추정하지 않음 |
| 불명확 표기 격리 | `-287fs`, `*261*` | other_unmappable, 빈 position, position-ineligible |

모든 대표 token은 normalize한 결과를 다시 parse해도 결과가 변하지 않는
idempotence 테스트를 통과한다.

## 실제 데이터 compact audit

환자 ID·SUBCLASS·Public LB를 사용하거나 저장하지 않고 전체 token occurrence와
vocabulary만 집계했다.

| 항목 | train | test |
|---|---:|---:|
| token occurrence | 255,164 | 337,512 |
| unique raw token | 115,200 | 134,224 |
| unique canonical token | 115,200 | 133,300 |
| canonical vocabulary 감소 | 0 | 924 |
| position-ineligible occurrence | 414 | 4,734 |
| X 표기 단순 stop-gain | 0 | 14,355 |
| Ter 표기 단순 stop-gain | 0 | 0 |
| 음수/upstream 부분 표기 | 75 | 19 |
| `*숫자*` 양쪽 별표 | 99 | 13 |

test에서 `R213X`와 `R213*`처럼 서로 다른 raw form이 같은 canonical token으로
합쳐지는 실제 사례를 확인했다. train에는 X-stop이 0건이라 이 문제는 일반
OOF에서 직접 드러나지 않는 annotation blind spot이다.

## 해석과 제한

- parser 의미 계약이 옳다는 것과 특정 feature representation의 모델 성능은
  별개다. EXP-355·359의 기각은 이 정규화 계약을 반증하지 않는다.
- 기존 공식 parser v1과 과거 실험 결과를 소급 변경하지 않는다.
- parser v2를 기본 Feature Spec으로 승격하려면 별도 Experiment Issue에서
  한 가지 변경만 적용해 canonical 5-fold로 검증해야 한다.
- `other_unmappable`은 오류·passenger mutation이라는 뜻이 아니라, 현재 문자열만
  가지고 안전하게 단백질 사건과 위치를 확정할 수 없다는 뜻이다.

## 재현

```bash
uv run pytest -q tests/test_robust_mutation_parser.py
uv run python scripts/audit_mutation_notation_semantics.py
```

- compact 원본 결과: [`audit.json`](audit.json)
- 관련 상위 Issue: [#360](https://github.com/fabxoe/open_cancer/issues/360)
- 영향 경로 감사: [#353](https://github.com/fabxoe/open_cancer/issues/353)
- 계약 Task: [#364](https://github.com/fabxoe/open_cancer/issues/364)
