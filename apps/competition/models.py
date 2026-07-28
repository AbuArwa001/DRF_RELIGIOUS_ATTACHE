"""
Competition app — models: Category, Registration, CompetitionSettings.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from .storage import (
    PassportPhotoStorage,
    IDDocumentStorage,
    passport_photo_upload_path,
    id_document_upload_path,
)


class Category(models.Model):
    """Memorisation category (e.g. 30 Juz', 20 Juz', 15 Juz', 5 Juz')."""

    name_en = models.CharField(_('Name (English)'), max_length=100)
    name_ar = models.CharField(_('Name (Arabic)'), max_length=100)
    juz_count = models.PositiveSmallIntegerField(_('Juz count'))
    max_age = models.PositiveSmallIntegerField(_('Maximum age (years)'))
    prize_sar = models.PositiveIntegerField(_('Prize (SAR)'))
    description_en = models.TextField(_('Description (English)'), blank=True)
    description_ar = models.TextField(_('Description (Arabic)'), blank=True)
    order = models.PositiveSmallIntegerField(_('Display order'), default=0)

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['order']

    def __str__(self):
        return f"{self.name_en} (max age: {self.max_age}, prize: {self.prize_sar:,} SAR)"


class Registration(models.Model):
    """Candidate registration for the Quran Competition."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    full_name = models.CharField(_('Full name'), max_length=255)
    date_of_birth = models.DateField(_('Date of birth'))
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='registrations',
        verbose_name=_('Category'),
    )
    nominating_institution = models.CharField(
        _('Nominating institution / school'), max_length=255
    )
    phone_number = models.CharField(_('Phone number'), max_length=30, blank=True)
    email = models.EmailField(_('Email address'), blank=True)

    # File uploads — stored in AWS S3 under: religionattche/<registrant_name>/
    id_document = models.FileField(
        _('ID document (National ID / Birth Cert / Passport)'),
        upload_to=id_document_upload_path,
        storage=IDDocumentStorage(),
    )
    passport_photo = models.ImageField(
        _('Passport photo (colour)'),
        upload_to=passport_photo_upload_path,
        storage=PassportPhotoStorage(),
    )

    # Review fields
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewer_notes = models.TextField(_('Reviewer notes'), blank=True)
    submitted_at = models.DateTimeField(_('Submitted at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)

    class Meta:
        verbose_name = _('Registration')
        verbose_name_plural = _('Registrations')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.full_name} — {self.category.name_en} ({self.status})"

    @property
    def age(self):
        from datetime import date
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class CompetitionSettings(models.Model):
    """Singleton model for editable competition dates and metadata."""

    registration_open = models.DateField(_('Registration opens'))
    registration_close = models.DateField(_('Registration closes'))
    preliminaries_date = models.DateField(_('Preliminaries date'))
    finals_date = models.DateField(_('Finals date'))
    venue_en = models.CharField(_('Venue (English)'), max_length=255, blank=True)
    venue_ar = models.CharField(_('Venue (Arabic)'), max_length=255, blank=True)
    about_en = models.TextField(_('About (English)'), blank=True)
    about_ar = models.TextField(_('About (Arabic)'), blank=True)

    class Meta:
        verbose_name = _('Competition Settings')
        verbose_name_plural = _('Competition Settings')

    def __str__(self):
        return f"Competition Settings (Finals: {self.finals_date})"

    def save(self, *args, **kwargs):
        # Enforce singleton
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'registration_open': '2025-09-20',
            'registration_close': '2025-10-13',
            'preliminaries_date': '2025-10-20',
            'finals_date': '2025-12-03',
            'venue_en': 'Nairobi, Kenya',
            'venue_ar': 'نيروبي، كينيا',
        })
        return obj
