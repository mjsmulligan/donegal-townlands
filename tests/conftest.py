"""Make the repo root (for `from tools import x`) and tools/ (for `import x`) importable
whichever way the tests are started."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
