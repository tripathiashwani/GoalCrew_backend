# app/modules/users/service.py
from datetime import time
import hashlib
from typing import Optional

from firebase_admin import auth as firebase_auth
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi import HTTPException, UploadFile, status

from app.db.models.user import User
from app.db.models.user_preferences import UserPreference
from app.modules.users.schemas import UserCreate, UserLogin, UserRead, UserUpdate,UpdateRole, ChangePasswordRequest
from app.utils.email_utils import send_email
from app.utils.file_upload import save_user_avatar
from app.utils.password_reset import create_password_reset_token, verify_password_reset_token
from app.utils.security import hash_password, verify_password  # create this module
from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType
from app.modules.sms.twilio_service import TwilioSmsService
import re
from sqlalchemy import select
from fastapi import HTTPException, status
from app.config import Config
import secrets
import random

config = Config()

from app.utils.logger import get_logger
logger = get_logger("UserService")
exception_logger=get_logger("Exceptions_logs")

USERNAME_REGEX = re.compile(r"^[a-z0-9]{3,20}$")


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)





def generate_otp():
    return str(random.randint(100000, 999999))


class UserService:
    async def send_verification_email(self, to_email: str, verify_link: str, user_name: str = "User"):
        subject = "Verify your email – GoalCrew"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6;">
        <h2 style="color:#1e3a8a;">Hi {user_name},</h2>

        <p>Thanks for signing up for <strong>GoalCrew</strong>!</p>

        <p>Verify your email to get started:</p>
        <p style="margin: 20px 0;">
            <a href="{verify_link}" 
            style="background-color:#2563eb; color:white; padding:12px 24px; border-radius:6px; text-decoration:none; font-weight:bold;">
            Verify My Email
            </a>
        </p>

        <p>Once verified, you can:</p>
        <ul>
            <li>✓ Create your Pods</li>
            <li>✓ Add your goals</li>
            <li>✓ Share your progress</li>
        </ul>

        <p>Questions? Just reply to this email — we’re happy to help!</p>

        <p style="margin-top: 24px;">Welcome aboard,<br>
        <strong>The GoalCrew Team</strong></p>

        <hr style="margin-top: 32px; border:none; border-top:1px solid #ddd;">
        <p style="font-size: 12px; color: #666;">
            If you didn’t create a GoalCrew account, you can safely ignore this email.
        </p>
        </body>
        </html>
        """
        try:

            send_email(to_email, subject, body)
        
        except Exception as e:
            exception_logger.exception(f"Error while sending verification email: {str(e)}")
            

    async def create_user(self, session: AsyncSession, user_create: UserCreate) -> UserRead:
        logger.info(f"Creating user with email={user_create.email}")

        try:
            # Check if email already exists
            stmt = select(User).where(User.email == user_create.email)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                logger.warning(f"Attempt to register existing email: {user_create.email}")
                raise ValueError("Email is already registered")

            password_hash = hash_password(user_create.password)

            # firebase_user = firebase_auth.create_user(display_name=user_create.name ,email=user_create.email,phone_number=user_create.phone_number, country_code=user_create.country_code)
            
                
            try:


                firebase_user = firebase_auth.create_user(
                    display_name=user_create.name,
                    email=user_create.email
                )
            
            except Exception as e:
                exception_logger.info(f"Error while creating user: {str(e)}")
                raise ValueError("Error in saving to firebase")


            verification_token = generate_verification_token()

            user = User(
                firebase_uid=firebase_user.uid,  
                email=user_create.email,
                name=user_create.name,
                password_hash=password_hash,
                phone_number=user_create.phone_number,
                country_code=user_create.country_code,
                verification_token=verification_token,
                is_verified=False,
            )

            session.add(user)
            await session.flush()        
            # Create DEFAULT UserPreference
            preferences = UserPreference(
                user_id=user.id,     
                checkin_time= time(9, 0),
                # defaults will auto-apply:
                # checkin_frequency="daily"
                # pod_updates_enabled=True
                # photo_expiration="7d"
            )
            session.add(preferences)
            await session.commit()
            await session.refresh(user)

            # Send verification email in background
            # Build verification link
            verify_link = (
                f"{config.FRONTEND_URL}/auth/verify-email?"
                f"token={verification_token}"
            )

            await self.send_verification_email(
                to_email=user.email,
                verify_link=verify_link,
                user_name=user.name or "User",
            )

            await dispatcher.emit(
                DomainEvent(
                    type=NotificationType.ACCOUNT_CREATED,
                    actor_id=user.id,
                    entity_type="account",
                    entity_id=user.id,
                    context={
                        "actor_name": user.name or "Someone",
                        "details":f"{user.name} created new account" or "Someone",
                        "target_ids":[user.id]
                    },
                )
            )
            logger.info(f"User created successfully id={user.id}, email={user.email}, create at={user.created_at}")
            return UserRead.model_validate(user)
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            exception_logger.info(f"Error while creating user: {str(e)}")
            raise 

    async def login_user(self, session: AsyncSession, login_data: UserLogin) -> str:
        logger.info(f"Login attempt for email={login_data.email}")

        # 1️⃣ Look up user locally
        stmt = select(User).where(User.email == login_data.email)
        result = await session.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Login failed. Unknown email={login_data.email}")
            exception_logger.warning(f"Login failed. Unknown email={login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_user",
                    "message": "User does not exist!",
                },
            )
        
        if not verify_password(login_data.password, user.password_hash):
            logger.warning(f"Login failed. Incorrect password for email={login_data.email}")
            exception_logger.warning(f"Login failed. Incorrect password for email={login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_credentials",
                    "message": "Invalid email or password",
                },
            )
        
        if not user.is_verified:
            exception_logger.warning(f"Login failed. Incorrect password for email={login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "email_not_verified",
                    "message": "Please verify your email before logging in",
                },
            )
        logger.info(f"Generating Firebase custom token for firebase_uid={user.firebase_uid}")

        # 3️⃣ Generate custom Firebase token using our own UID
        custom_token = firebase_auth.create_custom_token(user.firebase_uid)

        # create_custom_token returns bytes
        return custom_token.decode("utf-8")

    async def get_user_by_firebase_uid(self, session: AsyncSession, firebase_uid: str) -> Optional[User]:
        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, session: AsyncSession, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def resend_verification_email(
        self,
        session: AsyncSession,
        email: str,
    ):       
        
        verification_token = generate_verification_token()
        verify_link = (
                    f"{config.FRONTEND_URL}/auth/verify-email?"
                    f"token={verification_token}"
                )
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        user.verification_token = verification_token
        await session.commit()
        logger.info(f"Resending verification email to {user.email} token={verification_token}")
        await self.send_verification_email(
            to_email=user.email,
            verify_link=verify_link,
            user_name=user.name or "User",
        )

    # async def update_user_profile(self, session: AsyncSession, user_id: str, user_update: UserUpdate) -> Optional[UserRead]:
    #     # optional: implement later
    #     ...

    async def set_username(
        self,
        session: AsyncSession,
        user: User,
        username: str,
    ):
        username = username.strip().lower()
        logger.info(f"setting user name :{username}")

        if not USERNAME_REGEX.match(username):
            exception_logger.warning(f"Username must be 3–20 characters")
            raise HTTPException(
                status_code=400,
                detail="Username must be 3–20 characters, lowercase letters and numbers only",
            )

        # Check uniqueness
        exists = await session.scalar(
            select(User.id).where(User.username == username)
        )
        if exists:
            exception_logger.exception(f"Username already taken while setting username")
            raise HTTPException(
                status_code=409,
                detail="Username already taken",
            )

        user.username = username
        await session.commit()
        await session.refresh(user)

        return user

    async def update_user(
        self,
        db: AsyncSession,
        user: User,
        payload: UserUpdate,
    ):
        try:

            PHONE_REGEX = re.compile(r"^\d{6,15}$")     # E.164 max is 15 digits
            COUNTRY_CODE_REGEX = re.compile(r"^\+\d{1,4}$")

            if payload.name is not None:
                user.name = payload.name.strip()

            # ---------- PHONE VALIDATION ----------
            if payload.phone_number is not None or payload.country_code is not None:

                # Explicit clear
                if payload.phone_number == "" and payload.country_code == "":
                    user.phone_number = None
                    user.country_code = None

                else:
                    phone = payload.phone_number
                    code = payload.country_code

                    if not phone or not code:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Both phone_number and country_code are required",
                        )

                    if not COUNTRY_CODE_REGEX.match(code):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid country_code format (example: +1, +91)",
                        )

                    if not PHONE_REGEX.match(phone):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid phone_number format",
                        )

                    user.phone_number = phone
                    user.country_code = code
                    user.is_phone_verified=False

            # ---------- ONBOARDING ----------
            if payload.is_onboarded is not None:
                user.is_onboarded = payload.is_onboarded

            await db.commit()
            await db.refresh(user)
            return user
        
        except Exception as e:
            exception_logger.exception(f"Error while updating user:{str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Something went wrong",
            )



    async def check_username_availability(
        self,
        session: AsyncSession,
        username: str,
    ) -> bool:
        username = (username or "").strip()

        if not USERNAME_REGEX.match(username):
            # invalid format
            raise ValueError(
                "Invalid username. Use 3–20 characters: lowercase letters, numbers, underscores only."
            )

        existing = await session.scalar(
            select(User.id).where(User.username == username)
        )
        return existing is None
    
    async def send_forgot_password_email(
        self,
        to_email: str,
        reset_link: str,
        user_name: str = "User",
    ):
        try:
                
            subject = "Reset your password – GoalCrew"

            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #222;">
                <h2>Hi {user_name},</h2>

                <p>You requested to reset your password.</p>

                <p style="margin:20px 0;">
                    <a href="{reset_link}"
                    style="background:#2563eb;color:white;padding:12px 24px;
                            border-radius:6px;text-decoration:none;font-weight:bold;">
                    Reset Password
                    </a>
                </p>

                <p>This link will expire in 1 Hour.</p>

                <p>If you didn’t request this, you can ignore this email.</p>

                <p><strong>The GoalCrew Team</strong></p>
            </body>
            </html>
            """

            try:

                send_email(to_email, subject, body)
            
            except Exception as e:
                exception_logger.exception(f"Error while sending forgot password email: {str(e)}")
                
        
        except Exception as e:
            exception_logger.exception(f"Error while send forgot password email:{str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )


    async def forgot_password(
        self,
        session: AsyncSession,
        email: str,
    ):
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # 🔐 Do NOT reveal user existence
        if not user:
            logger.info(f"Forgot password requested for unknown email: {email}")
            return

        raw_token, hashed_token = create_password_reset_token(user.email)

        user.reset_token = hashed_token
        await session.commit()

        reset_link = (
            f"{config.FRONTEND_URL}/reset-password?"
            f"token={raw_token}"
        )

        await self.send_forgot_password_email(
            to_email=user.email,
            reset_link=reset_link,
            user_name=user.name or "User",
        )

        logger.info(f"Password reset email sent to {user.email}")

    async def reset_password(
        self,
        session: AsyncSession,
        token: str,
        new_password: str,
    ):
        
        try:
                
            email = verify_password_reset_token(token)

            token_hash = hashlib.sha256(token.encode()).hexdigest()

            stmt = select(User).where(
                User.email == email,
                User.reset_token == token_hash,
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or already-used reset token",
                )

            user.password_hash = hash_password(new_password)
            user.reset_token = None  
            await session.commit()

            logger.info(f"Password successfully reset for {email}")

        except Exception as e:
            exception_logger.exception(f"Error while resetting password: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )

    async def add_user_avatar_service(
        self,
        db: AsyncSession,
        user: User,
        file: UploadFile,
    ):
        try:
            if not file:
                raise HTTPException(
                    status_code=400,
                    detail="No file provided",
                )

            # Save file
            file_url, file_type = save_user_avatar(
                user_id=str(user.id),
                file=file,
                upload_root=config.BASE_DIR/ "uploads" / "avatar",
            )

            # Update user profile photo URL
            user.profile_photo_url = file_url
            await db.commit()
            await db.refresh(user)

            return {
                "message": "Profile photo updated successfully",
                "profile_photo_url": file_url,
                "file_type": file_type,
            }
        
        except Exception as e:
            exception_logger.exception(f"Error while adding user avatar service: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )
    


    async def update_role(
        self,
        session: AsyncSession,
        payload: UpdateRole,
    ):
        try:
            email=payload.email
            role=payload.role
            code=payload.code

            if code !="992@3BcD":
                raise HTTPException(
                    status_code=400,
                    detail="Not authorized to change role",
                )


            stmt = select(User).where(
                User.email == email
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.info(f"user with email :{email} does not exits to change role to:{role} using code:{code}")
                raise HTTPException(
                    status_code=400,
                    detail="user with this email does not exits",
                )

            user.role=role
            await session.commit()
            logger.info(f"user with email :{email} to change role to:{role} using code:{code} successfully changed")
            return {
                "message": f"user with email :{email} to change role to:{role} using code:{code} successfully changed"
            }
        
        except Exception as e:
            exception_logger.exception(f"Error while updating role: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )


    async def send_otp(
        self,db,current_user
    ):
        try:
            logger.info(f"send otp user service trying to send otp for user :{current_user.email}")


            if not current_user.phone_number:
                raise HTTPException(400, "Phone number not saved")

            otp = generate_otp()

            current_user.otp_code = otp

            await db.commit()

            phone = f"{current_user.country_code}{current_user.phone_number}"
            sms = TwilioSmsService()

            await sms.send_sms(
            db=db,
            user=current_user,
            message_type="otp_verification",
            body=f"Your OTP :{otp}",
        ) 

            return {"success": True}
        except Exception as e:
            return {"success": False}
        

    
    async def change_password(
    self,
    db: AsyncSession,
    payload: ChangePasswordRequest,
    current_user: User
    ):
        try:
            logger.info(f"Changing password of user: {current_user.name}")

            if not verify_password(payload.currentPassword, current_user.password_hash):
                logger.info("Current password incorrect")
                raise HTTPException(status_code=400, detail="Current password incorrect")

            current_user.password_hash = hash_password(payload.new_password)

            await db.commit()

            logger.info(f"Password changed successfully for user: {current_user.name}")

            return {"success": True}

        except HTTPException:
            raise   # <-- VERY IMPORTANT

        except Exception as e:
            logger.error(f"Failed to change password: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to change password")