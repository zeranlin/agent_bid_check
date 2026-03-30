#!/usr/bin/env python3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.web.v2_app import app


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, threaded=True, port=5011)
