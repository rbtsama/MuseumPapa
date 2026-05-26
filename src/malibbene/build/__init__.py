"""Build pipeline: raw/* → structured/{libraries, attractions, branches, passes}.json.

passes.py reads the per-platform raw catalog/ directly; there is no
library_catalog.json intermediate (that earlier design was removed)."""
