import httpx
import logging
AUTH_HEADERS = {
    "auth-key": "Web2@!9",
    "end-client": "Lotus-Web"
}

# Remote API endpoints
CHECK_USER_URL = "https://portal.lotuselectronics.com/web-api/user/check_user"
SEND_OTP_URL = "https://portal.lotuselectronics.com/web-api/user/send_otp"
VERIFY_OTP_URL = "https://portal.lotuselectronics.com/web-api/user/signin"

async def check_user(phone: str) -> dict:
    data = {"user_name": phone, "btn": "0"}
    async with httpx.AsyncClient() as client:
        response = await client.post(CHECK_USER_URL, data=data, headers=AUTH_HEADERS)
        return response.json()



check_user_schema = {
    "name": "check_user",
    "description": "Check if a phone number is registered.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {"type": "string"}
        },
        "required": ["phone"]
    }
}
logger = logging.getLogger(__name__)
# async def send_otp(phone: str) -> dict:
#     data = {"user_name": phone}
#     async with httpx.AsyncClient() as client:
#         response = await client.post(SEND_OTP_URL, data=data, headers=AUTH_HEADERS)
#         return response.json()

async def send_otp(phone: str) -> dict:
    data = {"user_name": phone}

    try:
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(SEND_OTP_URL, data=data, headers=AUTH_HEADERS)
            response.raise_for_status()
            return response.json()

    except httpx.ReadTimeout:
        logger.error("OTP request timed out for phone: %s", phone)
        return {
            "status": "error",
            "data": {
                "answer": "We're currently unable to reach our OTP service. Please try again in a moment."
            }
        }

    except httpx.HTTPStatusError as exc:
        logger.error("OTP request failed: %s", exc.response.text)
        return {
            "status": "error",
            "data": {
                "answer": f"OTP request failed with status code {exc.response.status_code}."
            }
        }

    except Exception as e:
        logger.exception("Unexpected error during OTP sending")
        return {
            "status": "error",
            "data": {
                "answer": "An unexpected error occurred while sending the OTP."
            }
        }



send_otp_schema = {
    "name": "send_otp",
    "description": "Send an OTP to the user's phone number.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {"type": "string"}
        },
        "required": ["phone"]
    }
}

async def verify_otp(phone: str, otp: str, session_id: str) -> dict:
    data = {"user_name": phone, "password": otp, "is_otp": "1"}
    async with httpx.AsyncClient() as client:
        response = await client.post(VERIFY_OTP_URL, data=data, headers=AUTH_HEADERS)
        result = response.json()
        # If successful, add session_id to result for tracking
        if result.get("error") == "0":
            result["session_id"] = session_id
            auth_token = (
                result.get("auth_token") or
                (result.get("data", {}).get("auth_token") if isinstance(result.get("data"), dict) else None)
            )
            if auth_token:
                result["auth_token"] = auth_token
        return result

verify_otp_schema = {
    "name": "verify_otp",
    "description": "Verify the OTP for the user's phone number and session.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "otp": {"type": "string"},
            "session_id": {"type": "string"}
        },
        "required": ["phone", "otp", "session_id"]
    }
}

async def sign_in(phone: str, password: str, session_id: str) -> dict:
    data = {"user_name": phone, "password": password, "is_otp": "0"}
    async with httpx.AsyncClient() as client:
        response = await client.post(VERIFY_OTP_URL, data=data, headers=AUTH_HEADERS)
        result = response.json()
        if result.get("error") == "0":
            result["session_id"] = session_id
            auth_token = (
                result.get("auth_token") or
                (result.get("data", {}).get("auth_token") if isinstance(result.get("data"), dict) else None)
            )
            if auth_token:
                result["auth_token"] = auth_token
        return result

sign_in_schema = {
    "name": "sign_in",
    "description": "Sign in the user with phone and password (not OTP).",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "password": {"type": "string"},
            "session_id": {"type": "string"}
        },
        "required": ["phone", "password", "session_id"]
    }
}

tool_registry = {
    # ... other tools ...
    "send_otp": (send_otp, send_otp_schema),
    # "verify_otp": (verify_otp, verify_otp_schema),
    "sign_in": (sign_in, sign_in_schema),
}
