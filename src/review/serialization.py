import json
from src.review.schema import ReviewRecord

def serialize_review_record(record: ReviewRecord) -> str:
    """
    Serialize ReviewRecord to a deterministic JSON string.
    """
    # model_dump_json takes care of Enums and nested Pydantic models.
    return record.model_dump_json(exclude_none=True)

def deserialize_review_record(json_str: str) -> ReviewRecord:
    """
    Deserialize JSON string back into a ReviewRecord.
    """
    return ReviewRecord.model_validate_json(json_str)
