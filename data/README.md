# data/

Nothing under this directory is study data. It holds provenance only:

- `manifests/` : SHA-256 manifests of the study mount, one per ingest date (`palmppg features build` writes them).
- `splits/`    : participant-level split files (`grouped_kfold_<name>.json`) with the seed and the sha256 of the sorted
                 id list, so every experiment can prove it used the same folds.
- `hashes/`    : config hashes recorded at each experiment run (frozen_config sha256, pipeline.yaml sha256).

Study data is mounted at `paths.study_root` (default `data/study`, git-ignored). The locked prospective test stream is
mounted separately at `paths.test_root` (default `data/test_stream`), read once through `TestStreamGuard`, which
appends every access attempt to `ACCESS_LOG.jsonl` on that mount.
