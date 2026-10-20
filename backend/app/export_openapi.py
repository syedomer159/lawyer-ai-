"""Write the OpenAPI schema to a file for the frontend type generator (`npm run gen:api`)."""

import json
import sys
from pathlib import Path

from app.main import app

out = Path(sys.argv[1])
out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"wrote {out}")
