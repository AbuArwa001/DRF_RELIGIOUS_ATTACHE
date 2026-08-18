"""
DRF serializers for the competition app.
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Category, Registration, CompetitionSettings
from .validators import (
    validate_age_for_category,
    validate_id_document,
    validate_passport_photo,
    validate_email_address,
    normalize_phone,
)


class CategorySerializer(serializers.ModelSerializer):
    """Public read-only serializer for competition categories."""

    class Meta:
        model = Category
        fields = [
            'id', 'name_en', 'name_ar', 'juz_count',
            'max_age', 'prize_sar', 'description_en', 'description_ar', 'order',
        ]
        read_only_fields = fields


class CompetitionInfoSerializer(serializers.ModelSerializer):
    """Public read-only serializer for competition dates and venue."""
    county_stats = serializers.SerializerMethodField()
    category_stats = serializers.SerializerMethodField()
    category_county_stats = serializers.SerializerMethodField()

    class Meta:
        model = CompetitionSettings
        fields = [
            'registration_open', 'registration_close',
            'preliminaries_date', 'preliminaries_end_date',
            'finals_date', 'finals_end_date',
            'venue_en', 'venue_ar', 'about_en', 'about_ar',
            'county_registration_limit', 'county_stats',
            'category_registration_limit', 'category_stats',
            'category_county_stats',
        ]
        read_only_fields = fields

    def get_county_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('county').annotate(count=Count('id'))
        return {item['county']: item['count'] for item in qs if item['county']}

    def get_category_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('category').annotate(count=Count('id'))
        return {item['category']: item['count'] for item in qs if item['category'] is not None}

    def get_category_county_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('category', 'county').annotate(count=Count('id'))
        stats = {}
        for item in qs:
            cat_id = item['category']
            county = item['county']
            if cat_id is not None and county:
                if cat_id not in stats:
                    stats[cat_id] = {}
                stats[cat_id][county] = item['count']
        return stats


class CompetitionInfoAdminSerializer(serializers.ModelSerializer):
    """
    Admin-only writable serializer for CompetitionSettings.
    All fields are editable; supports partial updates (PATCH).
    """
    county_stats = serializers.SerializerMethodField(read_only=True)
    category_stats = serializers.SerializerMethodField(read_only=True)
    category_county_stats = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CompetitionSettings
        fields = [
            'registration_open', 'registration_close',
            'preliminaries_date', 'preliminaries_end_date',
            'finals_date', 'finals_end_date',
            'venue_en', 'venue_ar', 'about_en', 'about_ar',
            'county_registration_limit', 'county_stats',
            'category_registration_limit', 'category_stats',
            'category_county_stats',
        ]

    def get_county_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('county').annotate(count=Count('id'))
        return {item['county']: item['count'] for item in qs if item['county']}

    def get_category_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('category').annotate(count=Count('id'))
        return {item['category']: item['count'] for item in qs if item['category'] is not None}

    def get_category_county_stats(self, obj):
        from django.db.models import Count
        qs = Registration.objects.values('category', 'county').annotate(count=Count('id'))
        stats = {}
        for item in qs:
            cat_id = item['category']
            county = item['county']
            if cat_id is not None and county:
                if cat_id not in stats:
                    stats[cat_id] = {}
                stats[cat_id][county] = item['count']
        return stats


class RegistrationCreateSerializer(serializers.ModelSerializer):
    """
    Public serializer used when a candidate submits their registration.
    Handles multipart/form-data including file uploads.
    """
    category       = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=True,
        error_messages={'required': _('Memorisation category is required.')}
    )
    email          = serializers.EmailField(
        required=True,
        error_messages={'required': _('Email address is required.')}
    )
    id_document    = serializers.FileField(required=True)
    passport_photo = serializers.ImageField(required=True)

    class Meta:
        model  = Registration
        fields = [
            'id', 'full_name', 'date_of_birth',
            'nationality', 'national_id_number', 'current_residence', 'county',
            'category', 'nominating_institution',
            'phone_number', 'alternative_phone', 'email',
            'id_document', 'passport_photo',
            'submitted_at',
        ]
        read_only_fields = ['id', 'submitted_at']

    def validate_id_document(self, value):
        validate_id_document(value)
        return value

    def validate_passport_photo(self, value):
        validate_passport_photo(value)
        return value

    def validate_email(self, value):
        return validate_email_address(value)

    def validate(self, attrs):
        dob      = attrs.get('date_of_birth')
        category = attrs.get('category')
        if dob and category:
            validate_age_for_category(dob, category)

        # ── Double registration prevention ──────────────────────────────────
        active_regs = Registration.objects.all()

        nat_id = (attrs.get('national_id_number') or '').strip()
        if nat_id:
            if active_regs.filter(national_id_number__iexact=nat_id).exists():
                raise serializers.ValidationError({
                    "national_id_number": _("A participant with this National ID / Passport number is already registered.")
                })


        
        county = attrs.get('county')

        if category and county:
            limit = 10  # Enforced 10 spots per category per county as requested
            count = Registration.objects.filter(category=category, county=county).count()
            if count >= limit:
                raise serializers.ValidationError({
                    "category": _(f"Registration limit of {limit} reached for {category.name_en} in {county} county.")
                })

        return attrs


class RegistrationAdminSerializer(serializers.ModelSerializer):
    """
    Admin-only serializer for reviewing and updating registrations.
    Includes all personal details, status, notes, computed age, and allows file updates.
    """
    age           = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    category_juz_count = serializers.SerializerMethodField()
    id_document   = serializers.FileField(required=False, allow_null=True)
    passport_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model  = Registration
        fields = [
            'id', 'full_name', 'date_of_birth', 'age',
            'nationality', 'national_id_number', 'current_residence', 'county',
            'category', 'category_name', 'category_juz_count',
            'nominating_institution', 'phone_number', 'alternative_phone', 'email',
            'id_document', 'passport_photo',
            'status', 'reviewer_notes',
            'submitted_at', 'updated_at',
        ]
        read_only_fields = ['id', 'age', 'category_name', 'category_juz_count', 'submitted_at', 'updated_at']

    def validate_id_document(self, value):
        if value:
            validate_id_document(value)
        return value

    def validate_passport_photo(self, value):
        if value:
            validate_passport_photo(value)
        return value

    def validate_email(self, value):
        if value:
            return validate_email_address(value)
        return value

    def validate(self, attrs):
        dob = attrs.get('date_of_birth') or (self.instance.date_of_birth if self.instance else None)
        category = attrs.get('category') or (self.instance.category if self.instance else None)
        if dob and category:
            validate_age_for_category(dob, category)
        return attrs

    def get_age(self, obj):
        return obj.age

    def get_category_name(self, obj):
        return getattr(obj.category, 'name_en', None)

    def get_category_juz_count(self, obj):
        return getattr(obj.category, 'juz_count', None)


