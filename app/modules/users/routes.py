from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import UUID, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_session
from app.dependencies import get_current_user
from app.modules.users.schemas import ForgotPasswordRequest, ResendVerificationRequest, ResetPasswordrequest, UserCreate, UserLogin, UserRead, UserUpdate, UsernameCreate, UsernameAvailabilityResponse,UpdateRole, VerifyOtpRequest,ChangePasswordRequest
from app.modules.users.service import UserService
from app.utils.logger import get_logger
from fastapi import Query


router = APIRouter(prefix="/users", tags=["Auth"])
service = UserService()
logger = get_logger("UserRoutes")
exception_logger=get_logger("Exceptions_logs")


@router.post("/register", response_model=UserRead)
async def register_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    logger.info(f"POST /register — data={user_create}")
    try:
        return await service.create_user(session, user_create)
    except ValueError as e:
        exception_logger.info(f"Registration Failed: {str(e)}")
        logger.info(f"Registration failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(
    user_login: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    """
    Login
    """
    custom_token = await service.login_user(session, user_login)
    return {"custom_token": custom_token}


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user=Depends(get_current_user)) -> UserRead:
    return current_user

@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.update_user(db, current_user, payload)

@router.post("/username", response_model=UserRead)
async def add_username(
    payload: UsernameCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.set_username(
        session=session,
        user=current_user,
        username=payload.username,
    )


@router.get("/check-username", response_model=UsernameAvailabilityResponse)
async def check_username(
    username: str = Query(..., min_length=3, max_length=20),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Check if a username is available.
    Requires auth (same as frontend expects Bearer token).
    """
    try:
        available = await service.check_username_availability(session, username)
        return {"available": available}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/verify-email")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(User).where(User.verification_token == token)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token",
        )

    user.is_verified = True
    user.verification_token = None
    await session.commit()

    return {"message": "Email verified successfully"}

@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    await service.forgot_password(session, payload.email)

    return {
        "message": "If the email exists, a reset link has been sent"
    }

@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordrequest,
    session: AsyncSession = Depends(get_session),
):
    await service.reset_password(session, payload.token, payload.new_password)
    return {"message": "Password reset successful"}


@router.post("/update-avatar")
async def update_user_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.add_user_avatar_service(
        db=db,
        user=user,
        file=file,
    )





@router.post("/resend-verification-email")
async def resend_verification_email(
    payload: ResendVerificationRequest,
    session: AsyncSession = Depends(get_session),
):

    await service.resend_verification_email(
        session=session,
        email=payload.email,
    )

    return {"message": "If the email exists, a reset link has been sent"}




@router.post("/change-role")
async def update_user_role(
    payload: UpdateRole,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.update_role(
        session=db,
        payload=payload,
    )






@router.post("/send-phone-otp")
async def send_phone_otp(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    
    logger.info(f"user :{current_user.username} called to send phone otp  ")
    return await service.send_otp(
        db=db,
        current_user=current_user,
    )







@router.post("/verify-phone-otp")
async def verify_phone_otp(
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"veriying otp of user :{current_user.name} with otp :{payload}")

    if not current_user.otp_code:
        logger.info(f"otp not generated of user {current_user.name}")
        raise HTTPException(400, "OTP not generated")

    if current_user.otp_code != payload.otp:
        logger.info(f"otp not correct of user {current_user.name}, payload otp : {payload} , correct otp:{current_user.otp_code} ")
        raise HTTPException(400, "Invalid OTP")

    current_user.is_phone_verified = True
    current_user.otp_code = None

    await db.commit()

    return {"success": True}

    

@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    

    return await service.change_password(db,payload,current_user)