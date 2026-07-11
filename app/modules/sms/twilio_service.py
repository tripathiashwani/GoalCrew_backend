# app/modules/sms/twilio_service.py
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.db.models.sms_log import SmsLog
from app.db.models.user import User
from app.utils.logger import get_logger

logger = get_logger("twilio-sms")
config = Config()


class TwilioSmsService:
    def __init__(self):
        self.client = Client(
            config.TWILIO_ACCOUNT_SID,
            config.TWILIO_AUTH_TOKEN,
        )
        self.messaging_service_sid = config.TWILIO_MESSAGING_SERVICE_SID

    async def send_sms(
        self,
        *,
        db: AsyncSession,
        user: User,
        message_type: str,
        body: str,
    ) -> None:
        """
        Sends SMS and ALWAYS persists SmsLog.
        Caller does not need to handle logging or errors.
        """

        phone = f"{user.country_code}{user.phone_number}"

        logger.info(
            f"📨 Sending SMS extra user_id: {str(user.id)},phone: {phone},type: {message_type}"
        )

        success = False
        provider_message_id = None
        error_message = None

        try:
            message = self.client.messages.create(
                messaging_service_sid=self.messaging_service_sid,
                body=body,
                to=phone,
            )

            success = True
            provider_message_id = message.sid

            logger.info(f"✅ SMS sent,user_id: {str(user.id)},phone: {phone},sid: {message.sid}, status: {message.status},")

        except TwilioRestException as e:
            error_message = e.msg
            logger.error(f"❌ Twilio SMS failed ,user_id: {str(user.id)},phone:{ phone},status: {e.status},code: e.code,error: {e.msg}")

        except Exception as e:
            error_message = str(e)
            logger.exception(f"Unexpected sms error user_id :{str(user.id)} phone:{phone}")

        finally:
            # ✅ ALWAYS persist attempt
            db.add(
                SmsLog(
                    user_id=user.id,
                    phone_number=phone,
                    message_type=message_type,
                    message=body,
                    success=success,
                    provider_message_id=provider_message_id,
                    error_message=error_message,
                )
            )
            await db.commit()
