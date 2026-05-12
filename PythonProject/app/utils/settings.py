from app.extensions import db
from app.models import AppSetting


def get_setting(key, default=None):
    setting = AppSetting.query.filter_by(key=key).first()
    return setting.value if setting else default


def set_setting(key, value):
    setting = AppSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()


def parse_alert_days(value):
    if not value:
        return [30, 15, 7, 1]
    parts = [p.strip() for p in value.split(',')]
    days = []
    for part in parts:
        if part.isdigit():
            days.append(int(part))
    return days or [30, 15, 7, 1]


def get_alert_days(default_days):
    stored = get_setting('alert_days')
    if stored is None:
        return default_days
    return parse_alert_days(stored)


def get_alert_interval_hours(default_hours):
    stored = get_setting('alert_interval_hours')
    if stored is None:
        return default_hours
    try:
        value = int(stored)
    except ValueError:
        return default_hours
    return value if value > 0 else default_hours


def set_alert_days(days):
    text = ','.join(str(d) for d in days)
    set_setting('alert_days', text)


def set_alert_interval_hours(hours):
    set_setting('alert_interval_hours', str(hours))

