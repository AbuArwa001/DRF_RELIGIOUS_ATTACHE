"""
Django Admin configuration for the competition app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Category, Registration, CompetitionSettings


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name_en', 'name_ar', 'juz_count', 'max_age', 'prize_display', 'order']
    list_editable = ['order']
    ordering = ['order']

    def prize_display(self, obj):
        return f"{obj.prize_sar:,} SAR"
    prize_display.short_description = _('Prize')


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'category', 'date_of_birth', 'age_display',
        'nominating_institution', 'status_badge', 'submitted_at',
    ]
    list_filter = ['status', 'category', 'submitted_at']
    search_fields = ['full_name', 'nominating_institution', 'email', 'phone_number']
    readonly_fields = [
        'submitted_at', 'updated_at', 'age_display',
        'id_document_preview', 'passport_photo_preview',
    ]
    list_per_page = 25
    date_hierarchy = 'submitted_at'

    fieldsets = (
        (_('Candidate Information'), {
            'fields': (
                'full_name', 'date_of_birth', 'age_display',
                'category', 'nominating_institution',
                'phone_number', 'email',
            )
        }),
        (_('Documents'), {
            'fields': ('id_document', 'id_document_preview', 'passport_photo', 'passport_photo_preview'),
        }),
        (_('Review'), {
            'fields': ('status', 'reviewer_notes'),
        }),
        (_('Metadata'), {
            'fields': ('submitted_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def age_display(self, obj):
        return f"{obj.age} years"
    age_display.short_description = _('Age')

    def status_badge(self, obj):
        colours = {
            'pending': '#f59e0b',
            'approved': '#10b981',
            'rejected': '#ef4444',
        }
        colour = colours.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    status_badge.allow_tags = True

    def id_document_preview(self, obj):
        if obj.id_document:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.id_document.url, _('View Document')
            )
        return '—'
    id_document_preview.short_description = _('Preview')

    def passport_photo_preview(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:4px;" />',
                obj.passport_photo.url
            )
        return '—'
    passport_photo_preview.short_description = _('Preview')


@admin.register(CompetitionSettings)
class CompetitionSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompetitionSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
