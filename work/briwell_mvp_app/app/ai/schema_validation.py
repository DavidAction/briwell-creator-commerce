from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.analysis import ANALYSIS_OUTPUT_SCHEMAS


class AnalysisSchemaError(ValueError):
    """Raised when an AI output does not match its task schema."""


def schema_for_task(task_type: str) -> type[BaseModel]:
    try:
        return ANALYSIS_OUTPUT_SCHEMAS[task_type]
    except KeyError as exc:
        raise AnalysisSchemaError(f"unsupported_analysis_task:{task_type}") from exc


def validate_analysis_output(task_type: str, output: dict[str, Any]) -> BaseModel:
    schema = schema_for_task(task_type)
    try:
        return schema.model_validate(output)
    except ValidationError as exc:
        raise AnalysisSchemaError(str(exc)) from exc
