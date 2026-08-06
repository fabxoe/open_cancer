# Parser-v4 기반 compact clinical baseline 감사

## 목적

고득점 팀이 공유한 전처리 문서의 **피처 구조**를 재현하되, 해당 문서의
정규표현식 parser 결과를 정답으로 복제하지 않는다. 모든 사건 의미는 저장소의
parser v4로 판정하고 다음 네 블록으로 압축한다.

- fold-train에서 관찰된 유전자별 `mutated` indicator
- fold-train에서 관찰된 유전자별 `truncating` indicator
- fold-train 환자 5명 이상에서 관찰된 exact missense의 유전자별 indicator
- 환자별 사건·의미 family 요약 14개

`recurrent missense`의 exact key는 `gene:reference-position-alternate`이며 한 환자의
같은 token 반복이나 isoform multiplicity는 support를 중복 증가시키지 않는다.
validation과 test는 outer-train에서 확정한 vocabulary를 transform만 한다.

## 전체 train 감사 결과

| 항목 | 공유 문서 | parser v4 구현 |
|---|---:|---:|
| mutated 유전자 | 4,230 | 4,230 |
| truncating 유전자 | 3,671 | 3,663 |
| recurrent missense 유전자 | 91 | 91 |
| recurrent exact key | 230 | 230 |
| 전체 피처 | 8,005 | 7,998 |

7열 차이는 강제로 맞추지 않는다. 공유 문서의 `INFRAME_INDEL=3`은 실제 데이터의
deletion·insertion·delins를 심하게 누락한 것으로 보이며, parser-v4 의미 판정과
truncating 정의가 달라진 결과다. 구조는 재현하되 잘못된 분류 수까지 재현하지
않는 것이 이 작업의 계약이다.

## canonical outer-fold 차원

| fold | mutated | truncating | recurrent gene | recurrent key | 전체 피처 |
|---:|---:|---:|---:|---:|---:|
| 0 | 4,230 | 3,481 | 60 | 151 | 7,785 |
| 1 | 4,229 | 3,501 | 71 | 178 | 7,815 |
| 2 | 4,230 | 3,477 | 65 | 172 | 7,786 |
| 3 | 4,228 | 3,545 | 64 | 173 | 7,851 |
| 4 | 4,226 | 3,519 | 72 | 179 | 7,831 |

수치 원본과 feature-name SHA-256은 [`audit.json`](audit.json)에 있다.

## 해석 제한

- 이 문서의 결과는 피처 builder 감사이며 모델 점수가 아니다.
- target, test 빈도, Public LB는 vocabulary 선택에 사용하지 않았다.
- 임상적 truncating/pathogenic 판정이 아니라 제공 token에서 관측 가능한
  protein-consequence proxy다.
- 공식 성능은 후속 Experiment Issue의 canonical 5-fold OOF Macro F1로 판단한다.
