# Annotation-invariant mutation parser v2

이 문서는 Issue #352에서 구현한 선택형 parser·feature contract를 설명한다. 기존
공식 실험은 `mutation_features.py`의 parser v1을 그대로 사용하며 결과를 다시
해석하거나 변경하지 않는다. parser v2는 별도 Experiment Issue에서 명시적으로
활성화했을 때만 사용한다.

## 왜 별도 parser가 필요한가

기존 parser는 단일 아미노산 치환과 `*` stop 표기, `fs` suffix를 제외한 모든
토큰을 `complex`로 분류한다. 실제 입력 감사에서는 test의 generic complex 토큰
중 `R213X`처럼 `X`로 기록된 stop-gain이 큰 비중을 차지했다. 이는 동일한
stop-gain 의미가 `*`와 `X` 표기 차이 때문에 서로 다른 피처로 들어가는 사례다.

parser v2는 다음 의미 범주를 target·Public·암종 빈도 없이 문자열 자체에서만
결정한다.

```text
missense
synonymous
stop_gain
frameshift
inframe_deletion
inframe_insertion
delins
range_replacement
duplication
other_unmappable
```

`X`와 `*`는 단순 치환의 alternate residue일 때만 `stop_gain`으로 통합한다.
`X127C`처럼 reference가 `X`인 표기는 reference amino acid를 알 수 없으므로
`other_unmappable`로 보존한다. transcript나 실제 발현 isoform을 추정하지 않는다.

## Robust representation 계약

- WT·빈값은 사건 없음으로 처리한다.
- token 순서, 공백, 대소문자 차이는 표현을 바꾸지 않는다.
- 의미 정규화 후 같은 exact token이 반복되면 한 번만 센다.
- sample 집계는 raw token 수가 아니라 해당 사건군이 관찰된 **서로 다른 유전자
  수**를 센다.
- 선택적으로 유전자×사건군 `any` indicator를 생성한다.
- position eligibility는 명확한 단일 치환·stop-gain과 시작점이 명시된
  frameshift에만 부여한다. Ensembl sequence 일치 여부는 기존 frozen annotation
  단계에서 별도로 검사한다.

## 해석 제한

- insertion·deletion 표기만으로 임상적 기능 효과를 판정하지 않는다.
- `other_unmappable`을 오류나 passenger mutation이라고 단정하지 않는다.
- train/test prevalence를 보고 범주나 임계값을 변경하지 않는다.
- parser v2는 아직 기본 Feature Spec이 아니다. canonical 5-fold 단일변수
  ablation을 통과해야 채택할 수 있다.

## 후속 실험 순서

1. raw `sample__complex_count` 대신 unique complex-event gene count 사용
2. generic complex gene indicator를 normalized event-family indicator로 교체
3. 채택된 robust representation과 EXP-313 Ensembl mask 조합

각 단계는 별도 Experiment Issue와 EXP-ID를 사용하고, 선행 결과를 보고 parser
범주를 다시 조정하지 않는다.
