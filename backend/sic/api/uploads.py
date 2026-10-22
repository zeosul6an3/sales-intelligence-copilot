"""CSV upload endpoints: template, stage, validate, import."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from sic.data import upload
from sic.data.storage import DatasetNotFound

router = APIRouter(prefix="/api/uploads")


class UploadOptions(BaseModel):
    mapping: dict[str, str | None]
    currency: str = Field(min_length=3, max_length=3)
    day_first: bool = False
    name: str | None = Field(default=None, max_length=120)

    def to_options(self) -> upload.Options:
        return upload.Options(self.mapping, self.currency.upper(), self.day_first, self.name)


def _call(fn, *args):
    try:
        return fn(*args)
    except upload.UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    except DatasetNotFound as exc:
        raise HTTPException(404, "Upload not found; please upload the file again.") from exc


@router.get("/template.csv", response_class=PlainTextResponse)
def template() -> PlainTextResponse:
    return PlainTextResponse(
        upload.TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sales_template.csv"'},
    )


@router.post("")
async def stage(file: Annotated[UploadFile, File()]) -> dict:
    raw = await file.read(upload.MAX_UPLOAD_BYTES + 1)
    return _call(upload.stage, raw, file.filename or "upload.csv")


@router.post("/{upload_id}/validate")
def validate(upload_id: str, options: UploadOptions) -> dict:
    return _call(upload.validate, upload_id, options.to_options())


@router.post("/{upload_id}/import")
def import_upload(upload_id: str, options: UploadOptions) -> dict:
    return _call(upload.import_upload, upload_id, options.to_options())
