# Lets `pytest` import `bench` and `gold` from the repository root. The production code (5ltep-layer1)
# is taken from ./upstream (the workflows check it out there) or, locally, from UPSTREAM.
import os
from pathlib import Path

if "UPSTREAM" not in os.environ and not (Path(__file__).parent / "upstream").exists():
    sibling = Path(__file__).resolve().parent.parent / "public"
    if sibling.exists():
        os.environ["UPSTREAM"] = str(sibling)
