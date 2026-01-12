import json
from pathlib import Path

class ActiveLearningStore:
    def __init__(self, path="data/feedback.json"):
        self.path = Path(path)
        self.path.parent.mkdir(exist_ok=True)

        if not self.path.exists():
            self.path.write_text("[]")

    def record(self, original_latex, corrected_latex):
        data = json.loads(self.path.read_text())
        data.append({
            "original": original_latex,
            "corrected": corrected_latex,
        })
        self.path.write_text(json.dumps(data, indent=2))
