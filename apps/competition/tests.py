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
        # Email duplicate check was removed so institutions/parents can submit multiple candidates with one email
        res = self.client.get('/api/v1/registrations/check_duplicate/', {'email': 'AHMAD@example.com'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['is_duplicate'])
        self.assertFalse(res.data['fields']['email'])

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


class SoftDeleteAndRegretEmailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin2',
            email='admin2@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.admin_user)
        self.category = Category.objects.create(
            name_en="30 Juz'",
            name_ar="٣٠ جزء",
            juz_count=30,
            max_age=25,
            prize_sar=30000,
            order=1
        )
        self.reg1 = Registration.objects.create(
            full_name="Omar Al-Khattab",
            date_of_birth=date(2005, 1, 1),
            nationality="Kenyan",
            national_id_number="OMAR101",
            county="Nairobi",
            nominating_institution="Markaz Bilal",
            phone_number="0711111111",
            email="omar@example.com",
            category=self.category,
            status=Registration.Status.PENDING
        )
        self.reg2 = Registration.objects.create(
            full_name="Zayd ibn Thabit",
            date_of_birth=date(2006, 2, 2),
            nationality="Kenyan",
            national_id_number="ZAYD102",
            county="Garissa",
            nominating_institution="Al-Azhar Garissa",
            phone_number="0722222222",
            email="zayd@example.com",
            category=self.category,
            status=Registration.Status.PENDING
        )

    def test_soft_delete_moves_candidate_to_deleted_archive(self):
        url = f"/api/v1/registrations/{self.reg1.id}/"
        res = self.client.delete(url, {'reason': 'Disqualified due to institution error'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['permanent'])

        self.reg1.refresh_from_db()
        self.assertTrue(self.reg1.is_deleted)
        self.assertIsNotNone(self.reg1.deleted_at)
        self.assertEqual(self.reg1.deletion_reason, 'Disqualified due to institution error')

        # Active list should not contain reg1
        list_res = self.client.get('/api/v1/registrations/')
        self.assertEqual(list_res.status_code, 200)
        active_ids = [r['id'] for r in list_res.data]
        self.assertNotIn(self.reg1.id, active_ids)
        self.assertIn(self.reg2.id, active_ids)

        # Deleted list should contain reg1
        deleted_res = self.client.get('/api/v1/registrations/?is_deleted=true')
        self.assertEqual(deleted_res.status_code, 200)
        deleted_ids = [r['id'] for r in deleted_res.data]
        self.assertIn(self.reg1.id, deleted_ids)
        self.assertNotIn(self.reg2.id, deleted_ids)

    def test_restore_candidate_back_to_active(self):
        # Soft delete first
        self.reg1.is_deleted = True
        self.reg1.save()

        res = self.client.post(f"/api/v1/registrations/{self.reg1.id}/restore/")
        self.assertEqual(res.status_code, 200)

        self.reg1.refresh_from_db()
        self.assertFalse(self.reg1.is_deleted)
        self.assertIsNone(self.reg1.deleted_at)

    def test_permanent_delete_purges_record(self):
        url = f"/api/v1/registrations/{self.reg1.id}/?permanent=true"
        res = self.client.delete(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['permanent'])

        self.assertFalse(Registration.objects.filter(id=self.reg1.id).exists())

    def test_send_single_regret_email(self):
        self.reg1.is_deleted = True
        self.reg1.save()

        mail.outbox.clear()
        res = self.client.post(f"/api/v1/registrations/{self.reg1.id}/send_regret_email/", {
            'reason': 'Quota reached for Nairobi county in this category.'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_sent'])

        self.reg1.refresh_from_db()
        self.assertTrue(self.reg1.regret_email_sent)
        self.assertIsNotNone(self.reg1.regret_email_sent_at)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("omar@example.com", sent.to)
        self.assertIn("Quota reached for Nairobi county", sent.body)

    def test_bulk_send_regret_emails(self):
        self.reg1.is_deleted = True
        self.reg2.is_deleted = True
        self.reg1.save()
        self.reg2.save()

        mail.outbox.clear()
        res = self.client.post("/api/v1/registrations/bulk_send_regret_email/", {
            'ids': [self.reg1.id, self.reg2.id],
            'reason': 'Thank you for participating.'
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['sent_count'], 2)

        self.reg1.refresh_from_db()
        self.reg2.refresh_from_db()
        self.assertTrue(self.reg1.regret_email_sent)
        self.assertTrue(self.reg2.regret_email_sent)
        self.assertEqual(len(mail.outbox), 2)

    def test_update_archival_reason_via_action(self):
        self.reg1.is_deleted = True
        self.reg1.deletion_reason = "Initial reason"
        self.reg1.save()

        res = self.client.post(
            f"/api/v1/registrations/{self.reg1.id}/update_archival_reason/",
            {"reason": "Updated committee reason: Age criteria exceeded."},
            format='json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['deletion_reason'], "Updated committee reason: Age criteria exceeded.")

        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.deletion_reason, "Updated committee reason: Age criteria exceeded.")

    def test_update_archival_reason_via_patch(self):
        self.reg1.is_deleted = True
        self.reg1.deletion_reason = "Initial reason"
        self.reg1.save()

        mail.outbox.clear()
        res = self.client.patch(
            f"/api/v1/registrations/{self.reg1.id}/",
            {"deletion_reason": "Corrected note: Incomplete documents."},
            format='json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['deletion_reason'], "Corrected note: Incomplete documents.")

        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.deletion_reason, "Corrected note: Incomplete documents.")
        # Updating archival reason should NOT trigger candidate update email
        self.assertEqual(len(mail.outbox), 0)



