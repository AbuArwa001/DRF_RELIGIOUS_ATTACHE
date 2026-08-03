from django.test import TestCase
from rest_framework.test import APIClient
from apps.competition.models import Category, Registration
from datetime import date


class DuplicateRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(
            name_en="5 Juz'",
            name_ar="٥ أجزاء",
            juz_count=5,
            max_age=10,
            prize_sar=5000,
            order=1
        )
        self.existing_reg = Registration.objects.create(
            full_name="Ahmad Ali",
            date_of_birth=date(2018, 5, 10),
            nationality="kenyan",
            national_id_number="ID123456",
            county="Nairobi",
            nominating_institution="Madrasa Al-Huda",
            phone_number="0712345678",
            email="ahmad@example.com",
            category=self.category,
            status=Registration.Status.PENDING
        )

    def test_duplicate_national_id_check_endpoint(self):
        res = self.client.get('/api/v1/registrations/check_duplicate/', {'national_id': 'id123456'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_duplicate'])
        self.assertTrue(res.data['fields']['national_id'])

    def test_duplicate_phone_check_endpoint(self):
        res = self.client.get('/api/v1/registrations/check_duplicate/', {'phone': '+254 712-345-678'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_duplicate'])
        self.assertTrue(res.data['fields']['phone'])

    def test_duplicate_email_check_endpoint(self):
        res = self.client.get('/api/v1/registrations/check_duplicate/', {'email': 'AHMAD@example.com'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_duplicate'])
        self.assertTrue(res.data['fields']['email'])

    def test_non_duplicate_check_endpoint(self):
        res = self.client.get('/api/v1/registrations/check_duplicate/', {'national_id': 'UNIQUE999', 'phone': '0799999999'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['is_duplicate'])

    def test_rejected_registration_allows_re_registration(self):
        self.existing_reg.status = Registration.Status.REJECTED
        self.existing_reg.save()

        res = self.client.get('/api/v1/registrations/check_duplicate/', {'national_id': 'ID123456'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['is_duplicate'])

