from datetime import datetime
from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class Role(StrEnum):
    USER = "USER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"
    VALIDATOR = "VALIDATOR"


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Error(DTO):
    code: str
    message: str
    request_id: UUID


class UserView(DTO):
    id: UUID
    email: str
    role: Role


class LoginRequest(DTO):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Invalid email")
        return value


class LoginResponse(DTO):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: Literal[900] = 900
    user: UserView


class AccountView(DTO):
    id: UUID
    owner_user_id: UUID
    label: str
    balance_minor: Annotated[int, Field(ge=0, le=10**12)]
    currency: Literal["EUR"]
    status: Literal["ACTIVE", "FROZEN"]
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime


class PaymentRequest(DTO):
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: Annotated[StrictInt, Field(ge=1, le=10**12)]
    currency: Literal["EUR"]

    @model_validator(mode="after")
    def different_accounts(self):
        if self.source_account_id == self.destination_account_id:
            raise ValueError("Source and destination must differ")
        return self


class PaymentView(DTO):
    id: UUID
    actor_user_id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: int
    currency: Literal["EUR"]
    status: Literal["SUCCESS", "REJECTED"]
    failure_code: Literal["INSUFFICIENT_FUNDS", "ACCOUNT_FROZEN", "BALANCE_LIMIT"] | None
    created_at: datetime


class Health(DTO):
    status: Literal["ok", "degraded", "unavailable"]
    service: str
    checked_at: datetime


T = TypeVar("T")


class Page(DTO, Generic[T]):
    items: list[T]
    next_cursor: str | None
