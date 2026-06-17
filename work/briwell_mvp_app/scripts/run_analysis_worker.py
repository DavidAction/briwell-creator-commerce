import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.contracts import AnalysisRequest
from app.workers.analysis_runner import AnalysisRunRequest, run_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Briwell analysis job request.")
    parser.add_argument("--input-json", required=True, help="Path to an AnalysisRunRequest JSON file.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    payload["request"] = AnalysisRequest.model_validate(payload["request"])
    result = run_analysis(AnalysisRunRequest.model_validate(payload))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
