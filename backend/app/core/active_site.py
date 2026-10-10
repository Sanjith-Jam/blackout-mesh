"""The site profile this process runs (#26), validated once at import, before any state is built.

SITE_PROFILE selects the profile file and RFID_ENROLLMENT the card map. A profile change is a restart
(a new run with a new config hash), never a live partial mutation.
"""
from __future__ import annotations

import os

from app.core.config import build_catalog, load_rfid_enrollment, load_site_profile

SITES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sites")
SITE_PROFILE_PATH = os.environ.get("SITE_PROFILE", os.path.join(SITES_DIR, "default_campus.json"))
RFID_ENROLLMENT_PATH = os.environ.get("RFID_ENROLLMENT", os.path.join(SITES_DIR, "rfid_enrollment.json"))

site_profile = load_site_profile(SITE_PROFILE_PATH)
CATALOG = build_catalog(site_profile)
rfid_enrollment = load_rfid_enrollment(RFID_ENROLLMENT_PATH)
