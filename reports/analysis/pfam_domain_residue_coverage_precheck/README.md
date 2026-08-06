# Pfam 기능 도메인 잔기 indicator — 커버리지·중복성 사전 감사

> Issue #557의 target-independent 사전 검증 기록입니다. 새 모델 실험이나
> 점수를 만들지 않습니다. 실행 전 착수 여부를 판단하기 위한 감사이므로
> Experiment Issue와 EXP-ID를 만들지 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../../EXPERIMENT_HISTORY.md)입니다.

## 배경

다른 팀 공유 정보 중 "해당 위치가 기능 domain·결합 부위·활성 부위인지"가 이
프로젝트에서 유일하게 아직 안 다뤄진 bio-knowledge 축이었다(자세한 배경은
Issue #557 참고). 과거 Issue #174 검토에서 UniProt domain 주석은 "isoform·
transcript 정합성이 없어 위치를 안전하게 연결할 수 없다"는 이유로 보류됐는데,
N6(#493/PR #495)까지 오며 확보된 `competition_gene_isoform_index.json`(패널
4,370유전자 대표 isoform, MANE Select→canonical→other 우선순위 고정)로 그
차단 사유가 해소됐다.

## 방법

1. `scripts/fetch_ensembl_pfam_domain_catalog.py`: EXP-374/392의
   `isoform_relative_position.py`가 실제로 고르는 것과 **동일한 대표
   protein_id 선택 로직**(MANE Select > canonical > other-isoform)을
   재사용해, train+test의 trusted(MANE_MATCH·CANONICAL_MATCH·
   OTHER_ISOFORM_MATCH) (gene, token) 쌍이 실제로 resolve하는 대표 protein만
   추려 Ensembl BioMart(`hsapiens_gene_ensembl`, release 116)에서 Pfam 도메인
   좌표를 조회했다. 최초 설계는 유전자당 모든 isoform(평균 26개, 최대 300개,
   합계 111,778개)을 대상으로 해 매우 비효율적이었으나, 실제 필요한 대표
   protein은 **12,681개**뿐임을 확인하고 범위를 좁혔다.
2. `scripts/audit_pfam_domain_residue_coverage.py`: 위 12,681개 protein의
   Pfam 도메인 좌표와, 각 trusted (gene, token) 쌍의 대표 잔기 위치를 대조해
   도메인 내부/외부 여부를 계산하고, 같은 대표 protein·position에서 계산한
   기존 `isoform_relative_position`(EXP-327/374/392, 5-bin) 값과 교차표를
   만들었다.

두 스크립트 모두 SUBCLASS·test 분포·Public LB를 사용하지 않는다.

## 결과

- 대상 trusted (gene, token) 쌍: **437,784건**(train+test 고유 쌍)
- 도메인 catalog resolution coverage: **100%**(437,784/437,784) — 요청한
  (gene, token)이 선택한 대표 protein_id가 catalog에 모두 존재한다는 뜻이다.
  모든 residue가 Pfam domain 내부라는 의미는 아니다.
- 도메인 내부 적중률: **54.9%**(240,443/437,784)

### 기존 residue-position bin과의 교차표(중복성 검사)

| bin(1=N말단…5=C말단) | in_domain | not_in_domain | in_domain 비율 |
|---|---:|---:|---:|
| 1 | 36,301 | 40,736 | 47.1% |
| 2 | 50,951 | 33,138 | 60.6% |
| 3 | 52,151 | 36,244 | 59.0% |
| 4 | 54,363 | 36,985 | 59.5% |
| 5 | 46,677 | 50,238 | 48.2% |

5개 bin 모두 in_domain True/False가 상당수 섞여 있고(최소 클래스 비율도
47.1%로 어느 한쪽으로 쏠리지 않음), bin 값이 in_domain을 결정하는 정도가
아니다(bin별 in_domain 비율 47.1%~60.6%, 약 13.5%p 스프레드 — 단백질
중간부(2~4)가 말단부(1, 5)보다 도메인일 확률이 다소 높은 생물학적으로
합리적인 경향은 있지만 결정적이지 않음). Issue #241(PIK3CA helical/kinase
도메인)이 기존 position-level hotspot 컬럼과 완전 중복이라 보류됐던 것과는
다른 패턴이다. 따라서 **Pfam 여부가 기존 5-bin 하나로 완전히 결정되지는
않는다**고 판단한다. 이것은 신규 예측 신호나 Macro F1 개선을 증명한 결과가
아니며, 그 유용성은 별도 canonical 5-fold ablation에서만 판정한다.

## 판단

두 완료 조건(커버리지 확보, 기존 피처와의 중복성 배제)을 모두 통과했다.
`in_functional_domain` 잔기 단위 indicator를 EXP-374 위 단독 ablation
Experiment 후보로 제안할 최소 조건이 마련됐다고 판단한다. 이 사전 감사는
feature 채택이나 성능 개선을 뜻하지 않는다.

## 다음 단계

- [x] 공개·정적 annotation 기본 허용 정책과 Pfam 사용 승인 확보 — [Issue #581](https://github.com/fabxoe/open_cancer/issues/581)
- [ ] 승인 후 별도 Experiment Issue에서 EXP-374 대비 canonical 5-fold 단독
      ablation 실행

2026-08-06 정책 변경으로 공개·정적 annotation은 별도 팀장 승인 없이 사용할 수
있다. 다만 외부 환자 자료와 test/Public 기반 선택은 계속 금지되며, 이 보고서는
Pfam 피처의 예측 유용성을 증명하지 않는다.

## 산출물

- `knowledge/ensembl_protein_domain_annotation_v1.json` — provenance manifest
- `data/external/ensembl_release_116/domain_features/pfam_domains_by_protein.json` —
  12,681개 protein의 Pfam 도메인 좌표(Git 제외, `data/external/` 규칙)
- `reports/analysis/pfam_domain_residue_coverage_precheck/coverage_redundancy_precheck.json` —
  이 문서의 수치 원본
