"""English error messages. Served when Accept-Language asks for it."""

from app.errors.codes import ErrorCode

MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NOT_IMPLEMENTED: "This feature is not available yet.",
    ErrorCode.INTERNAL_ERROR: "Something went wrong on our side. Please retry.",
    ErrorCode.MALFORMED_REQUEST: "Malformed request.",
    ErrorCode.VALIDATION_FAILED: "Some fields are invalid.",
    ErrorCode.REQUEST_TOO_LARGE: "Request body is too large.",
    ErrorCode.REQUEST_TIMEOUT: "The request took too long to process.",
    ErrorCode.RATE_LIMITED: "Too many attempts. Wait before retrying.",
    ErrorCode.DEPENDENCY_UNAVAILABLE: "Service temporarily unavailable.",
    ErrorCode.METHOD_NOT_ALLOWED: "Method not allowed for this resource.",

    ErrorCode.UNAUTHENTICATED: "Authentication required.",
    ErrorCode.INVALID_TOKEN: "Invalid session. Please sign in again.",
    ErrorCode.TOKEN_EXPIRED: "Session expired. Please sign in again.",
    ErrorCode.FORBIDDEN_ROLE: "Your account cannot perform this action.",
    ErrorCode.ACCOUNT_SUSPENDED: "Your account is suspended.",
    ErrorCode.PHONE_NOT_ALLOWED: "That phone number is not accepted.",

    ErrorCode.OTP_CHALLENGE_NOT_FOUND: "Verification code not found or expired.",
    ErrorCode.OTP_INVALID: "Incorrect verification code.",
    ErrorCode.OTP_EXPIRED: "Verification code expired. Request a new one.",
    ErrorCode.OTP_ATTEMPTS_EXCEEDED: "Too many attempts. Request a new code.",

    ErrorCode.REFRESH_TOKEN_INVALID: "Invalid session. Please sign in again.",
    ErrorCode.REFRESH_TOKEN_REUSED: "Invalid session. Please sign in again.",

    ErrorCode.QUOTE_INVALID: "Invalid quote. Request a new price.",
    ErrorCode.QUOTE_EXPIRED: "Quote expired. Request a new price.",
    ErrorCode.QUOTE_ALREADY_USED: "That quote has already been used to create a ride.",
    ErrorCode.OUTSIDE_SERVICE_AREA: "That location is outside the served area.",

    ErrorCode.RIDE_NOT_FOUND: "No ride with that identifier is visible to you.",
    ErrorCode.RIDE_STATE_CONFLICT: "That action is not possible in the ride's current state.",
    ErrorCode.ACTIVE_RIDE_EXISTS: "You already have a ride in progress.",
    ErrorCode.OUTSTANDING_BALANCE: "You have an outstanding balance. Settle it before booking.",
    ErrorCode.IDEMPOTENCY_KEY_REQUIRED: "Idempotency-Key header is required.",
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: "That key was already used for a different request.",
    ErrorCode.PIN_INVALID: "Incorrect PIN.",
    ErrorCode.PIN_ATTEMPTS_EXCEEDED: "Too many PIN attempts. Contact support.",
    ErrorCode.SEATS_UNAVAILABLE: "Not enough seats available.",
    ErrorCode.MESSAGE_TEMPLATE_UNKNOWN: "Unknown message template.",

    ErrorCode.KYC_NOT_VERIFIED: "Your driver documents are not verified yet.",
    ErrorCode.DRIVER_NOT_ONLINE: "You must be online to do that.",
    ErrorCode.OFFER_NOT_FOUND: "Offer not found or expired.",
    ErrorCode.OFFER_TAKEN: "Another driver has already accepted this ride.",
    ErrorCode.OFFER_EXPIRED: "That offer has expired.",

    ErrorCode.SHARE_TOKEN_INVALID: "This tracking link is not valid.",
    ErrorCode.SHARE_TOKEN_EXPIRED: "This tracking link has expired.",

    ErrorCode.CORRIDOR_NOT_JOINABLE: "No compatible shared route was found.",
    ErrorCode.DETOUR_CAP_EXCEEDED: "The detour exceeds the allowed limit.",
    ErrorCode.DRIVER_CONSENT_REQUIRED: "The driver must approve this pickup.",

    ErrorCode.INCIDENT_NOT_FOUND: "Incident report not found.",
}

MESSAGES[ErrorCode.KYC_DOCUMENT_ALREADY_REGISTERED] = (
    "That document is already registered to another driver account."
)
