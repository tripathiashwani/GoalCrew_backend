from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    phone_number:Optional[str] = None
    country_code:Optional[str]= None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: UUID
    firebase_uid : str
    email: EmailStr
    name: Optional[str] = None
    username: Optional[str] = None
    phone_number: Optional[str] = None
    country_code: Optional[str] = None
    profile_photo_url : Optional[str] = None
    is_onboarded: bool = Field(alias="is_onboarded")
    is_phone_verified : Optional[bool] = None
    role: Optional[str] = None
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    country_code: Optional[str] = None
    is_onboarded: Optional[bool] = None
 
    @model_validator(mode="after")
    def validate_phone_pair(self):
        phone = self.phone_number
        code = self.country_code

        # If one is provided, both must be provided
        if (phone and not code) or (code and not phone):
            raise ValueError(
                "phone_number and country_code must be provided together"
            )

        return self

class UsernameCreate(BaseModel):
    username: str

class UsernameAvailabilityResponse(BaseModel):
    available: bool

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordrequest(BaseModel):
    token: str
    new_password: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UpdateRole(BaseModel):
    email: Optional[str] = None
    code: Optional[str] = None
    role: Optional[str] = None



class SendPhoneOtpRequest(BaseModel):
    phone_number: str
    country_code: str






class VerifyOtpRequest(BaseModel):
    otp: str




class ChangePasswordRequest(BaseModel):
    currentPassword: str
    new_password: str