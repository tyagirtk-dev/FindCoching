"""
Central place to read/write admin-editable settings (SMTP, radius, commission, site config).
Falls back to sane defaults if a key hasn't been set yet.
"""
from app import db
from app.models.system_setting import SystemSetting

DEFAULTS = {
    "SITE_NAME": "LocalTutor",
    "SEARCH_RADIUS_KM": "5",
    "COMMISSION_PERCENT": "10",
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "",
    "SMTP_PASSWORD": "",
    "SMTP_SENDER_EMAIL": "",
    "SMTP_SENDER_NAME": "LocalTutor",
    "SMTP_USE_TLS": "True",
    "UPI_PAYEE_ID": "",
    "UPI_PAYEE_NAME": "",
}

_cache = {}


def get_setting(key, default=None):
    if key in _cache:
        return _cache[key]
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting is not None:
        _cache[key] = setting.value
        return setting.value
    return default if default is not None else DEFAULTS.get(key)


def set_setting(key, value):
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting is None:
        setting = SystemSetting(key=key, value=str(value))
        db.session.add(setting)
    else:
        setting.value = str(value)
    db.session.commit()
    _cache[key] = str(value)
    return setting


def get_settings_dict(keys):
    return {k: get_setting(k) for k in keys}


def seed_defaults():
    """Called once at startup / seed script to ensure every default key exists in DB."""
    for key, value in DEFAULTS.items():
        if SystemSetting.query.filter_by(key=key).first() is None:
            db.session.add(SystemSetting(key=key, value=value))
    db.session.commit()


def clear_cache():
    _cache.clear()


def get_search_radius_km():
    try:
        return float(get_setting("SEARCH_RADIUS_KM", "5"))
    except (TypeError, ValueError):
        return 5.0


def get_commission_percent():
    try:
        return float(get_setting("COMMISSION_PERCENT", "10"))
    except (TypeError, ValueError):
        return 10.0
