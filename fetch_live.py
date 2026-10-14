"""Fetch the live mv2-forecaster source + tests into the working directory so the
live-reproduction run (compare_extractors.py) runs against exactly what is
deployed on main. Made with AI by MV2 of Munim, Inc. (research field)."""
import urllib.request

RAW = "https://raw.githubusercontent.com/munimtechnologies/mv2-forecaster/main/"

for fn in ("mv2_forecaster.py", "test_mv2_forecaster.py"):
    data = urllib.request.urlopen(RAW + fn, timeout=60).read().decode("utf-8")
    with open(fn, "w", encoding="utf-8") as fh:
        fh.write(data)
    print(f"fetched {fn}: {len(data)} bytes")

import mv2_forecaster as mf  # noqa: E402
print("live __version__ =", mf.__version__)
