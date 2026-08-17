"""`python -m litharness` — the same entrypoint the console script exposes.

Both exist because whatever drives the session may only have one of them: a console
script needs the package installed with its bin directory on PATH, and `python -m` works
from a checkout with nothing but the interpreter. Driving ticks should not depend on
which.
"""

from litharness.cli import main

raise SystemExit(main())
