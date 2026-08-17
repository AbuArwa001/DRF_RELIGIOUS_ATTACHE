"""
Email helper functions for competition registration status updates.
"""
import logging
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)


def send_status_update_email(registration):
    """
    Sends an email notification to the participant when their registration status
    is updated to approved or rejected, attaching review notes if provided.
    """
    if not registration or not registration.email:
        logger.info(f"Skipping status email for registration ID {getattr(registration, 'id', None)}: No email address.")
        return False

    status = registration.status
    if status not in ['approved', 'rejected']:
        return False

    is_approved = (status == 'approved')
    status_text = "Approved" if is_approved else "Unsuccessful"
    status_color = "#059669" if is_approved else "#DC2626"
    category_name = registration.category.name_en if registration.category else ""
    reviewer_notes = (registration.reviewer_notes or "").strip()

    if is_approved:
        body_html_content = f"""
        <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum, {registration.full_name}</p>
        <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 24px;">
          Alhamdulillah — we are pleased to inform you that your application for the <strong>Annual Quran Memorization Competition 2026</strong> has been <strong style="color: #059669;">Approved</strong>.
        </p>
        <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 24px;">
          You are officially registered {'for the <strong>' + category_name + '</strong> category' if category_name else ''}. We will be reaching out to you soon with further details regarding examination dates and preliminaries.
        </p>
        """
    else:
        notes_block = ""
        if reviewer_notes:
            notes_block = f"""
            <div style="background-color: #FEF2F2; border: 1px solid #FECACA; border-left: 5px solid #DC2626; padding: 18px 20px; margin-bottom: 24px; border-radius: 8px;">
              <p style="font-size: 13px; font-weight: 800; color: #991B1B; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
                📌 Reviewer Note / Reason for Decision:
              </p>
              <p style="font-size: 14.5px; color: #7F1D1D; margin: 0; line-height: 1.65; white-space: pre-wrap; font-weight: 500;">{reviewer_notes}</p>
            </div>
            """

        body_html_content = f"""
        <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum, {registration.full_name}</p>
        <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 24px;">
          Thank you for applying to the <strong>Annual Quran Memorization Competition 2026</strong>. After careful review, we regret to inform you that your application was <strong style="color: #DC2626;">Unsuccessful</strong>.
        </p>
        {notes_block}
        <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 24px;">
          We appreciate your interest in the competition and encourage you to continue your journey with the Holy Quran. You are welcome to apply again in the future.
        </p>
        """

    review_note_row = ""
    if not is_approved and reviewer_notes:
        review_note_row = f"""
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Review Note</span>
          <span style="font-size: 13px; font-weight: 600; color: #991B1B;">{reviewer_notes}</span>
        </div>
        """

    category_row = f"""
    <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
      <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Category</span>
      <span style="font-size: 13px; font-weight: 600; color: #111827;">{category_name}</span>
    </div>
    """ if category_name else ""

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Application Status Update</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #F3F4F6; margin: 0; padding: 24px 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <div style="background: linear-gradient(135deg, #0E7A4A 0%, #166534 100%); padding: 36px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0 0 8px 0;">Quran Competition 2026</h1>
      <p style="color: rgba(255,255,255,0.8); font-size: 14px; margin: 0;">Religious Attaché · Embassy of Saudi Arabia, Nairobi</p>
    </div>
    <div style="height: 4px; background: linear-gradient(90deg, #BFA84F, #D4C068, #BFA84F);"></div>
    <div style="padding: 32px;">
      {body_html_content}
      <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;">📋 Application Summary</p>
      <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; overflow: hidden; margin-bottom: 24px;">
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Full Name</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{registration.full_name}</span>
        </div>
        {category_row}
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Status</span>
          <span style="font-size: 13px; font-weight: 600; color: {status_color};">{status_text}</span>
        </div>
        {review_note_row}
      </div>
    </div>
    <div style="background: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 20px 32px; text-align: center; font-size: 12px; color: #6B7280;">
      Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
    </div>
  </div>
</body>
</html>
    """.strip()

    subject = f"Application {status_text} | Quran Competition 2026"
    plain_message = strip_tags(html_message)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@religiousattacheksa.co.ke')

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[registration.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Status email sent to {registration.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {registration.email}: {e}")
        return False


def send_category_update_email(registration, old_category_name=None, new_category_name=None, reason=None):
    """
    Sends an email notification to the participant when their competition memorization
    category (Juz') is changed by the administration.
    """
    if not registration or not registration.email:
        logger.info(f"Skipping category update email for registration ID {getattr(registration, 'id', None)}: No email address.")
        return False

    old_cat = old_category_name or "Previous Category"
    new_cat = new_category_name or (registration.category.name_en if registration.category else "Updated Category")
    reason_clean = (reason or "").strip()

    reason_block = ""
    if reason_clean:
        reason_block = f"""
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 5px solid #2563EB; padding: 18px 20px; margin-bottom: 24px; border-radius: 8px;">
          <p style="font-size: 13px; font-weight: 800; color: #1E40AF; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
            📌 Committee Note / Reason:
          </p>
          <p style="font-size: 14.5px; color: #1E3A8A; margin: 0; line-height: 1.65; white-space: pre-wrap; font-weight: 500;">{reason_clean}</p>
        </div>
        """

    ref_str = f"REF-{registration.id:05d}" if registration.id else "—"

    body_html_content = f"""
    <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum, {registration.full_name}</p>
    <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 20px;">
      We would like to notify you that your assigned memorization category for the <strong>Annual Quran Memorization Competition 2026</strong> has been updated by the organizing committee.
    </p>

    <!-- Category Comparison Badge -->
    <div style="background: #F0FDF4; border: 1.5px solid #BBF7D0; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
      <div style="font-size: 12px; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
        Previous: <span style="text-decoration: line-through; color: #9CA3AF;">{old_cat}</span>
      </div>
      <div style="font-size: 22px; font-weight: 800; color: #0E7A4A;">
        ✨ New Category: {new_cat}
      </div>
    </div>

    {reason_block}

    <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;">📋 Updated Application Summary</p>
    <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; overflow: hidden; margin-bottom: 24px;">
      <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
        <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Full Name</span>
        <span style="font-size: 13px; font-weight: 600; color: #111827;">{registration.full_name}</span>
      </div>
      <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
        <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Reference No.</span>
        <span style="font-size: 13px; font-weight: 600; color: #111827;">{ref_str}</span>
      </div>
      <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
        <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Assigned Category</span>
        <span style="font-size: 13px; font-weight: 800; color: #0E7A4A;">{new_cat}</span>
      </div>
      <div style="display: flex; padding: 12px 16px;">
        <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Current Status</span>
        <span style="font-size: 13px; font-weight: 600; color: #111827; text-transform: capitalize;">{registration.status}</span>
      </div>
    </div>

    <p style="font-size: 13.5px; color: #4B5563; line-height: 1.7; margin-bottom: 12px;">
      Please make sure you are prepared according to the memorization requirements of your new category. If you have any inquiries, you may contact the organizing committee.
    </p>
    <p style="font-size: 13px; color: #6B7280; line-height: 1.6;">
      May Allah grant you success and reward your dedication to the Holy Quran.
    </p>
    """

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Memorization Category Update</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #F3F4F6; margin: 0; padding: 24px 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <div style="background: linear-gradient(135deg, #0E7A4A 0%, #166534 100%); padding: 36px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0 0 8px 0;">Quran Competition 2026</h1>
      <p style="color: rgba(255,255,255,0.8); font-size: 14px; margin: 0;">Religious Attaché · Embassy of Saudi Arabia, Nairobi</p>
    </div>
    <div style="height: 4px; background: linear-gradient(90deg, #BFA84F, #D4C068, #BFA84F);"></div>
    <div style="padding: 32px;">
      {body_html_content}
    </div>
    <div style="background: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 20px 32px; text-align: center; font-size: 12px; color: #6B7280;">
      Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
    </div>
  </div>
</body>
</html>
    """.strip()

    subject = f"Category Updated to {new_cat} | Quran Competition 2026"
    plain_message = strip_tags(html_message)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@religiousattacheksa.co.ke')

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[registration.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Category update email sent to {registration.email} ({new_cat})")
        return True
    except Exception as e:
        logger.error(f"Failed to send category update email to {registration.email}: {e}")
        return False

