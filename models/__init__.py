"""
models/
=======
One module per entity. Each module exposes simple CRUD functions that use
the helpers in `db.py`. All queries are parameterised.
"""

from . import users          # noqa: F401
from . import categories     # noqa: F401
from . import accounts       # noqa: F401
from . import transactions   # noqa: F401
from . import recurring      # noqa: F401
from . import budgets        # noqa: F401
from . import alerts         # noqa: F401
from . import scenarios      # noqa: F401
