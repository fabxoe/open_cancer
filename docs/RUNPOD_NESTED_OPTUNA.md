# RunPod nested Optuna 실행 계약

이 문서는 채택된 하나의 feature policy를 대상으로 하는 공식 nested Optuna
실험의 원격 실행 절차입니다. Task Issue에서는 runner만 구현하고, 실제 실행 전
별도 Experiment Issue를 발급해 `EXP-NNN`을 확정합니다.

## 누수 방지 계약

- outer split은 `data/splits/stratified_5fold_seed42.csv`를 그대로 사용합니다.
- 각 outer fold의 하이퍼파라미터는 그 fold의 outer-train 내부 3-fold에서만
  선택합니다.
- TPE seed는 `42 + outer_fold`, 예산은 outer fold당 완료 trial 30개입니다.
- outer validation, test 데이터, Public LB는 trial 선택에 사용하지 않습니다.
- 중단 후 재개할 때는 fold별 SQLite에서 `COMPLETE` trial만 예산에 포함합니다.
- 공식 runner는 clean experiment branch의 정확한 commit에서 실행합니다.

## 1. Pod 준비

- Secure Cloud RTX 4090 1장
- container disk 30GB 이상, `/workspace` volume 50GB 이상
- SSH 공개키 등록 및 Full SSH/public IP 사용

Pod가 실행된 뒤 로컬에서 접속 정보를 확인합니다.

```bash
runpodctl pod list
runpodctl ssh info <POD_ID>
```

## 2. 소스와 원본 데이터 배치

Pod에서 공식 experiment branch와 commit을 checkout합니다.

```bash
cd /workspace
git clone https://github.com/fabxoe/open_cancer.git
cd open_cancer
git switch issue-<번호>-<slug>
git rev-parse HEAD
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --frozen --group experiment
```

원본 CSV는 GitHub에 올리지 않습니다. 로컬 Mac에서 Full SSH의 host와 port를
사용해 전송합니다.

```bash
ssh -p <PORT> root@<HOST> 'mkdir -p /workspace/open_cancer/data/raw'
scp -P <PORT> data/raw/train.csv data/raw/test.csv \
  data/raw/sample_submission.csv \
  root@<HOST>:/workspace/open_cancer/data/raw/
```

실행 전 원본 데이터 해시와 GPU를 확인합니다.

```bash
cd /workspace/open_cancer
sha256sum data/raw/train.csv data/raw/test.csv data/raw/sample_submission.csv
nvidia-smi
uv run --group experiment python -c \
  'import xgboost; print(xgboost.__version__)'
```

## 3. Smoke와 공식 실행

공용 구현 smoke test는 competition data를 사용하지 않습니다.

```bash
uv run --group experiment python scripts/smoke_nested_optuna.py
```

공식 실험은 `tmux`에서 실행해 SSH 연결 종료와 분리합니다.

```bash
tmux new -s nested-optuna
cd /workspace/open_cancer
uv run --group experiment python scripts/run_expNNN_<slug>.py \
  2>&1 | tee reports/expNNN_<slug>/run.log
```

분리와 재접속:

```text
Ctrl-b d
tmux attach -t nested-optuna
```

Pod가 중단되었더라도 동일 commit·config·artifact slug로 다시 실행하면
`models/expNNN_<slug>/optuna/outer_XX.sqlite3`의 완료 trial 뒤부터 이어집니다.

## 4. 결과 회수와 검증

학습 종료 후 로컬 Mac으로 다음 디렉터리를 회수합니다.

```bash
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/models/expNNN_<slug>/ \
  models/expNNN_<slug>/
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/oof/expNNN_<slug>.csv oof/
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/preds/expNNN_<slug>_test_proba.csv preds/
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/submissions/expNNN_<slug>.csv submissions/
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/reproducibility/expNNN_<slug>/ \
  reproducibility/expNNN_<slug>/
rsync -av -e 'ssh -p <PORT>' \
  root@<HOST>:/workspace/open_cancer/reports/expNNN_<slug>/ \
  reports/expNNN_<slug>/
```

로컬에서 submission, checkpoint 재추론, manifest 해시, 전체 History validator를
확인한 뒤에만 보고서·History PR을 만듭니다.

## 5. 비용 종료 조건

다음 항목을 확인한 즉시 Pod를 **terminate/delete**합니다. Stop만 하면 volume
storage 비용이 계속 발생할 수 있습니다.

- checkpoint, fold별 Optuna SQLite/JSON 회수
- OOF/test 확률/submission 회수
- report/reproducibility/log 회수
- 로컬 파일 크기와 SHA-256 확인

```bash
runpodctl pod stop <POD_ID>
runpodctl pod remove <POD_ID>
runpodctl pod list
```

마지막 목록에서 해당 Pod가 사라진 것을 확인합니다.
