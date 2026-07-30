# EXP-001 Claude Code 핸드오프

이슈: https://github.com/fabxoe/open_cancer/issues/12
(데이터전처리_COSMIC 보호 유전자(cosmic_protected_genes) 기반 Feature 보호 전략 분석)

이 문서는 claude.ai에서 원본 train.csv/test.csv를 직접 열어 검증한 결과와,
Claude Code에서 그대로 이어받아 실행할 작업 순서를 정리한 것입니다.

---

## 0. 데이터 배치

원본 파일 3개(train.csv, test.csv, sample_submission.csv)를 레포의 데이터 폴더
(baseline 노트북 기준 `./train.csv` 상대경로 — 실제 레포 구조에 맞게 조정)에 둔 뒤 시작합니다.

## 1. claude.ai에서 검증 완료한 사실 (재검증 불필요)

이 수치들은 이미 확인이 끝났으므로, Claude Code에서는 이 값들을 그대로 가정하고
바로 다음 단계(화이트리스트 비교, 도메인 판단)로 넘어가면 됩니다.

```
train shape: (6201, 4386)  # ID, SUBCLASS 포함
test shape:  (2546, 4385)  # ID 포함, SUBCLASS 없음
gene_cols:   4384개

train 결측치: 0
test 결측치:  237개 (25개 컬럼)
  -> CNOT2(77) + TNFAIP6(65) + AK2(29) 세 컬럼이 171개(72%) 차지
  -> 나머지 22개 컬럼은 1~21개씩 산발 분포
  -> 즉 "랜덤 산발"이 아니라 소수 유전자에 결측이 몰린 구조.
     시퀀싱 커버리지/콜링 이슈일 가능성 -> 화이트리스트(cosmic_protected_genes)와
     겹치는지 1번으로 확인 필요 (아래 스크립트가 자동 체크)

클래스 분포: 26개 클래스, BRCA 786(최다) ~ DLBC 38(최소)

변이율 0%: 154개 유전자 (전부 WT)
변이율 <1%: 3,329개 유전자

Top mutation rate genes (train 기준):
  TP53 28.5%, PIK3CA 11.1%, RYR2 10.4%, SYNE1 10.4%, PCLO 9.6%,
  RYR1 7.6%, SPTA1 7.4%, KMT2D 7.3%, IDH1 7.1%, BRAF 7.1%

패널 부재 확인됨: KRAS, NRAS, BAP1, PBRM1, SETD2 -> 전부 gene_cols에 없음 (재확인 완료)

다중 변이(공백 구분) 셀: 22,026건 -> 파싱 단계에서 반드시 처리 필요
```

## 2. Claude Code에서 실행할 작업 (이슈 #12 체크리스트 순서대로)

첨부한 `exp001_feature_analysis.py`를 레포에 넣고 실행하면 아래를 자동으로 만들어줍니다.
단, **`cosmic_protected_genes` 목록 파일 경로는 스크립트 상단 `COSMIC_LIST_PATH`를
실제 레포에 이미 구축된 파일 경로로 바꿔야 합니다** (claude.ai에는 이 파일이 없어서
스크립트에는 더미 폴백만 넣어뒀습니다).

1. [ ] `COSMIC_LIST_PATH` 를 실제 파일로 연결 (레포에 이미 있다고 하셨던 그 파일)
2. [ ] 스크립트 실행 -> `reports/EXP-001/` 아래에 아래 산출물 생성됨:
   - `mutation_rate_distribution.csv` : 전체 4,384개 유전자 변이율 + 화이트리스트 여부
   - `whitelist_vs_rest_summary.csv` : 화이트리스트 vs 비화이트리스트 분포 비교 통계
   - `whitelist_low_mutation_187.csv` : 화이트리스트 중 변이율 1% 미만 187개 목록
     (COSMIC role 컬럼은 비어있음 -> 도메인 지식으로 직접 채우거나 COSMIC role 매핑 파일 조인 필요)
   - `high_mutation_nonwhitelist.csv` : 비화이트리스트인데 변이율 상위인 유전자
     (RYR2/SYNE1/PCLO/RYR1/SPTA1 등 long gene bias 의심 후보 -> 유전자 길이 컬럼
     추가해서 상관 확인 권장, 스크립트에 TODO로 표시해둠)
   - `missing_value_report.csv` : test 결측 25개 컬럼과 화이트리스트 overlap 여부
3. [ ] 위 산출물을 보고 "보호 규칙" 확정:
   - 화이트리스트 340개는 무조건 보호
   - 비화이트리스트 154개(변이율 0%)는 제거, 나머지는 임계값 논의
   - 임계값 근거를 수치로 EXPERIMENT_HISTORY.md에 남길 것
4. [ ] 최종 `protected_genes_final.csv` / `dropped_genes_final.csv` 작성
   (이게 이후 인코딩/모델 학습 이슈의 입력값이 됨)
5. [ ] EXPERIMENT_HISTORY.md에 EXP-001로 기록 (목적/설정/결과/다음 단계 템플릿 사용)

## 3. 이번 이슈에서 하지 않는 것 (범위 밖, 다음 이슈로 분리됨)

- 5-fold CV harness, 실제 모델 학습, OOF Macro F1 계산
- 인코딩 방식 구현 (이진화 vs 화이트리스트 세분화)
- sample_weight 적용, 오버샘플링 비교

이 항목들은 EXP-001 산출물(protected/dropped gene 목록)을 입력으로 받는
후속 이슈에서 다룹니다.
