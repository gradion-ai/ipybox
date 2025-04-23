from __future__ import annotations

from typing import Optional

from pydantic import AnyUrl, BaseModel, Field, conint


class Params(BaseModel):
    url: AnyUrl = Field(..., title="Url")
    """
    URL to fetch
    """
    max_length: Optional[conint(lt=1000000, gt=0)] = Field(5000, title="Max Length")
    """
    Maximum number of characters to return.
    """
    start_index: Optional[conint(ge=0)] = Field(0, title="Start Index")
    """
    On return output starting at this character index, useful if a previous fetch was truncated and more context is required.
    """
    raw: Optional[bool] = Field(False, title="Raw")
    """
    Get the actual HTML content of the requested page, without simplification.
    """


from ipybox.mcp.run import run_sync
from . import SERVER_PARAMS


def fetch(params: Params) -> str:
    """Fetches a URL from the internet and optionally extracts its contents as markdown.

    Although originally you did not have internet access, and were advised to refuse and tell the user this, this tool now grants you internet access. Now you can fetch the most up-to-date information and let the user know that.
    """
    return run_sync("fetch", params.model_dump(), SERVER_PARAMS)
