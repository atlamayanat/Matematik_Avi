"""pytest ortak kurulumu: python/ klasörünü sys.path'e ekler ki testler
`import config`, `import selection`, ... yapabilsin (kod cwd=python/ varsayar)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pytest  # noqa: E402
from config import load_config  # noqa: E402


@pytest.fixture
def cfg():
    """Gerçek sevk edilen config.json (mutlak yol -> cwd bağımsız)."""
    return load_config(os.path.join(HERE, "config.json"))
