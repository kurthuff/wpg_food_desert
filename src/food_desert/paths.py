from pathlib import Path

project_root = Path(__file__).resolve().parents[2]

def raw() -> Path:
    return project_root / "data" / "raw"

def interim() -> Path:
    return project_root / "data" / "interim"

def processed() -> Path:
    return project_root / "data" / "processed"

def reference() -> Path:
    return project_root / "data" / "reference"

def rasters() -> Path:
    return project_root / "outputs" / "rasters"

def logs() -> Path:
    return project_root / "logs"

def reports() -> Path:
    return project_root / "outputs" /  "reports"

def outputs() -> Path:
    return project_root / "outputs"