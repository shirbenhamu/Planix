# src/MVP/views/ui_utils.py

TRANSLATIONS = {
    "title": {"he": "לוח מבחנים שנתי", "en": "Annual Exam Schedule"},
    "monthly_title": {"he": "תצוגה חודשית", "en": "Monthly View"},
    "exclude_btn": {"he": "תאריך החרג", "en": "Exclude Date"},
    "export_btn": {"he": "📥", "en": "📥"},
    "start_date": {"he": "התחלה", "en": "Start"},
    "end_date": {"he": "סיום", "en": "End"},
    "update_range": {"he": "עדכן", "en": "Update"},
    "filter_btn": {"he": "סינון לפי", "en": "Filter By"},
    "schedule_lbl": {"he": "מערכת", "en": "Schedule"},
    "out_of_lbl": {"he": "מתוך", "en": "out of"},
    "load_more": {"he": "טען עוד", "en": "Load More"},
    "empty_state": {"he": "יש לטעון נתונים.", "en": "Please load data."},
    "days": {"he": ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳"], "en": ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]},
    "months": {"he": ["ינו", "פבר", "מרץ", "אפר", "מאי", "יונ", "יול", "אוג", "ספט", "אוק", "נוב", "דצמ"], "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]},
    "months_full": {"he": ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"], "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]},
    "type_hova": {"he": "חובה", "en": "Mandatory"},
    "type_bhira": {"he": "בחירה", "en": "Elective"},
    "exam_details": {"he": "פרטי מבחן", "en": "Exam Details"},
    "course_id": {"he": "קוד קורס:", "en": "Course ID:"},
    "type": {"he": "סוג:", "en": "Type:"},
    "program": {"he": "תוכנית:", "en": "Prog:"},
    "close": {"he": "סגור", "en": "Close"}
}

def format_text(key: str, lang: str) -> str:
    """Helper to return direction-aware formatted strings."""
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    return f"\u200F{text}\u200F" if lang == "he" else text