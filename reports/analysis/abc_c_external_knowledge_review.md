# ABC-Stack C 외부 지식 검토

Issue #104의 C family는 환자별 외부 값을 사용하지 않고 고정 gene membership만
사용한다. 근거 논문은 Sanchez-Vega et al.의 TCGA pathway 연구이며, 논문은 10개
canonical pathway를 정의한다. 공식 C-1은 수동으로 추린 대표 목록 대신
PathwayMapper의 고정 커밋에서 10개 canonical template의 모든 `GENE` node를
결정론적으로 추출한다.

- 원 논문: https://doi.org/10.1016/j.cell.2018.03.035
- 공개 본문: https://pmc.ncbi.nlm.nih.gov/articles/PMC6070353/
- Table S3 원본 SHA-256:
  `df722435b7c069b9225c9e4bbef7ab812385bd5e8ab7c415837cde5f2838c640`
- 논문 라이선스: CC BY-NC-ND 4.0
- PathwayMapper 원본:
  https://github.com/iVis-at-Bilkent/pathway-mapper/blob/7d29965de6ac8d0c6ec18c383f6dff8a48d562e7/packages/pathway-mapper/src/data/pathways.json
- PathwayMapper 원본 SHA-256:
  `a625675d03fa314eb27f3ab731524de13621a35aecd8edb7c67878f2d89ae07a`
- PathwayMapper 라이선스: AGPL-3.0

저장소에는 Table S3 전체나 환자 데이터를 복제하지 않는다. C-1 pathway 목록은
`knowledge/canonical_pathways_sanchez_vega_v1.json`에 원본 커밋·경로·해시와
추출 규칙을 함께 기록한다. 실제 피처에는 이 목록과 대회 4,384개 유전자 패널의
교집합만 사용한다. C-2 기능 역할 목록은 별도
`knowledge/abc_c_compact_groups_v1.json`에 두며 C-1 실험에는 섞지 않는다.

팀 리더는 2026-08-01 주최측으로부터 고정 문헌 gene membership 사용이 가능하다는
답변을 받았다고 확인했다. 이 사실은
<https://github.com/fabxoe/open_cancer/issues/96#issuecomment-5151028180>에 고정했고,
EXP-096 config와 manifest가 같은 링크를 참조한다. 허용 범위는 고정 그룹 정의와
대회 CSV 기반 집계이며 외부 환자 데이터·임베딩·연속 weight는 포함하지 않는다.
