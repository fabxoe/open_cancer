# EXP-151 재현 절차

원본 CSV를 `data/raw/`에 배치하고 Release 번들을 저장소 루트에 푼 뒤 실행합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp151_burden_incremental.py --replay-checkpoints
shasum -a 256 submissions/exp151_mutated_gene_burden.csv
```

제출 파일의 기대 SHA-256은 다음과 같습니다.

```text
dddaf57cf2c497b08264a2c883223afff0d347edcadb9585783f06e1294e4349
```

원 실행은 RTX 4090, 검증은 macOS CPU에서 수행했습니다. 장치 차이로 확률값은 완전히 같지 않았지만 test 예측 라벨 2,546개와 제출 CSV는 모두 일치했습니다. 상세 비교는 `comparison.json`을 확인합니다.

metrics에 기록된 런타임 commit `f0419e1…`은 원격 Git 이력에 남아 있지 않습니다. 실행 당시 코드와 config가 동일한 보존 commit `17d433f81cf41fce54045739b0531915cc89b565`를 Release source tag로 사용했습니다.
