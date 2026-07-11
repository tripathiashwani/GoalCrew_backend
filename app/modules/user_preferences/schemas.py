# app/modules/user_preferences/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import time


class UserPreferenceRead(BaseModel):
    checkin_frequency: str
    checkin_time: Optional[time] = None
    pod_updates_enabled: Optional[bool] = True
    reminder: Optional[bool] = False
    sms_reminder: Optional[bool] = False
    photo_expiration: str

    class Config:
        from_attributes = True


class UserPreferenceUpdate(BaseModel):
    checkin_frequency: Optional[str] = Field(
        None, pattern="^(daily|weekly|monthly)$"
    )
    checkin_time: Optional[time] = None
    reminder: Optional[bool] = None
    sms_reminder: Optional[bool] = None
    pod_updates_enabled: Optional[bool] = None
    photo_expiration: Optional[str] = Field(
        None, pattern="^(24h|5d|7d)$"
    )
