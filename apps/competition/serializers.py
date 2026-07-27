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
    """Public serializer for competition dates and venue."""

    class Meta:
        model = CompetitionSettings
        fields = [
            'registration_open', 'registration_close',
            'preliminaries_date', 'finals_date',
            'venue_en', 'venue_ar', 'about_en', 'about_ar',
        ]
        read_only_fields = fields


class RegistrationCreateSerializer(serializers.ModelSerializer):
    """
    Public serializer used when a candidate submits their registration.
    Handles multipart/form-data including file uploads.
    """
    id_document = serializers.FileField(required=True)
    passport_photo = serializers.ImageField(required=True)

    class Meta:
        model = Registration
        fields = [
            'id', 'full_name', 'date_of_birth', 'category',
            'nominating_institution', 'phone_number', 'email',
            'id_document', 'passport_photo', 'submitted_at',
        ]
        read_only_fields = ['id', 'submitted_at']

    def validate_id_document(self, value):
        validate_id_document(value)
        return value

    def validate_passport_photo(self, value):
        validate_passport_photo(value)
        return value

    def validate(self, attrs):
        dob = attrs.get('date_of_birth')
        category = attrs.get('category')
        if dob and category:
            validate_age_for_category(dob, category)
        return attrs


class RegistrationAdminSerializer(serializers.ModelSerializer):
    """
    Admin-only serializer for reviewing and updating registrations.
    Includes status, notes, and computed age.
    """
    age = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'id', 'full_name', 'date_of_birth', 'age',
            'category', 'category_name',
            'nominating_institution', 'phone_number', 'email',
            'id_document', 'passport_photo',
            'status', 'reviewer_notes',
            'submitted_at', 'updated_at',
        ]
        read_only_fields = ['id', 'age', 'category_name', 'submitted_at', 'updated_at']

    def get_age(self, obj):
        return obj.age

    def get_category_name(self, obj):
        return obj.category.name_en
