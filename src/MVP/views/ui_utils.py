# src/MVP/views/ui_utils.py

TRANSLATIONS = {
    "title": {"he": "לוח מבחנים שנתי", "en": "Annual Exam Schedule"},
    "monthly_title": {"he": "תצוגה חודשית", "en": "Monthly View"},
    "exclude_btn": {"he": "החרג תאריך", "en": "Exclude Date"},
    "export_btn": {"he": "ייצוא", "en": "Export"},
    "start_date": {"he": "התחלה", "en": "Start"},
    "end_date": {"he": "סיום", "en": "End"},
    "update_range": {"he": "עדכן", "en": "Update"},
    "filter_btn": {"he": "סינון לפי", "en": "Filter By"},
    "schedule_lbl": {"he": "מערכת", "en": "Schedule"},
    "out_of_lbl": {"he": "מתוך", "en": "out of"},
    "load_more": {"he": "טען עוד", "en": "Load More"},
    "empty_state": {"he": "יש לטעון נתונים", "en": "Please load data"},
    "computing": {"he": "מחשב שיבוצים...", "en": "Computing schedules..."},
    "no_results": {"he": "לא נמצאו מערכות מתאימות", "en": "No matching schedules found"},
    
    # --- Loading-indicator & robot translations ---
    "toast_courses_loaded": {"he": "קובץ קורסים נטען בהצלחה", "en": "Courses file loaded successfully"},
    "toast_dates_loaded": {"he": "קובץ תאריכים עודכן בהצלחה", "en": "Dates file updated successfully"},
    "toast_data_cleared": {"he": "הנתונים נמחקו", "en": "Data cleared"},
    "toast_courses_cleared": {"he": "קובץ הקורסים נמחק", "en": "Courses file cleared"},
    "err_both_missing": {"he": "אנא טען קובצי קורסים ותאריכים", "en": "Please load courses and dates files"},
    "err_courses_missing": {"he": "אנא טען קובץ קורסים", "en": "Please load a courses file"},
    "err_dates_missing": {"he": "אנא טען קובץ תאריכים", "en": "Please load a dates file"},
    "err_courses_format": {"he": "קובץ הקורסים שהועלה אינו תקין", "en": "The uploaded courses file is invalid"},
    "err_dates_format": {"he": "קובץ התאריכים שהועלה אינו תקין", "en": "The uploaded dates file is invalid"},

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
    "no_selection": {"he": "בחר תוכנית מהרשימה כדי לראות את הקורסים שלה כאן", "en": "Select a program from the list to view its courses here"},
    "btn_run": {"he": "הפעל", "en": "START"},
    "max_programs_err": {"he": "לא ניתן לבחור יותר מ-5 תוכניות לימוד במקביל", "en": "Cannot select more than 5 programs at once"},
    "icon_upload": {"he": "העלה", "en": "Upload"},
    "icon_trash": {"he": "מחק", "en": "Delete"},
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
    "no_dates_loaded": {"he": "אנא העלה קובץ תאריכים תחילה", "en": "Please load a dates file first"},
    "semester": {"he": "סמסטר", "en": "Semester"},
    "moed": {"he": "מועד", "en": "Moed"},
    "no_periods_defined": {"he": "לא הוגדרו תקופות בחינה", "en": "No exam periods defined"},

    # --- Moed values (translate the raw data value Aleph/Bet/Gimel for both languages) ---
    "moed_Aleph": {"he": "א", "en": "A"},
    "moed_Bet": {"he": "ב", "en": "B"},
    "moed_Gimel": {"he": "ג", "en": "C"},
    
    # --- Dynamic Value Translations ---
    "semester_FALL": {"he": "סתיו", "en": "Fall"}, 
    "semester_SPRI": {"he": "אביב", "en": "Spring"}, 
    "semester_SUMM": {"he": "קיץ", "en": "Summer"},
    "eval_EXAM": {"he": "מבחן", "en": "Exam"},
    "eval_PROJECT": {"he": "פרויקט", "en": "Project"},
    "eval_ASSIGNMENT": {"he": "מטלה", "en": "Assignment"},
    "eval_OTHER": {"he": "אחר", "en": "Other"},

    # --- Ranking bar: sort + windowing controls (PLAN-411..415) ---
    "sort_by": {"he": "מיון לפי:", "en": "Sort by:"},
    "sort_then": {"he": "ואז:", "en": "then:"},
    "sort_dir_desc": {"he": "יורד", "en": "Desc"},
    "sort_dir_asc": {"he": "עולה", "en": "Asc"},
    "sort_none": {"he": "— ללא —", "en": "— None —"},
    "refresh_btn": {"he": "רענן", "en": "Refresh"},
    "end_of_results": {"he": "סוף התוצאות", "en": "End of results"},
    "metrics_panel_title": {"he": "מדדי המערכת הנוכחית", "en": "Current schedule metrics"},
    "sort_selector_tooltip": {"he": "בחירת מדדי מיון וסדר עדיפות", "en": "Choose sort metrics and priority order"},
    "sort_selector_title": {"he": "בחירת סדר מיון", "en": "Sort Criteria Priority"},
    "sort_selector_hint": {"he": "סמן את המדדים שישתתפו במיון. סדר השורות קובע עדיפות: השורה הראשונה היא המדד הראשי. ניתן לגרור שורות או להשתמש בחצים.", "en": "Select the metrics used for sorting. Row order sets priority: the first row is the primary criterion. Drag rows or use the arrow buttons."},
    "sort_selector_empty_error": {"he": "יש לבחור לפחות מדד מיון אחד", "en": "Select at least one sort metric"},

    # Sort-metric labels (dropdown) for the five section-3 metrics
    "metric_avg_gap_all": {"he": "ממוצע ימים בין בחינות", "en": "Avg days between exams"},
    "metric_min_gap_mandatory": {"he": "מרווח מינימלי (חובה)", "en": "Min gap (mandatory)"},
    "metric_elective_conflicts": {"he": "התנגשויות בחירה", "en": "Elective conflicts"},
    "metric_mandatory_span": {"he": "מרווח ראשונה-אחרונה (חובה)", "en": "First–last span (mandatory)"},
    "metric_max_exams_per_day": {"he": "מקסימום בחינות ביום", "en": "Max exams per day"},

    # Compact metric labels for the live readout
    "metric_short_avg_gap_all": {"he": "ממוצע", "en": "Avg"},
    "metric_short_min_gap_mandatory": {"he": "מינ' חובה", "en": "Min(mand)"},
    "metric_short_elective_conflicts": {"he": "התנגשויות", "en": "Conflicts"},
    "metric_short_mandatory_span": {"he": "מרווח חובה", "en": "Span(mand)"},
    "metric_short_max_exams_per_day": {"he": "מקס'/יום", "en": "Max/day"},

    # --- Info / help screen for the ranking features ---
    "info_btn_tooltip": {"he": "הסבר על המיון והמדדים", "en": "About sorting & metrics"},
    "info_title": {"he": "דירוג ומדדים — הסבר", "en": "Ranking & Metrics — Help"},
    "info_sort_title": {"he": "מיון", "en": "Sorting"},
    "info_sort_desc": {
        "he": "המיון משנה רק את סדר ההצגה של הלוחות — הוא אף פעם לא מוסיף או מסיר לוחות. בוחרים מדד ראשי, מדד משני לשובר־שוויון, וכיוון (יורד/עולה). השינוי מיידי ואינו מריץ את המנוע מחדש.",
        "en": "Sorting only changes the display order of the schedules — it never adds or removes any. Pick a primary metric, an optional secondary tie-breaker, and a direction (descending/ascending). It applies instantly and does not re-run the engine.",
    },
    "info_metrics_title": {"he": "חמשת המדדים", "en": "The five metrics"},
    "info_metric_avg_gap_all": {
        "he": "ממוצע מספר הימים בין כל זוג בחינות (חובה או בחירה) באותה תוכנית ושנה. ערך גבוה = הבחינות מפוזרות יותר.",
        "en": "Average number of days between every pair of exams (mandatory or elective) in the same program and year. Higher = exams are more spread out.",
    },
    "info_metric_min_gap_mandatory": {
        "he": "המרווח הקטן ביותר (בימים) בין שתי בחינות חובה באותה תוכנית ושנה. ערך גבוה = אין שתי בחינות חובה צמודות.",
        "en": "The smallest gap (in days) between two mandatory exams in the same program and year. Higher = no two mandatory exams are crammed together.",
    },
    "info_metric_elective_conflicts": {
        "he": "כמה זוגות קורסי בחירה באותה תוכנית נופלים באותו יום. ערך נמוך = פחות חפיפות בקורסי בחירה.",
        "en": "How many pairs of elective courses in the same program fall on the same day. Lower = fewer elective clashes.",
    },
    "info_metric_mandatory_span": {
        "he": "מספר הימים בין בחינת החובה הראשונה לאחרונה באותה תוכנית ושנה.",
        "en": "The number of days between the first and last mandatory exam in the same program and year.",
    },
    "info_metric_max_exams_per_day": {
        "he": "מספר הבחינות המקסימלי המשובצות באותו יום בלוח.",
        "en": "The maximum number of exams scheduled on any single day in the schedule.",
    },
    "info_refresh_title": {"he": "רענן מול Sync", "en": "Refresh vs. Sync"},
    "info_refresh_desc": {
        "he": "רענן: מושך לתצוגה לוחות חדשים שהמנוע ייצר וממיין אותם מחדש — בלי להריץ את המנוע מחדש. Sync: מריץ את המנוע מאפס (למשל אחרי שינוי תוכניות או תאריכים).",
        "en": "Refresh: pulls in newly generated schedules and re-ranks them — without re-running the engine. Sync: re-runs the engine from scratch (e.g. after changing programs or dates).",
    },

    # --- Pruning constraints settings modal (PLAN-418) ---
    "constraints_button": {"he": "אילוצים", "en": "Constraints"},
    "constraints_tooltip": {"he": "הגדרות אילוצי שיבוץ", "en": "Scheduling constraints settings"},
    "constraints_title": {"he": "הגדרות אילוצי שיבוץ", "en": "Scheduling Constraints"},
    "constraints_header_name": {"he": "אילוץ", "en": "Constraint"},
    "constraints_header_enabled": {"he": "פעיל", "en": "Enabled"},
    "constraints_header_k": {"he": " k ערך ", "en": "k value"},
    "constraint_min_days_mandatory": {"he": "מרווח מינימלי בין מבחני חובה באותה תוכנית ושנה", "en": "Minimum days between mandatory exams in the same program/year"},
    "constraint_min_days_any": {"he": "מרווח מינימלי בין כל שתי בחינות באותה תוכנית ושנה", "en": "Minimum days between any two exams in the same program/year"},
    "constraint_max_elective_conflicts": {"he": "מקסימום התנגשויות בין קורסי בחירה", "en": "Maximum elective-elective conflicts"},
    "constraint_span_mandatory": {"he": "טווח מקסימלי בין מבחן חובה ראשון לאחרון", "en": "Maximum span from first to last mandatory exam"},
    "constraint_max_exams_per_day": {"he": "מקסימום בחינות באותו יום", "en": "Maximum exams on the same day"},
    "constraints_invalid": {"he": "חייב להיות מספר שלם ולא שלילי k ערך ", "en": "k must be a non-negative whole number"},
    "constraints_locked": {"he": "לא ניתן לשמור אילוצים בזמן שהמנוע רץ", "en": "Constraints cannot be saved while the engine is running"},
    "constraints_saved": {"he": "האילוצים נשמרו בהצלחה", "en": "Constraints saved successfully"},
}

def format_text(key: str, lang: str) -> str:
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    return f"\u200F{text}\u200F" if lang == "he" else text