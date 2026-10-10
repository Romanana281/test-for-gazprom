import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import ColumnElement, select

from app import stats
from app.db import SessionDep
from app.models import Device, Metric, User

router = APIRouter(prefix="/api")


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class CreateDeviceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: uuid.UUID | None = Field(default=None, alias="userId")


class MetricRequest(BaseModel):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    z: float = Field(allow_inf_nan=False)


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def metric_period(
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[ColumnElement[bool]]:
    from_, to = _to_utc(from_), _to_utc(to)
    if from_ is not None and to is not None and from_ > to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "'from' must not be later than 'to'.")

    conditions = []
    if from_ is not None:
        conditions.append(Metric.timestamp >= from_)
    if to is not None:
        conditions.append(Metric.timestamp <= to)
    return conditions


MetricPeriod = Annotated[list[ColumnElement[bool]], Depends(metric_period)]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(request: CreateUserRequest, db: SessionDep):
    user = User(name=request.name)
    db.add(user)
    db.commit()
    return {"id": user.id}


@router.get("/users/{id}/analytics")
def get_user_analytics(id: uuid.UUID, period: MetricPeriod, db: SessionDep):
    if db.get(User, id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    device_ids = db.scalars(select(Device.id).where(Device.user_id == id).order_by(Device.id)).all()
    metrics = db.scalars(select(Metric).where(Metric.device_id.in_(device_ids), *period)).all()

    by_device = defaultdict(list)
    for metric in metrics:
        by_device[metric.device_id].append(metric)

    return {
        "userId": id,
        "aggregated": stats.calculate(metrics),
        "devices": [
            {"deviceId": device_id, "statistics": stats.calculate(by_device[device_id])}
            for device_id in device_ids
        ],
    }


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def create_device(request: CreateDeviceRequest, db: SessionDep):
    if request.user_id is not None and db.get(User, request.user_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User not found.")

    device = Device(user_id=request.user_id)
    db.add(device)
    db.commit()
    return {"id": device.id}


@router.post("/devices/{id}/metrics", status_code=status.HTTP_201_CREATED)
def add_metric(id: uuid.UUID, request: MetricRequest, db: SessionDep):
    if db.get(Device, id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    metric = Metric(device_id=id, x=request.x, y=request.y, z=request.z)
    db.add(metric)
    db.commit()
    return {"id": metric.id}


@router.get("/devices/{id}/analytics")
def get_device_analytics(id: uuid.UUID, period: MetricPeriod, db: SessionDep):
    if db.get(Device, id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    metrics = db.scalars(select(Metric).where(Metric.device_id == id, *period)).all()
    return {"deviceId": id, "statistics": stats.calculate(metrics)}
