
from pydantic import BaseModel, ConfigDict


class UploadedFileResponse(BaseModel):
    id: int
    consultation_id: int
    uploaded_by: int
    file_type: str
    original_name: str
    stored_name: str
    size_kb: int

    model_config = ConfigDict(from_attributes=True)
