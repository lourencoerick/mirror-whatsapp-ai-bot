import phonenumbers
from typing import Optional
from loguru import logger


# --- Helper Function (Synchronous) ---
def normalize_phone_number(
    phone_number: str,
    account_country_code: Optional[str] = "BR",
    is_simulation: Optional[bool] = False,
) -> Optional[str]:
    """
    Normalizes a phone number to E.164 digits format (without the leading '+').
    Suitable for WhatsApp Cloud API 'to' field.

    Args:
        phone_number: The phone number string to normalize.
        account_country_code: An optional default country code (e.g., 'BR', 'US')
                               to help parse numbers without a '+'.

    Returns:
        The normalized phone number digits based on E.164 format (e.g., '5511941986775'),
        or None if parsing fails or number is invalid.
    """
    if is_simulation:
        return phone_number

    if not phone_number:
        return None
    try:
        parsed_number = phonenumbers.parse(phone_number, account_country_code)
        if not phonenumbers.is_valid_number(parsed_number):
            logger.error(f"Invalid phone number provided: {phone_number}")
            return None
        e164_format = phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.E164
        )

        return e164_format.lstrip("+")
    except phonenumbers.NumberParseException:
        logger.error(f"Could not parse phone number: {phone_number}")
        return None
    except Exception as e:
        logger.error(f"Error normalizing phone number {phone_number}: {e}")
        return None
