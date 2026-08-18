"""
Age and file validation logic for registrations.
"""
from datetime import date
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError


def calculate_age(dob: date) -> int:
    """Return the current age given a date of birth."""
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def normalize_phone(phone_str: str) -> str:
    """Normalize phone numbers to digits only, handling Kenyan local (07/01) & intl (+254) prefixes."""
    if not phone_str:
        return ''
    digits = ''.join(c for c in phone_str if c.isdigit())
    if digits.startswith('254') and len(digits) == 12:
        return digits[3:]
    if digits.startswith('0') and len(digits) == 10:
        return digits[1:]
    return digits


def validate_age_for_category(dob: date, category) -> None:
    """
    Raise ValidationError if the candidate's age exceeds the category's max_age.
    The error message is translatable so DRF returns it in the requested locale.
    """
    age = calculate_age(dob)
    if age > category.max_age:
        raise ValidationError(
            _(
                'Candidates for the %(category)s category must be %(max_age)s years old '
                'or younger. The provided date of birth gives an age of %(age)s years.'
            ) % {
                'category': category.name_en,
                'max_age': category.max_age,
                'age': age,
            }
        )
    if age < 5:
        raise ValidationError(_('The provided date of birth is not valid for competition entry.'))


def validate_id_document(file) -> None:
    """Restrict ID document to PDF, JPEG, PNG under 5 MB."""
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
    max_size = 5 * 1024 * 1024  # 5 MB

    if hasattr(file, 'content_type') and file.content_type not in allowed_types:
        raise ValidationError(
            _('ID document must be a PDF, JPEG, or PNG file.')
        )
    if file.size > max_size:
        raise ValidationError(
            _('ID document must not exceed 5 MB.')
        )


def validate_passport_photo(file) -> None:
    """Restrict passport photo to JPEG/PNG under 2 MB."""
    allowed_types = ['image/jpeg', 'image/png']
    max_size = 2 * 1024 * 1024  # 2 MB

    if hasattr(file, 'content_type') and file.content_type not in allowed_types:
        raise ValidationError(
            _('Passport photo must be a JPEG or PNG image.')
        )
    if file.size > max_size:
        raise ValidationError(
            _('Passport photo must not exceed 2 MB.')
        )


DISPOSABLE_DOMAINS = {
    'mailinator.com', 'tempmail.com', 'temp-mail.org', '10minutemail.com',
    'guerrillamail.com', 'sharklasers.com', 'throwawaymail.com', 'yopmail.com',
    'dispostable.com', 'trashmail.com', 'getairmail.com', 'maildrop.cc',
    'fakeinbox.com', 'mohmal.com', 'generator.email', 'tempinbox.com',
}

KNOWN_TYPO_DOMAINS = {
    'gamil.com', 'gmial.com', 'gmaill.com', 'gmil.com', 'gmai.com',
    'gmail.con', 'gmail.co', 'gmail.cm', 'gmal.com', 'gmaik.com',
    'gmeil.com', 'gnail.com', 'gemail.com', 'gmaul.com', 'gamil.con',
    'yaho.com', 'yahoo.con', 'yahoo.co', 'yhaoo.com', 'yhoo.com',
    'hotmial.com', 'hotmale.com', 'hotmaill.com', 'hotmai.com',
    'outlok.com', 'outllok.com', 'otlook.com', 'outlook.con',
    'icloude.com', 'iclod.com',
}


def validate_email_address(email_str: str) -> str:
    """
    Validate email address format, reject disposable/typo domains,
    and verify domain DNS deliverability.
    """
    import re
    import socket
    from django.core.validators import EmailValidator
    from django.core.exceptions import ValidationError as DjangoValidationError

    if not email_str:
        raise ValidationError(_('Email address is required.'))

    clean_email = email_str.strip().lower()

    if len(clean_email) > 254:
        raise ValidationError(_('Email address is too long.'))

    django_validator = EmailValidator()
    try:
        django_validator(clean_email)
    except DjangoValidationError:
        raise ValidationError(_('Please enter a valid email address.'))

    parts = clean_email.split('@')
    if len(parts) != 2:
        raise ValidationError(_('Please enter a valid email address.'))

    local_part, domain = parts

    if domain in KNOWN_TYPO_DOMAINS:
        raise ValidationError(
            _('The email domain "%(domain)s" appears to be a typo. Please check your email address.') % {'domain': domain}
        )

    if domain in DISPOSABLE_DOMAINS:
        raise ValidationError(_('Temporary or disposable email addresses are not permitted.'))

    # Basic DNS host resolution check for domain existence
    try:
        socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (socket.gaierror, socket.herror, OSError):
        raise ValidationError(
            _('The email domain "%(domain)s" could not be verified. Please check for spelling mistakes.') % {'domain': domain}
        )

    return clean_email

