"""
Management command: seed initial competition categories and settings.
Usage: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.competition.models import Category, CompetitionSettings

User = get_user_model()

CATEGORIES = [
    {
        'name_en': "30 Juz'",
        'name_ar': "٣٠ جزءاً",
        'juz_count': 30,
        'max_age': 24,
        'prize_sar': 20000,
        'description_en': "Full Quran memorisation (all 30 Juz'). Open to candidates aged 24 and below.",
        'description_ar': "حفظ القرآن الكريم كاملاً (٣٠ جزءاً). مفتوح للمتسابقين الذين لا تتجاوز أعمارهم ٢٤ سنة.",
        'order': 1,
    },
    {
        'name_en': "20 Juz'",
        'name_ar': "٢٠ جزءاً",
        'juz_count': 20,
        'max_age': 22,
        'prize_sar': 15000,
        'description_en': "Memorisation of 20 Juz' of the Quran. Open to candidates aged 22 and below.",
        'description_ar': "حفظ ٢٠ جزءاً من القرآن الكريم. مفتوح للمتسابقين الذين لا تتجاوز أعمارهم ٢٢ سنة.",
        'order': 2,
    },
    {
        'name_en': "15 Juz'",
        'name_ar': "١٥ جزءاً",
        'juz_count': 15,
        'max_age': 20,
        'prize_sar': 10000,
        'description_en': "Memorisation of 15 Juz' of the Quran. Open to candidates aged 20 and below.",
        'description_ar': "حفظ ١٥ جزءاً من القرآن الكريم. مفتوح للمتسابقين الذين لا تتجاوز أعمارهم ٢٠ سنة.",
        'order': 3,
    },
    {
        'name_en': "5 Juz'",
        'name_ar': "٥ أجزاء",
        'juz_count': 5,
        'max_age': 16,
        'prize_sar': 5000,
        'description_en': "Memorisation of 5 Juz' of the Quran. Open to candidates aged 16 and below.",
        'description_ar': "حفظ ٥ أجزاء من القرآن الكريم. مفتوح للمتسابقين الذين لا تتجاوز أعمارهم ١٦ سنة.",
        'order': 4,
    },
]


class Command(BaseCommand):
    help = 'Seed the database with initial competition categories, settings, and a superuser.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-username', default='admin',
            help='Username for the superuser (default: admin)'
        )
        parser.add_argument(
            '--admin-password', default='Admin@1234',
            help='Password for the superuser (default: Admin@1234)'
        )
        parser.add_argument(
            '--admin-email', default='admin@example.com',
            help='Email for the superuser'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Seeding categories...'))
        for data in CATEGORIES:
            cat, created = Category.objects.update_or_create(
                juz_count=data['juz_count'],
                defaults=data,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f"  {action}: {cat.name_en}")

        self.stdout.write(self.style.MIGRATE_HEADING('Seeding competition settings...'))
        settings = CompetitionSettings.load()
        settings.about_en = (
            "The Quran Competition 2026 is a prestigious annual event organised by the "
            "Religious Attaché of the Saudi Embassy in Kenya. Open to Muslim youth across "
            "Kenya, the competition celebrates Quran memorisation (Hifz) and exemplary "
            "recitation (Tajweed). Trusted partners include the Ministry of Foreign Affairs, "
            "SUPKEM, and Jamia Mosque Nairobi."
        )
        settings.about_ar = (
            "مسابقة القرآن الكريم ٢٠٢٦ حدث سنوي مرموق تنظمه الملحقية الدينية للسفارة "
            "السعودية في كينيا. مفتوحة للشباب المسلم في جميع أنحاء كينيا، وتحتفي المسابقة "
            "بحفظ القرآن الكريم وحسن تلاوته. من الشركاء الموثوقين: وزارة الخارجية، "
            "والمجلس الأعلى للمسلمين (سوبكيم)، ومسجد جامعة نيروبي."
        )
        settings.save()
        self.stdout.write("  Competition settings saved.")

        self.stdout.write(self.style.MIGRATE_HEADING('Creating superuser...'))
        username = options['admin_username']
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                password=options['admin_password'],
                email=options['admin_email'],
            )
            self.stdout.write(f"  Superuser '{username}' created.")
        else:
            self.stdout.write(f"  Superuser '{username}' already exists, skipping.")

        self.stdout.write(self.style.SUCCESS('\n✓ Database seeding complete!'))
