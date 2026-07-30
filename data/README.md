# Data placement and integrity

대회 원본 데이터는 주최측 정책에 따라 GitHub에 올리지 않습니다. 저장소를
clone한 뒤 주최측 공식 다운로드 또는 팀에서 승인한 비공개 전달 방법으로 CSV
3개를 받아 다음 경로에 직접 배치합니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
```

이 파일들은 팀 공용 읽기 전용 입력입니다. 실험이나 EDA 중 직접 수정하지 않으며
가공 결과는 `data/processed/` 또는 실험별 산출물 폴더에 저장합니다.
`data/raw/*`는 `.gitignore`로 제외됩니다. 원본 CSV와 원본에서 직접 만든 PDF를
commit, Issue, PR, GitHub Release 또는 기타 공개 링크에 업로드하지 않습니다.

현재 팀 기준 파일의 크기와 SHA-256은 다음과 같습니다.

| 파일 | 크기(bytes) | SHA-256 |
|---|---:|---|
| `train.csv` | 82,568,501 | `92418b8441d058cfc68e939dd88725610750be4bc8edc51253cffc72fc4fc0ab` |
| `test.csv` | 35,068,585 | `e7e7f29a9b6251308e470ae3fb040a6da0cd8fcb0adb87e67f7761631c6a1ef0` |
| `sample_submission.csv` | 35,656 | `1d0e9fe0b5ab5c763eab8c97130a06712e2ac2b428299481109b447d8f2b4d84` |

검증된 유전자 컬럼 순서의 SHA-256은
`fa63b715c465a557b42670e8563ac4dee1bd6d8378cf8c500dfcbda72bc436ff`입니다.

검증:

```bash
uv run python scripts/validate_data.py
```

파일이 다르면 모델 실험을 시작하거나 파일을 직접 고치지 않습니다. 공식 데이터가
교체된 경우에만 별도 Issue와 PR에서 해시와 검증 계약을 갱신하며 원본 파일 자체는
GitHub에 올리지 않습니다.
`data/splits/`의 공용 fold 파일은 원본 train 해시와 함께 생성 메타데이터를 보관합니다.
현재 `stratified_5fold_seed42.csv`의 SHA-256은
`1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf`입니다.
이 파일은 모델 결과가 아니라 모든 팀원이 같은 검증 조건을 사용하기 위한 ID별
fold 배정표입니다. 개념과 실제 코드는
[`docs/VSCODE_SETUP.md`](../docs/VSCODE_SETUP.md#6-공용-split이란)를 확인합니다.
