"""Project-wide immutable data contracts."""

CLASS_LABELS: tuple[str, ...] = (
    "ACC",
    "BLCA",
    "BRCA",
    "CESC",
    "COAD",
    "DLBC",
    "GBMLGG",
    "HNSC",
    "KIPAN",
    "KIRC",
    "LAML",
    "LGG",
    "LIHC",
    "LUAD",
    "LUSC",
    "OV",
    "PAAD",
    "PCPG",
    "PRAD",
    "SARC",
    "SKCM",
    "STES",
    "TGCT",
    "THCA",
    "THYM",
    "UCEC",
)

EXPECTED_TRAIN_ROWS = 6_201
EXPECTED_TEST_ROWS = 2_546
EXPECTED_GENE_COLUMNS = 4_384
PROBABILITY_COLUMNS: tuple[str, ...] = tuple(f"PROBA_{label}" for label in CLASS_LABELS)

EXPERIMENT_STATUSES: tuple[str, ...] = (
    "PLANNED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "ABORTED",
)

REPRODUCIBILITY_STATUSES: tuple[str, ...] = (
    "NOT_STARTED",
    "MANIFEST_COMPLETE",
    "INFERENCE_VERIFIED",
    "TRAINING_VERIFIED",
    "FAILED",
)
