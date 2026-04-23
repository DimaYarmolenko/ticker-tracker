from datetime import datetime

from pydantic import BaseModel, field_validator


class TickerCreate(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()


class TickerResponse(BaseModel):
    id: str
    symbol: str
    date_added: datetime

    model_config = {"from_attributes": True}
