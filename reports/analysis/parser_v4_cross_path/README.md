# Parser v4 compatibility·cross-path 감사

> Issue: [#429](https://github.com/fabxoe/open_cancer/issues/429)
>
> 이 결과는 과거 5-family와 새 native representation의 연결을 검증하는 QC이며
> 모델 학습이나 baseline 점수가 아닙니다.

## 검사 내용

- 모든 새 parser 소비자가 `CanonicalGeneCell`과 canonical event SHA-256을 공유
- stop alias `*`, `X`, `Ter`가 동일 canonical identity를 가짐
- v4 event를 과거 다섯 family로 결정적으로 재투영
- compatibility feature 이름·순서가 기존 sample count와 gene type 열에 일치
- mutation presence와 missing/base feature는 교체하지 않음
- 기존 regex 소비자는 과거 실험 계보에서만 허용

## Compatibility mapping

```text
substitution missense  -> missense
substitution no_change -> synonymous
substitution nonsense  -> nonsense
frameshift             -> frameshift
deletion/insertion/delins/range/unresolved -> complex
```

Compatibility adapter의 출력은 sample type count 5개와 유전자별 type indicator
`4,384 × 5`개, 총 `21,925`개입니다. N4-C에서는 기존 동일 이름 열을 drop한 뒤
이 adapter의 열로 교체해야 하며, mutation presence는 계속 유지합니다.

## 실제 crosswalk 핵심 결과

- canonical normalized identity collision: train `0`, test `0`
- legacy와 v4 compatibility family가 달라진 token: train `78`, test `14,948`
- test의 가장 큰 변화: legacy `complex` → v4 `nonsense` `14,355`개
- train의 legacy `frameshift` → v4 `complex` `78`개는 signed/부분 표기를
  확정 frameshift로 강제하지 않은 결과

따라서 과거와 v4의 입력 차이는 train보다 test에서 훨씬 큽니다. 이는 v4 correctness를
되돌릴 근거가 아니라, 같은 환경에서 L/C/N 세 arm을 다시 실행해야 한다는 근거입니다.

## 해석 제한

Compatibility C arm은 v4의 풍부한 의미를 다시 `complex`로 압축하므로 실제 새
baseline이 아닙니다. 향후 `C-L`은 notation·routing 교체 감사에만, `N-C`는 native
semantic representation의 추가 효과 해석에만 사용합니다.

전체 수치와 crosswalk는 [`audit.json`](audit.json)에 기록합니다.

## 재실행

```bash
uv run python scripts/audit_parser_v4_cross_path.py
```
