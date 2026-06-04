# src/MVP/views/ui_utils.py

TRANSLATIONS = {
    "title": {"he": "לוח מבחנים שנתי", "en": "Annual Exam Schedule"},
    "monthly_title": {"he": "תצוגה חודשית", "en": "Monthly View"},
    "exclude_btn": {"he": "החרג תאריך", "en": "Exclude Date"},
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
    "close": {"he": "סגור", "en": "Close"},
    
    # --- Input View & Dates Modal Translations ---
    "courses": {"he": "קורסים", "en": "Courses"},
    "dates": {"he": "תאריכים", "en": "Dates"},
    "programs_title": {"he": "בחירת תוכניות לימוד (עד 5)", "en": "Select Programs (Max 5)"},
    "details_title": {"he": "פרטים", "en": "Details"},
    "no_selection": {"he": "בחר תוכנית מהרשימה כדי לראות את הקורסים שלה כאן.", "en": "Select a program from the list to view its courses here."},
    "btn_run": {"he": "הפעל", "en": "START"},
    "max_programs_err": {"he": "לא ניתן לבחור יותר מ-5 תוכניות לימוד במקביל.", "en": "Cannot select more than 5 programs at once."},
    "icon_upload": {"he": "📤", "en": "📤"},
    "icon_trash": {"he": "🗑️", "en": "🗑️"},
    "year": {"he": "שנה", "en": "Year"},

    # --- Dates File Load Chooser ---
    "dates_load_title": {"he": "טעינת קובץ תאריכים", "en": "Load Dates File"},
    "add_file": {"he": "הוסף קובץ", "en": "Add File"},
    "overwrite_file": {"he": "דרוס קובץ קיים", "en": "Overwrite Existing"},
    "cancel": {"he": "ביטול", "en": "Cancel"},
    
    # --- Date Edit Modal ---
    "edit_dates": {"he": "עריכת תאריכים", "en": "Edit Dates"},
    "add_excluded_date": {"he": "הוספת תאריך מוחרג:", "en": "Add Excluded Date:"},
    "save": {"he": "שמור", "en": "Save"},
    "date_format": {"he": "dd/mm/yyyy", "en": "dd/mm/yyyy"},
    "no_dates_loaded": {"he": "אנא העלה קובץ תאריכים תחילה.", "en": "Please load a dates file first."},
    "semester": {"he": "סמסטר", "en": "Semester"},
    "moed": {"he": "מועד", "en": "Moed"},
    
    # --- Dynamic Value Translations ---
    "semester_FALL": {"he": "סתיו", "en": "Fall"}, 
    "semester_SPRI": {"he": "אביב", "en": "Spring"}, 
    "semester_SUMM": {"he": "קיץ", "en": "Summer"},
    "eval_EXAM": {"he": "מבחן", "en": "Exam"},
    "eval_PROJECT": {"he": "פרויקט", "en": "Project"},
    "eval_ASSIGNMENT": {"he": "מטלה", "en": "Assignment"},
    "eval_OTHER": {"he": "אחר", "en": "Other"}
}

def format_text(key: str, lang: str) -> str:
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    return f"\u200F{text}\u200F" if lang == "he" else text