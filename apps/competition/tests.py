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
        self.assertFalse(res.data['is_duplicate'])
        self.assertFalse(res.data['fields']['phone'])

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


from django.contrib.auth.models import User
from django.core import mail

class RegistrationUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.admin_user)
        self.category = Category.objects.create(
            name_en="15 Juz'",
            name_ar="١٥ جزء",
            juz_count=15,
            max_age=18,
            prize_sar=15000,
            order=2
        )
        self.registration = Registration.objects.create(
            full_name="Fatima Zahra",
            date_of_birth=date(2010, 3, 15),
            nationality="Kenyan",
            national_id_number="BC987654",
            county="Mombasa",
            nominating_institution="Madrasa Noor",
            phone_number="0722000000",
            email="fatima@example.com",
            category=self.category,
            status=Registration.Status.PENDING
        )

    def test_update_registrant_name_and_institution_sends_email(self):
        url = f"/api/v1/registrations/{self.registration.id}/"
        payload = {
            "full_name": "Fatima Zahra Hassan",
            "nominating_institution": "Darul Uloom Mombasa",
            "reviewer_notes": "Updated surname and school as requested by administration."
        }
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['full_name'], "Fatima Zahra Hassan")
        self.assertEqual(res.data['nominating_institution'], "Darul Uloom Mombasa")
        self.assertTrue(res.data.get('email_sent'))

        # Verify email was dispatched
        self.assertGreaterEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[-1]
        self.assertIn("Fatima Zahra Hassan", sent_email.subject)
        self.assertIn("fatima@example.com", sent_email.to)
        self.assertIn("Darul Uloom Mombasa", sent_email.body)


