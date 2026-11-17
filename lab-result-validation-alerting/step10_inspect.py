import inspect
import sys
from pathlib import Path
from dataclasses import fields, is_dataclass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from labvalidation import critical_alerts, models

for module in (models, critical_alerts):
    print(f"\n--- {module.__name__} ---")
    for name in ("AlertStatus", "CriticalAlert", "EscalationStep",
                 "CriticalAlertRecord", "CriticalAlertRegistry",
                 "NotificationEvent"):
        obj = getattr(module, name, None)
        if obj is None:
            continue
        print(f"\n{name}:")
        if is_dataclass(obj):
            print("Fields:", ", ".join(f.name for f in fields(obj)))
        if inspect.isclass(obj):
            for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                if not method_name.startswith("_"):
                    print(f"  {method_name}{inspect.signature(method)}")