# Parser v4 환자별 canonical event-token 계약

## 목적

`canonical_event_tokenizer.py`는 parser v4가 판정한 단백질 변이 사건을
환자별 순서 불변 multiset으로 변환합니다. 이 계층은 모델이 아니며 label,
validation, test prevalence, Public LB를 읽지 않습니다.

```text
raw gene cell
→ parser v4 canonical event
→ bounded semantic tokens
→ fold-train vocabulary·support 선택(T1 이후)
→ sparse linear / set model / ensemble
```

## 보존하는 의미

- 유전자와 `substitution`, `frameshift`, `deletion`, `insertion`,
  `duplication_candidate`, `delins`, range, unresolved family
- missense·no-change·nonsense와 `R>H`, `R>R`, `R>STOP` 같은 단일 잔기 치환
- 고정 폭 단백질 위치 구간과 range span
- deletion·insertion·delins·range의 고정 길이 bucket
- insertion·delins·range에 명시된 아미노산 조성 count
- 확정 가능한 한 글자 frameshift first-new residue
- partial·unresolved 문법 provenance
- 빈 gene cell과 명시적 `WT`의 차이

## 의도적으로 만들지 않는 의미

- arbitrary raw token 또는 긴 peptide 전체를 feature 이름으로 사용하지 않음
- `SDEL133fs`의 `DEL`처럼 compact frameshift에서 확정되지 않은 문자열을
  새 peptide로 간주하지 않음
- 종료 거리나 downstream frameshift peptide를 원문 없이 추정하지 않음
- 빈값을 WT로 변경하지 않음
- test에서 많이 보인다는 이유로 vocabulary를 선택하지 않음

## 불변성과 재현성

- gene column 입력 순서와 무관하게 token count를 정렬합니다.
- `R582X`, `R582Ter`, `R582*`는 같은 canonical semantic token을 만듭니다.
- vocabulary는 사전순으로 고정하고 tokenizer version과 함께 SHA-256을
  계산합니다.
- 공식 실험의 vocabulary는 해당 outer-train에서만 만들고 validation/test는
  transform-only로 처리합니다.
- position bin 기본 폭은 100이며 resolved config에 실제 폭을 기록해야 합니다.

## 다음 단계

Issue #531의 T1에서 이 API로 train/test 및 canonical fold별 다음 항목을
감사합니다.

- token family별 support와 vocabulary 크기
- validation/test OOV율
- 환자별 token 수와 긴 꼬리
- blank·partial·unresolved 분포
- 길이가 긴 peptide가 exact vocabulary로 유출되지 않았는지

T1은 분석 전용이며 점수를 만들지 않습니다. 공식 모델은 이 감사를 마친 뒤
별도 Experiment Issue에서 실행합니다.
