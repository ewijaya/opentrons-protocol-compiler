"""Front-ends: parse a spec into a ``TransferGraph``.

Two front-ends share one IR:

* :func:`~pipettec.spec.yaml_spec.load_yaml` — human-written YAML templates.
* :func:`~pipettec.spec.echo.load_echo_csv` — Echo picklist CSV import.
"""

from pipettec.spec.echo import load_echo_csv
from pipettec.spec.yaml_spec import load_yaml, load_yaml_str

__all__ = ["load_yaml", "load_yaml_str", "load_echo_csv"]
