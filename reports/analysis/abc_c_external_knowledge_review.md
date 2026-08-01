# ABC-Stack C 외부 지식 검토

Issue #104의 C family는 환자별 외부 값을 사용하지 않고 고정 gene membership만
사용한다. 근거 논문은 Sanchez-Vega et al.의 TCGA pathway 연구이며, 논문은 10개
canonical pathway를 정의하고 Table S3에 curated pathway template를 제공한다.

- 원 논문: https://doi.org/10.1016/j.cell.2018.03.035
- 공개 본문: https://pmc.ncbi.nlm.nih.gov/articles/PMC6070353/
- Table S3 원본 SHA-256:
  `df722435b7c069b9225c9e4bbef7ab812385bd5e8ab7c415837cde5f2838c640`
- 논문 라이선스: CC BY-NC-ND 4.0

저장소에는 Table S3 전체나 환자 데이터를 복제하지 않는다. 사전에 고정한 소수의
대표 gene membership와 OG/TSG 역할만 `knowledge/abc_c_compact_groups_v1.json`에
사실 메타데이터로 기록한다. 이 목록은 대회 label·빈도·OOF·Public LB를 보고
선택하지 않았다.

다만 외부 문헌의 gene membership도 대회 규정상 외부 데이터로 해석될 수 있다.
따라서 구현과 score-free smoke는 허용하되, 주최측의 명시적 허용 답변과 링크를
config에 기록하기 전에는 공식 5-fold, 제출 또는 모델 입력에 사용하지 않는다.
