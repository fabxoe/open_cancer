# Data placement and integrity

대회 원본 CSV와 데이터 리포트 PDF는 저장소에 버전을 고정하여 Git으로 추적합니다.
팀원이 clone하면 다음 파일이 `data/raw/`에 함께 내려옵니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
data/raw/train_data_report.pdf
data/raw/test_data_report.pdf
data/raw/sample_submission_data_report.pdf
```

이 파일들은 팀 공용 읽기 전용 입력입니다. 실험이나 EDA 중 직접 수정하지 않으며,
가공 결과는 `data/processed/` 또는 실험별 산출물 폴더에 저장합니다.
`.gitattributes`에서 binary로 고정하므로 macOS와 Windows의 줄바꿈 설정에 따른
바이트 변환 없이 동일한 파일을 받습니다.

현재 팀 기준 파일의 크기와 SHA-256은 다음과 같습니다.

| 파일 | 크기(bytes) | SHA-256 |
|---|---:|---|
| `train.csv` | 82,568,501 | `92418b8441d058cfc68e939dd88725610750be4bc8edc51253cffc72fc4fc0ab` |
| `test.csv` | 35,068,585 | `e7e7f29a9b6251308e470ae3fb040a6da0cd8fcb0adb87e67f7761631c6a1ef0` |
| `sample_submission.csv` | 35,656 | `1d0e9fe0b5ab5c763eab8c97130a06712e2ac2b428299481109b447d8f2b4d84` |
| `train_data_report.pdf` | 147,724 | `307cadf08c0adfb1791c294fa09462dac775bb0750e7ef30609a532770f99a7e` |
| `test_data_report.pdf` | 142,866 | `de01719bcccebe0adeaec7add81f3ec59276a94df605e78deabfe1c5aeeaafd7` |
| `sample_submission_data_report.pdf` | 39,822 | `92c16893ecc3ebbf7f54b7d571cfaf4d719a1919c68bb54bd0dee462fe33c528` |

검증된 유전자 컬럼 순서의 SHA-256은
`fa63b715c465a557b42670e8563ac4dee1bd6d8378cf8c500dfcbda72bc436ff`입니다.

검증:

```bash
uv run python scripts/validate_data.py
```

파일이 다르면 모델 실험을 시작하거나 파일을 직접 고치지 않습니다. 먼저
`git status`로 변경 여부를 확인하고 팀 저장소의 버전과 비교합니다. 공식 데이터가
교체된 경우에만 별도 Issue와 PR에서 파일, 해시, 검증 계약을 함께 갱신합니다.
`data/splits/`의 공용 fold 파일은 원본 train 해시와 함께 생성 메타데이터를 보관합니다.
현재 `stratified_5fold_seed42.csv`의 SHA-256은
`1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf`입니다.
이 파일은 모델 결과가 아니라 모든 팀원이 같은 검증 조건을 사용하기 위한 ID별
fold 배정표입니다. 개념과 실제 코드는
[`docs/VSCODE_SETUP.md`](../docs/VSCODE_SETUP.md#6-공용-split이란)를 확인합니다.
