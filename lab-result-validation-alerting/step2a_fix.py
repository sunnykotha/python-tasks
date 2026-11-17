from pathlib import Path

project = Path(r"C:\Users\GK\lab-result-validation-alerting")

files = [
    project / "src" / "labvalidation" / "models.py",
    project / "tests" / "test_models.py",
]

for path in files:
    content = path.read_text(encoding="utf-8")
    content = content.replace("TestDefinition", "LabTestDefinition")
    path.write_text(content, encoding="utf-8")

print("Renamed TestDefinition to LabTestDefinition.")