"""Telephony abstraction layer with Twilio + Exotel providers."""
from abc import ABC, abstractmethod
from typing import Dict, Any
import os
import logging

logger = logging.getLogger(__name__)


class TelephonyProvider(ABC):
    """Abstract base class for telephony providers."""

    @abstractmethod
    async def initiate_call(self, to_number: str, webhook_url: str, status_url: str) -> Dict[str, Any]:
        """Initiate an outbound call. Returns dict with 'call_sid'."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if provider has all required credentials."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider."""


class TwilioProvider(TelephonyProvider):
    """Twilio telephony provider."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.from_number = os.environ.get("TWILIO_PHONE_NUMBER")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "twilio"

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    def _get_client(self):
        if self._client is None and self.is_configured():
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    async def initiate_call(self, to_number: str, webhook_url: str, status_url: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER.")

        client = self._get_client()
        call = client.calls.create(
            to=to_number,
            from_=self.from_number,
            url=webhook_url,
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            timeout=45,
        )
        logger.info(f"Twilio call initiated to {to_number}, SID: {call.sid}")
        return {"call_sid": call.sid, "status": call.status}


class ExotelProvider(TelephonyProvider):
    """Exotel telephony provider (India-focused carrier)."""

    def __init__(self):
        self.sid = os.environ.get("EXOTEL_SID", "")
        self.api_key = os.environ.get("EXOTEL_API_KEY", "")
        self.api_token = os.environ.get("EXOTEL_API_TOKEN", "")
        self.subdomain = os.environ.get("EXOTEL_SUBDOMAIN", "api")
        self.phone_number = os.environ.get("EXOTEL_PHONE_NUMBER", "")

    @property
    def provider_name(self) -> str:
        return "exotel"

    def is_configured(self) -> bool:
        return bool(self.sid and self.api_key and self.api_token and self.phone_number)

    def _base_url(self) -> str:
        return f"https://{self.subdomain}.api.exotel.com/v1/Accounts/{self.sid}"

    async def initiate_call(self, to_number: str, webhook_url: str, status_url: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Exotel not configured. Set EXOTEL_SID, EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_PHONE_NUMBER.")

        import httpx
        url = f"{self._base_url()}/Calls/connect.json"
        data = {
            "From": to_number,
            "To": self.phone_number,
            "CallerId": self.phone_number,
            "Url": webhook_url,
            "StatusCallback": status_url,
            "StatusCallbackContentType": "application/json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, data=data, auth=(self.api_key, self.api_token), timeout=30
            )
            response.raise_for_status()
            result = response.json()
            call_data = result.get("Call", {})
            logger.info(f"Exotel call initiated to {to_number}, SID: {call_data.get('Sid')}")
            return {
                "call_sid": call_data.get("Sid", ""),
                "status": call_data.get("Status", ""),
            }


class TelephonyService:
    """Selects the active telephony provider from the TELEPHONY_PROVIDER env var."""

    def __init__(self):
        provider_name = os.environ.get("TELEPHONY_PROVIDER", "twilio").lower()
        if provider_name == "exotel":
            self.provider: TelephonyProvider = ExotelProvider()
        elif provider_name == "twilio":
            self.provider = TwilioProvider()
        else:
            self.provider = TwilioProvider()

    def is_configured(self) -> bool:
        return self.provider.is_configured()

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name


telephony_service = TelephonyService()
