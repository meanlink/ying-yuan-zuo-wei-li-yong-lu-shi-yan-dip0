from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ConfigureSubsidy(BaseModel):
    model_config = ConfigDict(extra='forbid')

    total: Decimal = Field(ge=0, max_digits=11, decimal_places=2)
    per_seat: Decimal = Field(gt=0, max_digits=9, decimal_places=2)
