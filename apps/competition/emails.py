"""
Email helper functions for competition registration status updates.
"""
import logging
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)


COUNTY_CENTERS = {
    'nairobi': {'center': 'Jamia Mosque', 'region': 'Nairobi County', 'venue_full': 'Jamia Mosque (Main Hall), Banda Street, Nairobi Central'},
    'mombasa': {'center': 'Masjid Bilal', 'region': 'Coast Region', 'venue_full': 'Masjid Bilal, Mombasa Island'},
    'garissa': {'center': 'Masjid Andalus', 'region': 'North Eastern Region', 'venue_full': 'Masjid Andalus, Garissa Town'},
    'nakuru': {'center': 'Jamia Mosque', 'region': 'Rift Valley Region', 'venue_full': 'Jamia Mosque, Nakuru City'},
    'isiolo': {'center': 'Jamia Mosque', 'region': 'Upper Eastern Region', 'venue_full': 'Jamia Mosque, Isiolo Town'},
    'mandera': {'center': 'Jamia Mosque', 'region': 'North Eastern Region', 'venue_full': 'Jamia Mosque, Mandera Town'},
    'wajir': {'center': 'Masjidul-Falah', 'region': 'North Eastern Region', 'venue_full': 'Masjidul-Falah, Wajir Town'},
}


def get_county_center_info(county_name):
    normalized = (county_name or "").strip()
    key = normalized.lower()
    if key and key in COUNTY_CENTERS:
        return {
            'name': normalized,
            'center': COUNTY_CENTERS[key]['center'],
            'region': COUNTY_CENTERS[key]['region'],
            'venue_full': COUNTY_CENTERS[key]['venue_full'],
        }
    return {
        'name': normalized or "Designated Examination County",
        'center': 'Jamia Mosque',
        'region': 'Central Examination Center',
        'venue_full': 'Jamia Mosque, Banda Street, Nairobi (or your designated county center)',
    }


def send_status_update_email(registration):
    """
    Sends an absolute premium royal Islamic admission email notification to the participant
    when their registration status is Approved, containing assigned county preliminary venue,
    full schedule, candidate roll reference, checklist, and roadmap.
    Sends an official dignified regret notice if Unsuccessful.
    """
    if not registration or not registration.email:
        logger.info(f"Skipping status email for registration ID {getattr(registration, 'id', None)}: No email address.")
        return False

    status = registration.status
    if status not in ['approved', 'rejected']:
        return False

    from datetime import date
    current_year = date.today().year

    is_approved = (status == 'approved')
    status_text = "Approved" if is_approved else "Unsuccessful"
    category_name = registration.category.name_en if registration.category else "Holy Quran Memorization"
    reviewer_notes = (registration.reviewer_notes or "").strip()
    ref_display = f"REF-{registration.id:05d}" if getattr(registration, 'id', None) else "REF-OFFICIAL"
    county_display = registration.county or "Not Specified"
    institution_display = registration.nominating_institution or "Private Candidate / Self-Nominated"
    assigned_center = get_county_center_info(registration.county)

    # Dynamic competition settings dates (Official Competition Calendar)
    prelims_date_display = "5th – 7th September 2026"
    finals_date_display = "11th – 13th October 2026"
    try:
        from .models import CompetitionSettings
        cfg = CompetitionSettings.load()
        if cfg.preliminaries_date:
            p_start = cfg.preliminaries_date.strftime("%d %B %Y")
            if cfg.preliminaries_end_date and cfg.preliminaries_end_date != cfg.preliminaries_date:
                prelims_date_display = f"{cfg.preliminaries_date.strftime('%-d')}th – {cfg.preliminaries_end_date.strftime('%-d')}th {cfg.preliminaries_end_date.strftime('%B %Y')}"
            else:
                prelims_date_display = p_start
        if cfg.finals_date:
            f_start = cfg.finals_date.strftime("%d %B %Y")
            if cfg.finals_end_date and cfg.finals_end_date != cfg.finals_date:
                finals_date_display = f"{cfg.finals_date.strftime('%-d')}th – {cfg.finals_end_date.strftime('%-d')}th {cfg.finals_end_date.strftime('%B %Y')}"
            else:
                finals_date_display = f_start
    except Exception as e:
        logger.debug(f"Using default competition dates: {e}")

    if is_approved:
        # ═══════════════════════════════════════════════════════════════════════
        # ABSOLUTE PREMIUM ROYAL APPROVAL EMAIL TEMPLATE
        # ═══════════════════════════════════════════════════════════════════════
        html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Official Admission Notice – Annual Quran Memorization Competition {current_year}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@700&family=Inter:wght@400;500;600;700;800&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #F1F5F9;
      color: #1E293B;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }}
    table {{ border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ border: 0; outline: none; text-decoration: none; }}
    .wrapper {{ width: 100%; background-color: #F1F5F9; padding: 36px 12px; }}
    .container {{ max-width: 640px; margin: 0 auto; background-color: #ffffff; border-radius: 18px; overflow: hidden; box-shadow: 0 12px 40px rgba(14, 122, 74, 0.12), 0 4px 12px rgba(0,0,0,0.05); }}
    
    .royal-header {{
      background: linear-gradient(135deg, #043823 0%, #0E7A4A 55%, #166534 100%);
      padding: 44px 32px 36px;
      text-align: center;
      position: relative;
    }}
    .basmalah {{
      font-family: 'Amiri', 'Traditional Arabic', serif;
      font-size: 24px;
      font-weight: 700;
      color: #F0D97A;
      letter-spacing: 0.05em;
      margin-bottom: 14px;
      text-shadow: 0 2px 4px rgba(0,0,0,0.35);
    }}
    .state-emblem {{
      display: inline-block;
      padding: 4px 14px;
      background: rgba(191, 168, 79, 0.18);
      border: 1px solid #BFA84F;
      color: #F0D97A;
      border-radius: 9999px;
      font-size: 10.5px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }}
    .header-h1 {{
      color: #ffffff;
      font-size: 24px;
      font-weight: 800;
      line-height: 1.3;
      margin-bottom: 6px;
      letter-spacing: -0.01em;
    }}
    .header-sub {{
      color: rgba(255, 255, 255, 0.88);
      font-size: 13.5px;
      font-weight: 500;
    }}
    .gold-bar {{
      height: 5px;
      background: linear-gradient(90deg, #996515 0%, #D4AF37 25%, #F3E5AB 50%, #D4AF37 75%, #996515 100%);
    }}

    .body-content {{ padding: 36px 32px; }}

    .pass-card {{
      background: linear-gradient(145deg, #FBFDFB 0%, #F0FDF4 100%);
      border: 1.5px solid #86EFAC;
      border-radius: 14px;
      padding: 22px 24px;
      margin-bottom: 28px;
      box-shadow: 0 4px 16px rgba(14, 122, 74, 0.06);
    }}
    .pass-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px dashed #86EFAC;
      padding-bottom: 14px;
      margin-bottom: 16px;
    }}
    .pass-roll-label {{
      font-size: 10.5px;
      font-weight: 800;
      color: #166534;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .pass-roll-number {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 22px;
      font-weight: 800;
      color: #0E7A4A;
      letter-spacing: 0.08em;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #0E7A4A;
      color: #ffffff;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 11.5px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      box-shadow: 0 2px 8px rgba(14, 122, 74, 0.25);
    }}

    .hadith-quote {{
      background-color: #FEFCE8;
      border: 1px solid #FEF08A;
      border-left: 4px solid #CA8A04;
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 26px;
      text-align: center;
    }}
    .hadith-arabic {{
      font-family: 'Amiri', 'Traditional Arabic', serif;
      font-size: 18px;
      font-weight: 700;
      color: #854D0E;
      margin-bottom: 4px;
      direction: rtl;
    }}
    .hadith-trans {{
      font-size: 12.5px;
      color: #713F12;
      font-style: italic;
    }}

    .section-title {{
      font-size: 12.5px;
      font-weight: 800;
      color: #0E7A4A;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .venue-card {{
      background: #FFFFFF;
      border: 2px solid #BFA84F;
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 28px;
      box-shadow: 0 4px 20px rgba(191, 168, 79, 0.15);
    }}
    .venue-tag {{
      background: #BFA84F;
      color: #ffffff;
      display: inline-block;
      font-size: 10px;
      font-weight: 800;
      padding: 3px 10px;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
    }}
    .venue-name {{
      font-size: 20px;
      font-weight: 800;
      color: #043823;
      margin-bottom: 6px;
    }}
    .venue-address {{
      font-size: 13.5px;
      color: #475569;
      margin-bottom: 16px;
    }}

    .dossier-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      background: #F8FAFC;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 28px;
    }}
    .dossier-table td {{
      padding: 12px 18px;
      border-bottom: 1px solid #E2E8F0;
      font-size: 13px;
    }}
    .dossier-table tr:last-child td {{ border-bottom: none; }}
    .dossier-lbl {{ width: 38%; color: #64748B; font-weight: 600; }}
    .dossier-val {{ color: #0F172A; font-weight: 700; }}

    .counties-box {{
      background: #F8FAFC;
      border: 1px solid #CBD5E1;
      border-radius: 12px;
      padding: 18px 20px;
      margin-bottom: 28px;
    }}
    .counties-desc {{
      font-size: 12px;
      color: #64748B;
      margin-bottom: 12px;
      line-height: 1.5;
    }}

    .roadmap-list {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      padding: 16px 18px;
      margin-bottom: 28px;
    }}
    .roadmap-step {{
      display: flex;
      gap: 14px;
      margin-bottom: 14px;
      align-items: flex-start;
    }}
    .roadmap-step:last-child {{ margin-bottom: 0; }}
    .step-badge {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: #0E7A4A;
      color: #ffffff;
      font-size: 11.5px;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }}
    .step-title {{
      font-size: 13px;
      font-weight: 700;
      color: #0F172A;
      margin-bottom: 2px;
    }}
    .step-desc {{
      font-size: 12px;
      color: #64748B;
      line-height: 1.5;
    }}

    .checklist-card {{
      background: #F1F5F9;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 28px;
    }}
    .check-item {{
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 10px;
      font-size: 12.5px;
      color: #334155;
      line-height: 1.5;
    }}
    .check-item:last-child {{ margin-bottom: 0; }}
    .check-icon {{
      color: #0E7A4A;
      font-weight: 800;
      font-size: 14px;
      line-height: 1;
      margin-top: 1px;
    }}

    .reviewer-note-box {{
      background: #EFF6FF;
      border: 1px solid #BFDBFE;
      border-left: 5px solid #2563EB;
      border-radius: 8px;
      padding: 16px 18px;
      margin-bottom: 28px;
    }}

    .closing-dua {{
      text-align: center;
      padding: 20px 0 10px;
      border-top: 1px solid #E2E8F0;
    }}
    .dua-arabic {{
      font-family: 'Amiri', 'Traditional Arabic', serif;
      font-size: 20px;
      font-weight: 700;
      color: #0E7A4A;
      margin-bottom: 6px;
    }}
    .dua-en {{
      font-size: 13px;
      color: #64748B;
      font-style: italic;
      margin-bottom: 16px;
    }}
    .attestation-block {{ text-align: center; margin-top: 8px; }}
    .attest-team {{ font-size: 14px; font-weight: 800; color: #043823; }}
    .attest-org {{ font-size: 12.5px; color: #475569; }}

    .footer {{
      background: #0F172A;
      color: #94A3B8;
      padding: 28px 32px;
      text-align: center;
      font-size: 11.5px;
      line-height: 1.7;
    }}
    .footer-title {{ color: #F8FAFC; font-weight: 700; font-size: 12.5px; margin-bottom: 4px; }}
    .footer-links a {{ color: #D4AF37; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      
      <!-- ═══ ROYAL HEADER ═══════════════════════════════════════════════════ -->
      <div class="royal-header">
        <div class="basmalah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>
        <div class="state-emblem">Kingdom of Saudi Arabia · Ministry of Islamic Affairs</div>
        <h1 class="header-h1">Annual Holy Quran Memorization Competition</h1>
        <p class="header-sub">Religious Attaché Office · Embassy of Saudi Arabia, Nairobi · {current_year}</p>
      </div>
      <div class="gold-bar"></div>

      <!-- ═══ BODY CONTENT ══════════════════════════════════════════════════ -->
      <div class="body-content">

        <!-- Admission Pass Card -->
        <div class="pass-card">
          <div class="pass-top">
            <div>
              <div class="pass-roll-label">Official Candidate Roll No.</div>
              <div class="pass-roll-number">{ref_display}</div>
            </div>
            <div>
              <span class="status-badge">
                <span style="font-size: 10px;">●</span> ADMITTED & CONFIRMED
              </span>
            </div>
          </div>
          <div style="font-size: 16px; font-weight: 800; color: #043823; margin-bottom: 4px;">
            {registration.full_name}
          </div>
          <div style="font-size: 13px; color: #4B5563;">
            Category: <strong style="color: #0E7A4A;">{category_name}</strong> · County: <strong>{county_display}</strong>
          </div>
        </div>

        <!-- Opening Congratulations -->
        <p style="font-size: 15.5px; font-weight: 700; color: #0F172A; margin-bottom: 10px;">
          Assalamu Alaikum wa Rahmatullahi wa Barakatuh,
        </p>
        <p style="font-size: 14px; color: #334155; line-height: 1.7; margin-bottom: 20px;">
          Alhamdulillah wa Kafaa — We are honored to officially inform you that following the review of your submitted credentials by the Higher Organizing Committee, your application for the <strong>Annual Holy Quran Memorization Competition {current_year}</strong> has been <strong style="color: #0E7A4A;">Approved</strong>.
        </p>
        <p style="font-size: 14px; color: #334155; line-height: 1.7; margin-bottom: 24px;">
          You have been formally accredited as a participating candidate for the <strong>{category_name}</strong> memorization level. Please find your assigned County Preliminary Examination Center and reporting instructions detailed below.
        </p>

        <!-- Prophetic Hadith Inspiration -->
        <div class="hadith-quote">
          <div class="hadith-arabic">«خَيْرُكُمْ مَنْ تَعَلَّمَ الْقُرْآنَ وَعَلَّمَهُ»</div>
          <div class="hadith-trans">“The best among you are those who learn the Quran and teach it.” — Sahih al-Bukhari</div>
        </div>

        <!-- ═══ ASSIGNED PRELIMINARY CENTER (HIGHLIGHT) ════════════════════ -->
        <div class="section-title">
          <span>📍</span> Assigned County Preliminary Center
        </div>
        <div class="venue-card">
          <div class="venue-tag">Official Examination Venue</div>
          <div class="venue-name">{assigned_center['center']}</div>
          <div class="venue-address">
            🏛️ {assigned_center['venue_full']}
          </div>

          <table width="100%" style="margin-top: 14px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px;">
            <tr>
              <td style="padding: 12px 14px; border-right: 1px solid #E2E8F0; width: 50%;">
                <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Examination Dates</div>
                <div style="font-size: 13.5px; font-weight: 800; color: #0E7A4A; margin-top: 2px;">{prelims_date_display}</div>
              </td>
              <td style="padding: 12px 14px; width: 50%;">
                <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Candidate Call Time</div>
                <div style="font-size: 13.5px; font-weight: 800; color: #0F172A; margin-top: 2px;">7:30 AM EAT (Roll-Call)</div>
              </td>
            </tr>
            <tr>
              <td style="padding: 12px 14px; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0;">
                <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Jurisdiction / County</div>
                <div style="font-size: 13px; font-weight: 700; color: #0F172A; margin-top: 2px;">{assigned_center['region']} ({county_display})</div>
              </td>
              <td style="padding: 12px 14px; border-top: 1px solid #E2E8F0;">
                <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Examination Format</div>
                <div style="font-size: 13px; font-weight: 700; color: #0F172A; margin-top: 2px;">Oral Recitation Before Jury</div>
              </td>
            </tr>
          </table>
        </div>

        <!-- ═══ CANDIDATE DOSSIER SUMMARY ═════════════════════════════════ -->
        <div class="section-title">
          <span>📋</span> Official Candidate Dossier
        </div>
        <table class="dossier-table">
          <tr>
            <td class="dossier-lbl">Candidate Full Name</td>
            <td class="dossier-val">{registration.full_name}</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Candidate Reference</td>
            <td class="dossier-val" style="font-family: monospace; color: #0E7A4A;">{ref_display}</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Competition Category</td>
            <td class="dossier-val" style="color: #0E7A4A;">{category_name}</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Nominating Institution</td>
            <td class="dossier-val">{institution_display}</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Registered County</td>
            <td class="dossier-val">{county_display}</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Assigned Center</td>
            <td class="dossier-val">{assigned_center['center']} ({assigned_center['region']})</td>
          </tr>
          <tr>
            <td class="dossier-lbl">Official Status</td>
            <td class="dossier-val" style="color: #0E7A4A;">✓ Approved & Qualified for Preliminaries</td>
          </tr>
        </table>

        <!-- ═══ 7 COUNTIES PRELIMINARY DIRECTORY ═══════════════════════════ -->
        <div class="section-title">
          <span>🏢</span> County Preliminaries Centers Directory
        </div>
        <div class="counties-box">
          <p class="counties-desc">
            The preliminary rounds will be conducted simultaneously across the designated regional examination hubs. Your examination takes place at the venue assigned above according to your registered county:
          </p>
          <table width="100%" style="border-collapse: separate; border-spacing: 6px;">
            <tr>
              <td style="width: 50%; padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'nairobi' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Nairobi:</strong> Jamia Mosque
              </td>
              <td style="width: 50%; padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'mombasa' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Mombasa:</strong> Masjid Bilal
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'garissa' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Garissa:</strong> Masjid Andalus
              </td>
              <td style="padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'nakuru' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Nakuru:</strong> Jamia Mosque
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'isiolo' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Isiolo:</strong> Jamia Mosque
              </td>
              <td style="padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'mandera' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Mandera:</strong> Jamia Mosque
              </td>
            </tr>
            <tr>
              <td colspan="2" style="padding: 8px 12px; background: {'#DCFCE7; border: 1.5px solid #16A34A;' if 'wajir' in county_display.lower() else '#FFFFFF; border: 1px solid #E2E8F0;'} border-radius: 8px; font-size: 12px;">
                <strong style="color: #0F172A;">Wajir:</strong> Masjidul-Falah
              </td>
            </tr>
          </table>
        </div>

        <!-- ═══ COMPETITION ROADMAP ════════════════════════════════════════ -->
        <div class="section-title">
          <span>🗓️</span> Competition Milestone Roadmap
        </div>
        <div class="roadmap-list">
          <div class="roadmap-step">
            <div class="step-badge">1</div>
            <div>
              <div class="step-title">Stage 1: Preliminary Examinations (County Hubs)</div>
              <div class="step-desc"><strong>{prelims_date_display}</strong> — Candidates recite before the accredited jury at their assigned county preliminary mosque center.</div>
            </div>
          </div>
          <div class="roadmap-step">
            <div class="step-badge" style="background: #2563EB;">2</div>
            <div>
              <div class="step-title">Stage 2: Official Qualifiers & Finalists Announcement</div>
              <div class="step-desc"><strong>Late September 2026</strong> — Highest-scoring reciters across all categories and counties are officially published and invited to Nairobi.</div>
            </div>
          </div>
          <div class="roadmap-step">
            <div class="step-badge" style="background: #BFA84F; color: #000;">3</div>
            <div>
              <div class="step-title">Stage 3: Grand National Finals & Royal Awards Gala</div>
              <div class="step-desc"><strong>{finals_date_display} (Nairobi, Kenya)</strong> — The grand stage, closing ceremony, and distribution of official royal awards & certificates.</div>
            </div>
          </div>
        </div>

        <!-- ═══ CANDIDATE INSTRUCTIONS & CHECKLIST ═════════════════════════ -->
        <div class="section-title">
          <span>📌</span> Mandatory Candidate Instructions
        </div>
        <div class="checklist-card">
          <div class="check-item">
            <span class="check-icon">✓</span>
            <div><strong>Punctuality:</strong> Arrive at the examination hall by <strong>7:30 AM EAT</strong> sharp for roll call and seating verification.</div>
          </div>
          <div class="check-item">
            <span class="check-icon">✓</span>
            <div><strong>Judging Criteria:</strong> Reciters are evaluated on memorization accuracy (Hifdh), Ahkam of Tajweed, Makharij al-Huroof, Husn al-Sawt, and confidence.</div>
          </div>
        </div>

        {f'''
        <!-- Reviewer Notes -->
        <div class="reviewer-note-box">
          <div style="font-size: 11.5px; font-weight: 800; color: #1E40AF; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;">
            📌 Committee Note / Specific Instruction:
          </div>
          <div style="font-size: 13.5px; color: #1E3A8A; line-height: 1.6; white-space: pre-wrap;">
            {reviewer_notes}
          </div>
        </div>
        ''' if reviewer_notes else ''}

        <!-- ═══ CLOSING DUA & ATTESTATION ═══════════════════════════════════ -->
        <div class="closing-dua">
          <div class="dua-arabic">وفقكم الله ونفع بكم القرآن الكريم وجعلكم من أهله وخاصته</div>
          <div class="dua-en">May Allah (SWT) crown your efforts with success, bless your memorization, and grant you victory in this world and the Hereafter.</div>
          <div class="attestation-block">
            <div class="attest-team">The Higher Organizing Committee</div>
            <div class="attest-org">Religious Attaché Office · Embassy of the Kingdom of Saudi Arabia, Nairobi</div>
          </div>
        </div>

      </div>

      <!-- ═══ FOOTER ═════════════════════════════════════════════════════════ -->
      <div class="footer">
        <div class="footer-title">Office of the Religious Attaché</div>
        <div>Embassy of the Kingdom of Saudi Arabia · Nairobi, Kenya</div>
        <div style="margin: 8px 0;" class="footer-links">
          Official Portal: <a href="https://religiousattacheksa.co.ke" target="_blank">religiousattacheksa.co.ke</a> · Contact: <a href="mailto:admin@religiousattacheksa.co.ke">admin@religiousattacheksa.co.ke</a>
        </div>
        <div style="color: #64748B; font-size: 10.5px; margin-top: 12px;">
          © {current_year} Religious Attaché, Royal Embassy of Saudi Arabia, Nairobi. All rights reserved.
        </div>
      </div>

    </div>
  </div>
</body>
</html>
        """.strip()
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

        html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Application Status Update</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #F1F5F9; margin: 0; padding: 24px 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <div style="background: linear-gradient(135deg, #043823 0%, #0E7A4A 100%); padding: 36px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0 0 8px 0;">Quran Competition {current_year}</h1>
      <p style="color: rgba(255,255,255,0.85); font-size: 14px; margin: 0;">Religious Attaché · Embassy of Saudi Arabia, Nairobi</p>
    </div>
    <div style="height: 4px; background: linear-gradient(90deg, #996515, #D4AF37, #996515);"></div>
    <div style="padding: 32px;">
      <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum wa Rahmatullahi wa Barakatuh,</p>
      <p style="font-size: 14.5px; font-weight: 600; color: #1E293B; margin-bottom: 14px;">Dear {registration.full_name},</p>
      <p style="font-size: 14px; color: #475569; line-height: 1.7; margin-bottom: 18px;">
        Thank you for applying to the <strong>Annual Holy Quran Memorization Competition {current_year}</strong>. After careful review, we regret to inform you that your application was <strong style="color: #DC2626;">Unsuccessful</strong> for this edition.
      </p>
      {notes_block}
      <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;">📋 Application Summary</p>
      <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; overflow: hidden; margin-bottom: 24px;">
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E2E8F0;">
          <span style="font-size: 12.5px; font-weight: 600; color: #64748B; width: 140px; flex-shrink: 0;">Full Name</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{registration.full_name}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E2E8F0;">
          <span style="font-size: 12.5px; font-weight: 600; color: #64748B; width: 140px; flex-shrink: 0;">Reference No.</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{ref_display}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E2E8F0;">
          <span style="font-size: 12.5px; font-weight: 600; color: #64748B; width: 140px; flex-shrink: 0;">Category</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{category_name}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E2E8F0;">
          <span style="font-size: 12.5px; font-weight: 600; color: #64748B; width: 140px; flex-shrink: 0;">County</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{county_display}</span>
        </div>
        <div style="display: flex; padding: 12px 16px;">
          <span style="font-size: 12.5px; font-weight: 600; color: #64748B; width: 140px; flex-shrink: 0;">Status</span>
          <span style="font-size: 13px; font-weight: 700; color: #DC2626;">Unsuccessful</span>
        </div>
      </div>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.7; margin-bottom: 16px;">
        We appreciate your noble interest in the competition and encourage you to continue your journey with the Holy Quran.
      </p>
      <p style="font-size: 13.5px; color: #0E7A4A; font-weight: 700; line-height: 1.6;">
        جزاكم الله خيراً وبارك الله فيكم ونفع بكم الإسلام والمسلمين<br />
        <span style="color: #64748B; font-weight: 500; font-size: 12px;">May Allah reward you abundantly and bless your continuous path with the Holy Quran.</span>
      </p>
    </div>
    <div style="background: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 20px 32px; text-align: center; font-size: 12px; color: #64748B;">
      Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
    </div>
  </div>
</body>
</html>
        """.strip()

    subject = f"Official Admission & Preliminary Notice: {registration.full_name} ({ref_display}) | Quran Competition {current_year}" if is_approved else f"Application Status Notification: {registration.full_name} ({ref_display}) | Quran Competition {current_year}"
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
        logger.info(f"Status email sent to {registration.email} ({status_text})")
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


def send_profile_update_email(registration, changed_fields=None, reason=None, old_data=None, extra_recipients=None):
    """
    Sends an email notification to the participant / nominating institution when their
    registration profile details (name, passport photo, ID document, institution, contact, etc.)
    are updated by the administration.
    """
    if not registration:
        return False

    recipients = []
    if registration.email and registration.email.strip():
        recipients.append(registration.email.strip())

    if extra_recipients:
        for r in extra_recipients:
            if r and r.strip() and r.strip() not in recipients:
                recipients.append(r.strip())

    if not recipients:
        logger.info(f"Skipping profile update email for registration ID {getattr(registration, 'id', None)}: No recipient email.")
        return False

    category_name = registration.category.name_en if registration.category else "Unassigned"
    reason_clean = (reason or "").strip()
    ref_str = f"REF-{registration.id:05d}" if registration.id else "—"

    # Format changed fields list
    changes_html = ""
    if changed_fields:
        rows = []
        if isinstance(changed_fields, dict):
            for field_key, val in changed_fields.items():
                if isinstance(val, dict):
                    label = val.get('label', field_key.replace('_', ' ').title())
                    old_v = val.get('old', '—')
                    new_v = val.get('new', '—')
                    rows.append(f"""
                    <tr style="border-bottom: 1px solid #E5E7EB;">
                      <td style="padding: 10px 14px; font-weight: 700; color: #374151; font-size: 13px; width: 140px;">{label}</td>
                      <td style="padding: 10px 14px; color: #6B7280; font-size: 12.5px; text-decoration: line-through;">{old_v}</td>
                      <td style="padding: 10px 14px; color: #0E7A4A; font-weight: 700; font-size: 13px;">{new_v}</td>
                    </tr>
                    """)
                else:
                    label = field_key.replace('_', ' ').title()
                    rows.append(f"""
                    <tr style="border-bottom: 1px solid #E5E7EB;">
                      <td style="padding: 10px 14px; font-weight: 700; color: #374151; font-size: 13px;">{label}</td>
                      <td colspan="2" style="padding: 10px 14px; color: #0E7A4A; font-weight: 700; font-size: 13px;">{val}</td>
                    </tr>
                    """)
        elif isinstance(changed_fields, list):
            for item in changed_fields:
                rows.append(f"""
                <tr style="border-bottom: 1px solid #E5E7EB;">
                  <td colspan="3" style="padding: 10px 14px; color: #0E7A4A; font-weight: 700; font-size: 13px;">✓ {item}</td>
                </tr>
                """)

        if rows:
            changes_html = f"""
            <div style="margin-bottom: 24px;">
              <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;">
                🔄 Modified Details
              </p>
              <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; border-radius: 10px; overflow: hidden;">
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                  <thead>
                    <tr style="background: #EDF2F7; border-bottom: 1px solid #CBD5E1;">
                      <th style="padding: 10px 14px; font-size: 11.5px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.05em;">Field</th>
                      <th style="padding: 10px 14px; font-size: 11.5px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.05em;">Previous</th>
                      <th style="padding: 10px 14px; font-size: 11.5px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.05em;">Updated Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows)}
                  </tbody>
                </table>
              </div>
            </div>
            """

    reason_block = ""
    if reason_clean:
        reason_block = f"""
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 5px solid #2563EB; padding: 18px 20px; margin-bottom: 24px; border-radius: 8px;">
          <p style="font-size: 13px; font-weight: 800; color: #1E40AF; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em;">
            📌 Committee Note / Reason:
          </p>
          <p style="font-size: 14.5px; color: #1E3A8A; margin: 0; line-height: 1.65; white-space: pre-wrap; font-weight: 500;">{reason_clean}</p>
        </div>
        """

    institution_info = f"<strong>{registration.nominating_institution}</strong>" if registration.nominating_institution else "your institution"

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Registration Details Updated</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #F3F4F6; margin: 0; padding: 24px 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <div style="background: linear-gradient(135deg, #0E7A4A 0%, #166534 100%); padding: 36px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0 0 8px 0;">Quran Competition 2026</h1>
      <p style="color: rgba(255,255,255,0.8); font-size: 14px; margin: 0;">Religious Attaché · Embassy of Saudi Arabia, Nairobi</p>
    </div>
    <div style="height: 4px; background: linear-gradient(90deg, #BFA84F, #D4C068, #BFA84F);"></div>
    <div style="padding: 32px;">
      <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum,</p>
      <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 20px;">
        Please be informed that the candidate registration details for <strong>{registration.full_name}</strong> ({institution_info}) for the <strong>Annual Quran Memorization Competition 2026</strong> have been updated by the organizing committee.
      </p>

      {changes_html}
      {reason_block}

      <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;">📋 Updated Application Summary</p>
      <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; overflow: hidden; margin-bottom: 24px;">
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Full Name</span>
          <span style="font-size: 13px; font-weight: 700; color: #111827;">{registration.full_name}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Reference No.</span>
          <span style="font-size: 13px; font-weight: 700; color: #111827;">{ref_str}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Institution</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{registration.nominating_institution or '—'}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Category</span>
          <span style="font-size: 13px; font-weight: 800; color: #0E7A4A;">{category_name}</span>
        </div>
        {f'''
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">County</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{registration.county}</span>
        </div>
        ''' if registration.county else ''}
        <div style="display: flex; padding: 12px 16px;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Status</span>
          <span style="font-size: 13px; font-weight: 700; color: #111827; text-transform: capitalize;">{registration.status}</span>
        </div>
      </div>

      <p style="font-size: 13.5px; color: #4B5563; line-height: 1.7; margin-bottom: 12px;">
        If you have any questions regarding these updates, please contact the competition organizing committee quoting your reference number.
      </p>
      <p style="font-size: 13px; color: #6B7280; line-height: 1.6;">
        Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
      </p>
    </div>
    <div style="background: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 20px 32px; text-align: center; font-size: 12px; color: #6B7280;">
      Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
    </div>
  </div>
</body>
</html>
    """.strip()

    subject = f"Registration Details Updated – {registration.full_name} | Quran Competition 2026"
    plain_message = strip_tags(html_message)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@religiousattacheksa.co.ke')

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Profile update email sent to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send profile update email to {recipients}: {e}")
        return False


def send_regret_email(registration, reason=None, custom_notes=None):
    """
    Sends an official regret email notification to a candidate whose registration
    was removed / archived from the active competition roster.
    """
    if not registration or not registration.email or not registration.email.strip():
        logger.info(f"Skipping regret email for registration ID {getattr(registration, 'id', None)}: No email address.")
        return False

    recipient = registration.email.strip()
    category_name = registration.category.name_en if registration.category else "Unassigned"
    ref_str = f"REF-{registration.id:05d}" if registration.id else "—"
    institution_str = registration.nominating_institution or "—"
    county_str = registration.county or "—"

    # Combine custom_notes or deletion_reason or reason
    notes_text = (custom_notes or reason or registration.deletion_reason or registration.reviewer_notes or "").strip()

    notes_block = ""
    if notes_text:
        notes_block = f"""
        <div style="background-color: #FEF2F2; border: 1px solid #FECACA; border-left: 5px solid #DC2626; padding: 18px 20px; margin-bottom: 24px; border-radius: 8px;">
          <p style="font-size: 13px; font-weight: 800; color: #991B1B; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
            📌 Committee Note / Reason:
          </p>
          <p style="font-size: 14.5px; color: #7F1D1D; margin: 0; line-height: 1.65; white-space: pre-wrap; font-weight: 500;">{notes_text}</p>
        </div>
        """

    html_message = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Application Status Notification | Quran Competition 2026</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #F3F4F6; margin: 0; padding: 24px 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #0E7A4A 0%, #166534 100%); padding: 36px 32px; text-align: center;">
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0 0 8px 0;">Quran Competition 2026</h1>
      <p style="color: rgba(255,255,255,0.85); font-size: 14px; margin: 0;">Religious Attaché · Embassy of Saudi Arabia, Nairobi</p>
    </div>
    <div style="height: 4px; background: linear-gradient(90deg, #BFA84F, #D4C068, #BFA84F);"></div>

    <!-- Body -->
    <div style="padding: 32px;">
      <p style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 12px;">Assalamu Alaikum wa Rahmatullahi wa Barakatuh,</p>
      <p style="font-size: 15px; font-weight: 600; color: #1F2937; margin-bottom: 16px;">Dear {registration.full_name},</p>
      
      <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 18px;">
        Thank you for submitting your application for the <strong>Annual Quran Memorization Competition 2026</strong> organized by the Religious Attaché of the Embassy of the Kingdom of Saudi Arabia in Nairobi.
      </p>

      <p style="font-size: 14.5px; color: #4B5563; line-height: 1.7; margin-bottom: 22px;">
        The registration and screening phase has concluded. Due to high candidate volume and strict quota regulations across categories and counties, we regret to inform you that your application was <strong style="color: #DC2626;">not selected</strong> to proceed to the examination rounds for this edition.
      </p>

      {notes_block}

      <!-- Application Details -->
      <p style="font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px;">📋 Application Reference</p>
      <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; overflow: hidden; margin-bottom: 24px;">
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Full Name</span>
          <span style="font-size: 13px; font-weight: 700; color: #111827;">{registration.full_name}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Reference No.</span>
          <span style="font-size: 13px; font-weight: 700; color: #111827;">{ref_str}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Category</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{category_name}</span>
        </div>
        <div style="display: flex; padding: 12px 16px; border-bottom: 1px solid #E5E7EB;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">Institution</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{institution_str}</span>
        </div>
        <div style="display: flex; padding: 12px 16px;">
          <span style="font-size: 12.5px; font-weight: 600; color: #6B7280; width: 140px; flex-shrink: 0;">County</span>
          <span style="font-size: 13px; font-weight: 600; color: #111827;">{county_str}</span>
        </div>
      </div>

      <p style="font-size: 14px; color: #4B5563; line-height: 1.7; margin-bottom: 16px;">
        We deeply appreciate your noble effort and dedication to memorizing the Book of Allah. We wholeheartedly encourage you to continue your Quranic studies and look forward to your participation in future competitions.
      </p>

      <p style="font-size: 13.5px; color: #0E7A4A; font-weight: 700; line-height: 1.6; margin-bottom: 0;">
        جزاكم الله خيراً وبارك الله فيكم ونفع بكم الإسلام والمسلمين<br />
        <span style="color: #6B7280; font-weight: 500; font-size: 12.5px;">May Allah reward you abundantly and bless your continuous journey with the Holy Quran.</span>
      </p>
    </div>

    <!-- Footer -->
    <div style="background: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 20px 32px; text-align: center; font-size: 12px; color: #6B7280;">
      Religious Attaché — Embassy of the Kingdom of Saudi Arabia, Nairobi
    </div>
  </div>
</body>
</html>
    """.strip()

    subject = f"Competition Update: Application Status | Quran Competition 2026"
    plain_message = strip_tags(html_message)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@religiousattacheksa.co.ke')

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Regret email successfully sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send regret email to {recipient}: {e}")
        return False



