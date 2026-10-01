"""Copy release sources and reproducibility records into the existing Git archive.

No Git mutations or network operations. Generated builds, SSH configuration, and
raw profiler databases are excluded; V13's compact evidence bundle is retained.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "CANN_archive"
DEST = ARCHIVE / "BMMS"
TEXT = {".asc", ".py", ".sh", ".cpp", ".h", ".hpp", ".md", ".json", ".diff", ".ini"}
BLOCKED = {"env", ".ssh", ".git", "__pycache__", "build", "cpu_build", "host_build", "dispatch_build", "bounds_build", "CMakeFiles"}


def allowed(p, base):
    rel = p.relative_to(base)
    return not any(part in BLOCKED or part.endswith("_build") or part.startswith("PROF_") for part in rel.parts)


def tree(base, suffixes):
    if not base.exists():
        return []
    return [p for p in base.rglob("*") if p.is_file() and allowed(p, base)
            and (p.suffix in suffixes or p.name == "CMakeLists.txt")]


def selected():
    files = set(ROOT.glob("*.md"))
    for name in ["BMMS_V12", "BMMS_V13", "V13_npu_lab"]:
        files.update(tree(ROOT / name, TEXT | {".txt", ".gz"}))
    for base in ROOT.glob("BMMS_V11_*"):
        if base.is_dir():
            files.update(tree(base, TEXT))
    for pattern in ["V11_impl_r*", "V12_impl_r*", "V11_analysis_r43", "V12_analysis_r01"]:
        for base in ROOT.glob(pattern):
            files.update(tree(base, TEXT))
    for name in ["V11_results", "V12_results"]:
        files.update(tree(ROOT / name, {".md", ".json", ".png", ".csv", ".py", ".cpp"}))
    lab = ROOT / "V12_npu_lab"
    files.update(p for p in lab.iterdir() if p.is_file() and p.suffix in TEXT)
    for name in ["harness", "small_20261001", "rethink_20261001", "case12_k1_20261001", "narrow_dense", "host_c1112", "host_c12", "host_r23", "host_r24"]:
        files.update(tree(lab / name, TEXT | {".txt"}))
    # Keep each experiment's top-level reports and summaries. Raw profiler
    # traces remain local; new V13 raw validation is in its evidence.tar.gz.
    for experiment in (lab / "results").iterdir():
        if experiment.is_dir():
            files.update(p for p in experiment.iterdir() if p.is_file() and p.suffix in {".md", ".json", ".csv"})
    return sorted(files)


def main():
    assert (ARCHIVE / ".git").exists(), "Expected existing CANN archive checkout"
    files = selected()
    records = []
    for src in files:
        rel = src.relative_to(ROOT)
        dst = DEST / rel
        data = src.read_bytes()
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != data:
            shutil.copyfile(src, dst)
        records.append({"path": rel.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    report = {
        "date": "2026-10-01", "line": "V13", "accepted": "BMMS_V13/v13_r1_baseline_r72.asc",
        "pending_submission": "BMMS_V13/v13_r2_submit_compact.asc",
        "judge_status": "r2 HTTP 413 before evaluation; compact retry pending",
        "scope": "Release source history, reports, reproducibility scripts, V13 raw validation bundle",
        "excluded": ["SSH/environment configuration", "build products", "raw V12 profiler databases", "third-party source trees"],
        "file_count": len(records), "total_bytes": sum(r["bytes"] for r in records), "files": records,
    }
    (ARCHIVE / "PUBLICATION_V13.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
