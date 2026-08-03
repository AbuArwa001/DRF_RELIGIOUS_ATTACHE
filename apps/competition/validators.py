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
