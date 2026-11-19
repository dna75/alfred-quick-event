#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Alfred Script Filter: one line of text -> calendar event preview (+ JSON for create.sh).

Understands English and Dutch. Everything is parsed locally, no network.
"""
import sys, os, re, json, subprocess, datetime as dt

# ---- vocabulary (English + Dutch) ------------------------------------------------------------
WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
    "ma": 0, "maandag": 0, "di": 1, "dinsdag": 1, "wo": 2, "woensdag": 2, "do": 3, "donderdag": 3,
    "vr": 4, "vrijdag": 4, "za": 5, "zaterdag": 5, "zo": 6, "zondag": 6,
}
MONTHS = {
    "jan": 1, "january": 1, "januari": 1, "feb": 2, "february": 2, "februari": 2,
    "mar": 3, "march": 3, "mrt": 3, "maart": 3, "apr": 4, "april": 4, "may": 5, "mei": 5,
    "jun": 6, "june": 6, "juni": 6, "jul": 7, "july": 7, "juli": 7, "aug": 8, "august": 8, "augustus": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "okt": 10, "october": 10, "oktober": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}
TODAY, TOMORROW, DAY_AFTER = ("today", "vandaag"), ("tomorrow", "morgen"), ("overmorgen",)
AT_WORDS, UNTIL_WORDS = ("at", "om"), ("until", "tot")

# ---- texts shown in Alfred ---------------------------------------------------------------------
LANG = os.environ.get("language", "en")
TEXTS = {
    "en": {"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
           "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           "all_day": "all day", "example_title": "New event", "example": "E.g.: dentist tomorrow 2pm +1h @Office #work",
           "need_title": "Type a title for the event…", "no_cal_title": "Calendar not found",
           "no_cal": "Calendar '#%s' does not exist. Choose from: %s", "cmd": "Create in %s and open Calendar"},
    "nl": {"days": ["ma", "di", "wo", "do", "vr", "za", "zo"],
           "months": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
           "all_day": "hele dag", "example_title": "Nieuwe afspraak", "example": "Bijv.: tandarts morgen 14:00 +1u @Leeuwarden #werk",
           "need_title": "Typ een titel voor de afspraak…", "no_cal_title": "Agenda niet gevonden",
           "no_cal": "Agenda '#%s' bestaat niet. Kies uit: %s", "cmd": "Aanmaken in %s en Agenda openen"},
}
TXT = TEXTS.get(LANG, TEXTS["en"])


def writable_calendars():
    """Names of writable calendars, cached for an hour."""
    cache = os.path.join(os.environ.get("alfred_workflow_cache", "/tmp"), "calendars.json")
    try:
        if os.path.exists(cache) and (dt.datetime.now().timestamp() - os.path.getmtime(cache)) < 3600:
            return json.load(open(cache))
    except Exception:
        pass
    try:
        out = subprocess.run(["osascript", "-e", 'tell application "Calendar" to get name of every calendar whose writable is true'],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        names = [x.strip() for x in out.split(", ") if x.strip()]
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump(names, open(cache, "w"))
        return names
    except Exception:
        return []


def next_weekday(now, weekday):
    return now.date() + dt.timedelta(days=(weekday - now.weekday()) % 7 or 7)


def parse(query, now):
    """Split the query into title, date, time, end, duration, calendar, place and all-day flag."""
    words = query.split()
    rest = []
    date = clock = end = duration = calendar = place = None
    all_day = False
    i = 0
    while i < len(words):
        word = words[i]
        low = word.lower().strip(",")
        nxt = words[i + 1].lower().strip(",") if i + 1 < len(words) else ""
        if low.startswith("#") and len(low) > 1:
            calendar = low[1:]; i += 1; continue
        if low.startswith("@") and len(low) > 1:
            place = word[1:].replace("_", " "); i += 1; continue
        if low in TODAY:
            date = now.date(); i += 1; continue
        if low in TOMORROW:
            date = now.date() + dt.timedelta(days=1); i += 1; continue
        if low in DAY_AFTER:
            date = now.date() + dt.timedelta(days=2); i += 1; continue
        if low in ("next", "volgende", "komende") and nxt in WEEKDAYS:
            date = next_weekday(now, WEEKDAYS[nxt]); i += 2; continue
        if low in WEEKDAYS and date is None:
            date = next_weekday(now, WEEKDAYS[low]); i += 1; continue
        m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?", low)      # 25-11, 25/11/2026
        if m and date is None:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else now.year
            year += 2000 if year < 100 else 0
            try:
                date = dt.date(year, month, day)
                if not m.group(3) and date < now.date():
                    date = dt.date(year + 1, month, day)
                i += 1; continue
            except ValueError:
                pass
        if re.fullmatch(r"\d{1,2}", low) and nxt in MONTHS and date is None:   # 5 dec
            try:
                date = dt.date(now.year, MONTHS[nxt], int(low))
                if date < now.date():
                    date = dt.date(now.year + 1, MONTHS[nxt], int(low))
                i += 2; continue
            except ValueError:
                pass
        m = re.fullmatch(r"(?:at|om|until|tot)?(\d{1,2})(?:[:.u](\d{2})|u)", low)   # 14:00, 14.30, 14u30, at14:00
        if m and int(m.group(1)) < 24 and int(m.group(2) or 0) < 60:
            t = (int(m.group(1)), int(m.group(2) or 0))
            if clock is None: clock = t
            else: end = t
            i += 1; continue
        m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)", low)                    # 2pm, 9:30am
        if m:
            t = (int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0), int(m.group(2) or 0))
            if clock is None: clock = t
            else: end = t
            i += 1; continue
        if low in AT_WORDS + UNTIL_WORDS and nxt:
            m = re.fullmatch(r"(\d{1,2})(?:[:.u](\d{2})|u)?", nxt)
            if m and int(m.group(1)) < 24:
                t = (int(m.group(1)), int(m.group(2) or 0))
                if low in UNTIL_WORDS: end = t
                elif clock is None: clock = t
                i += 2; continue
        m = re.fullmatch(r"\+(\d+(?:[,.]\d+)?)(u|uur|h|hr|hour|hours|m|min|mins|minutes|minuten)?", low)  # +1h, +30m, +1.5h
        if m:
            amount = float(m.group(1).replace(",", "."))
            hours = (m.group(2) or "h") in ("u", "uur", "h", "hr", "hour", "hours")
            duration = int(round(amount * 60 if hours else amount)); i += 1; continue
        if low in ("allday", "all-day", "heledag", "hele-dag"):
            all_day = True; i += 1; continue
        if low in ("all", "hele") and nxt in ("day", "dag"):
            all_day = True; i += 2; continue
        rest.append(word); i += 1
    title = " ".join(rest).strip()
    if title:
        title = title[0].upper() + title[1:]
    return dict(title=title, date=date, clock=clock, end=end, duration=duration, calendar=calendar, place=place, all_day=all_day)


def build(query):
    """Turn the parsed query into a concrete event. Returns (event, error_message)."""
    now = dt.datetime.now()
    r = parse(query, now)
    default_cal = os.environ.get("default_calendar", "") or ""
    default_minutes = int(float(os.environ.get("default_duration", "60") or 60))
    names = writable_calendars()
    calendar = default_cal if (default_cal in names) else (names[0] if names else default_cal)
    if r["calendar"]:
        found = [c for c in names if c.lower().startswith(r["calendar"])] or [c for c in names if r["calendar"] in c.lower()]
        if not found:
            return None, TXT["no_cal"] % (r["calendar"], ", ".join(names))
        calendar = found[0]
    date = r["date"] or now.date()
    all_day = r["all_day"] or (r["clock"] is None and r["date"] is not None)
    if r["clock"] is None and r["date"] is None:           # nothing given: next full hour today
        start = (now + dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        all_day = False
    elif all_day:
        start = dt.datetime.combine(date, dt.time(0, 0))
    else:
        h, mi = r["clock"]
        start = dt.datetime.combine(date, dt.time(h % 24, mi))
        if r["date"] is None and start < now:
            start += dt.timedelta(days=1)
    if all_day:
        finish = start + dt.timedelta(days=1)
    elif r["end"]:
        finish = dt.datetime.combine(start.date(), dt.time(*r["end"]))
        if finish <= start:
            finish += dt.timedelta(days=1)
    else:
        finish = start + dt.timedelta(minutes=r["duration"] or default_minutes)
    return dict(title=r["title"], start=start, end=finish, all_day=all_day, calendar=calendar,
                place=r["place"], explicit=bool(r["calendar"])), None


def describe(e):
    s = e["start"]
    day = "%s %d %s" % (TXT["days"][s.weekday()], s.day, TXT["months"][s.month - 1])
    when = day + (" · " + TXT["all_day"] if e["all_day"] else " · %s–%s" % (s.strftime("%H:%M"), e["end"].strftime("%H:%M")))
    return when + " · " + e["calendar"] + ((" · " + e["place"]) if e["place"] else "")


def output(items):
    print(json.dumps({"items": items}, ensure_ascii=False))


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    if not query.strip():
        return output([{"title": TXT["example_title"], "subtitle": TXT["example"], "valid": False, "icon": {"path": "icon.png"}}])
    e, error = build(query)
    if error:
        return output([{"title": TXT["no_cal_title"], "subtitle": error, "valid": False}])
    if not e["title"]:
        return output([{"title": TXT["need_title"], "subtitle": describe(e), "valid": False, "icon": {"path": "icon.png"}}])
    hidden = [x.strip().lower() for x in (os.environ.get("hide_calendars", "") or "").split(",") if x.strip()]
    if e["explicit"]:
        choices = [e["calendar"]]
    else:                                                    # default calendar first, then the others
        choices = [e["calendar"]] + [c for c in writable_calendars() if c != e["calendar"] and c.lower() not in hidden]
    items = []
    for name in choices:
        payload = dict(title=e["title"], start=e["start"].strftime("%Y-%m-%d %H:%M"), end=e["end"].strftime("%Y-%m-%d %H:%M"),
                       all_day=e["all_day"], calendar=name, place=e["place"] or "")
        items.append({"uid": "calendar:" + name, "title": e["title"] + "  →  " + name, "subtitle": describe(dict(e, calendar=name)),
                      "arg": json.dumps(payload, ensure_ascii=False), "icon": {"path": "icon.png"},
                      "mods": {"cmd": {"subtitle": TXT["cmd"] % name, "arg": json.dumps(dict(payload, open=True), ensure_ascii=False)}}})
    output(items)


if __name__ == "__main__":
    main()
