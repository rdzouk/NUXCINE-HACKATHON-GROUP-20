"""French error messages. The default catalogue.

Messages are deliberately non-specific where specificity would leak state:
RIDE_NOT_FOUND reads the same whether the ride is absent or merely invisible
to the caller (I1), and the OTP messages never reveal whether a phone number
is registered.
"""

from app.errors.codes import ErrorCode

MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NOT_IMPLEMENTED: "Cette fonctionnalite n'est pas encore disponible.",
    ErrorCode.INTERNAL_ERROR: "Une erreur interne est survenue. Reessayez.",
    ErrorCode.MALFORMED_REQUEST: "Requete mal formee.",
    ErrorCode.VALIDATION_FAILED: "Certains champs sont invalides.",
    ErrorCode.REQUEST_TOO_LARGE: "Requete trop volumineuse.",
    ErrorCode.REQUEST_TIMEOUT: "Le traitement a pris trop de temps.",
    ErrorCode.RATE_LIMITED: "Trop de tentatives. Patientez avant de reessayer.",
    ErrorCode.DEPENDENCY_UNAVAILABLE: "Service temporairement indisponible.",
    ErrorCode.METHOD_NOT_ALLOWED: "Methode non autorisee pour cette ressource.",

    ErrorCode.UNAUTHENTICATED: "Authentification requise.",
    ErrorCode.INVALID_TOKEN: "Session invalide. Reconnectez-vous.",
    ErrorCode.TOKEN_EXPIRED: "Session expiree. Reconnectez-vous.",
    ErrorCode.FORBIDDEN_ROLE: "Votre compte n'a pas acces a cette action.",
    ErrorCode.ACCOUNT_SUSPENDED: "Votre compte est suspendu.",
    ErrorCode.PHONE_NOT_ALLOWED: "Ce numero de telephone n'est pas accepte.",

    ErrorCode.OTP_CHALLENGE_NOT_FOUND: "Code de verification introuvable ou expire.",
    ErrorCode.OTP_INVALID: "Code de verification incorrect.",
    ErrorCode.OTP_EXPIRED: "Code de verification expire. Demandez-en un nouveau.",
    ErrorCode.OTP_ATTEMPTS_EXCEEDED: "Trop de tentatives. Demandez un nouveau code.",

    ErrorCode.REFRESH_TOKEN_INVALID: "Session invalide. Reconnectez-vous.",
    ErrorCode.REFRESH_TOKEN_REUSED: "Session invalide. Reconnectez-vous.",

    ErrorCode.QUOTE_INVALID: "Estimation invalide. Demandez un nouveau tarif.",
    ErrorCode.QUOTE_EXPIRED: "Estimation expiree. Demandez un nouveau tarif.",
    ErrorCode.QUOTE_ALREADY_USED: "Cette estimation a deja servi a creer une course.",
    ErrorCode.OUTSIDE_SERVICE_AREA: "Ce point est hors de la zone desservie.",

    ErrorCode.RIDE_NOT_FOUND: "Aucune course correspondante n'est visible pour vous.",
    ErrorCode.RIDE_STATE_CONFLICT: "Cette action n'est pas possible dans l'etat actuel de la course.",
    ErrorCode.ACTIVE_RIDE_EXISTS: "Vous avez deja une course en cours.",
    ErrorCode.OUTSTANDING_BALANCE: "Un solde reste du. Reglez-le avant de reserver.",
    ErrorCode.IDEMPOTENCY_KEY_REQUIRED: "En-tete Idempotency-Key requis.",
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: "Cette cle a deja servi pour une requete differente.",
    ErrorCode.PIN_INVALID: "Code PIN incorrect.",
    ErrorCode.PIN_ATTEMPTS_EXCEEDED: "Trop de tentatives de PIN. Contactez le support.",
    ErrorCode.SEATS_UNAVAILABLE: "Plus assez de places disponibles.",
    ErrorCode.MESSAGE_TEMPLATE_UNKNOWN: "Message predefini inconnu.",

    ErrorCode.KYC_NOT_VERIFIED: "Votre dossier chauffeur n'est pas encore valide.",
    ErrorCode.DRIVER_NOT_ONLINE: "Vous devez etre en ligne pour cette action.",
    ErrorCode.OFFER_NOT_FOUND: "Proposition introuvable ou expiree.",
    ErrorCode.OFFER_TAKEN: "Cette course a deja ete acceptee par un autre chauffeur.",
    ErrorCode.OFFER_EXPIRED: "Cette proposition a expire.",

    ErrorCode.SHARE_TOKEN_INVALID: "Ce lien de suivi n'est pas valide.",
    ErrorCode.SHARE_TOKEN_EXPIRED: "Ce lien de suivi a expire.",

    ErrorCode.CORRIDOR_NOT_JOINABLE: "Aucun trajet partage compatible n'a ete trouve.",
    ErrorCode.DETOUR_CAP_EXCEEDED: "Le detour depasse la limite autorisee.",
    ErrorCode.DRIVER_CONSENT_REQUIRED: "Le chauffeur doit accepter ce ramassage.",

    ErrorCode.INCIDENT_NOT_FOUND: "Signalement introuvable.",
}
