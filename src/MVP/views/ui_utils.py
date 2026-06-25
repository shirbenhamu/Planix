# src/MVP/views/ui_utils.py

TRANSLATIONS = {
    "title": {"he": "לוח מבחנים שנתי", "en": "Annual Exam Schedule"},
    "monthly_title": {"he": "תצוגה חודשית", "en": "Monthly View"},
    "exclude_btn": {"he": "החרג תאריך", "en": "Exclude Date"},
    "export_btn": {"he": "ייצוא", "en": "Export"},
    "export_choice_title": {"he": "בחירת סוג ייצוא", "en": "Choose Export Type"},
    "export_choice_desc": {
        "he": "אפשר לשמור את הלוח הנוכחי כקובץ טקסט, או ליצור קובץ ICS תקני ולפתוח אותו באפליקציית היומן המקומית",
        "en": "Save the current schedule as a text file, or create a standards-compliant ICS file and open it with your local calendar app.",
    },
    "export_text_file": {"he": "קובץ טקסט", "en": "Text file"},
    "export_local_calendar": {"he": "פתיחה ביומן המקומי", "en": "Open in local calendar"},
    "export_text_dialog_title": {"he": "שמירת קובץ טקסט", "en": "Save text file"},
    "export_calendar_dialog_title": {"he": "שמירת קובץ ICS", "en": "Save ICS calendar file"},
    "start_date": {"he": "התחלה", "en": "Start"},
    "end_date": {"he": "סיום", "en": "End"},
    "update_range": {"he": "עדכן", "en": "Update"},
    "filter_btn": {"he": "סינון לפי", "en": "Filter By"},
    "schedule_lbl": {"he": "מערכת", "en": "Schedule"},
    "out_of_lbl": {"he": "מתוך", "en": "out of"},
    "load_more": {"he": "טען עוד", "en": "Load More"},
    "refresh_feed": {"he": "רענן תצוגה", "en": "Refresh Feed"},
    "refresh_feed_tooltip": {"he": "רענן את חלון התוצאות לפי המיון הפעיל", "en": "Refresh the result window using the active sort"},
    "empty_state": {"he": "יש לטעון נתונים", "en": "Please load data"},
    "computing": {"he": "מחשב שיבוצים", "en": "Computing schedules..."},
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
    "date_format": {"he": "יום/חודש/שנה", "en": "dd/mm/yyyy"},
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
    "sort_by": {"he": "מיון לפי", "en": "Sort by"},
    "sort_then": {"he": "ואז", "en": "then"},
    "sort_dir_desc": {"he": "יורד", "en": "Desc"},
    "sort_dir_asc": {"he": "עולה", "en": "Asc"},
    "sort_none": {"he": "— ללא —", "en": "— None —"},
    "end_of_results": {"he": "סוף התוצאות", "en": "End of results"},
    "metrics_panel_title": {"he": "מדדי המערכת הנוכחית", "en": "Current schedule metrics"},
    "metrics_values_button": {"he": "מדדים", "en": "Metrics"},
    "metrics_values_tooltip": {"he": "פתח חלונית עם חמשת המדדים המלאים", "en": "Open the full five-metric details popup"},
    "metrics_values_empty": {"he": "אין עדיין מדדים להצגה", "en": "No metrics to display yet"},
    "sort_selector_tooltip": {"he": "בחירת מדדי מיון וסדר עדיפות", "en": "Choose sort metrics and priority order"},
    "sort_selector_title": {"he": "בחירת סדר מיון", "en": "Sort Criteria Priority"},
    "sort_selector_hint": {"he": "סמן את המדדים שישתתפו במיון סדר השורות קובע עדיפות: השורה הראשונה היא המדד הראשי ניתן לגרור שורות או להשתמש בחצים", "en": "Select the metrics used for sorting. Row order sets priority: the first row is the primary criterion. Drag rows or use the arrow buttons."},
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
    "info_title": {"he": "דירוג ומדדים - הסבר", "en": "Ranking & Metrics — Help"},
    "info_sort_title": {"he": "מיון", "en": "Sorting"},
    "info_sort_desc": {
        "he": "המיון קובע רק את סדר הצגת הלוחות הוא לא מוסיף ולא מסיר לוחות בוחרים אילו מדדים ישתתפו במיון ומסדרים אותם לפי עדיפות: המדד הראשון הוא הראשי, והבאים אחריו שוברים שוויון הכיוון ״יורד״ מציג ערכים גבוהים תחילה, ו״עולה״ מציג ערכים נמוכים תחילה השינוי מיידי ואינו מריץ מחדש את המנוע",
        "en": "Sorting only sets the order in which schedules are shown. It never adds or removes schedules. Choose which metrics participate in sorting and arrange them by priority: the first metric is primary, and later metrics break ties. ‘Desc’ shows higher values first, and ‘Asc’ shows lower values first. The change applies immediately and does not re-run the engine.",
    },
    "info_metrics_title": {"he": "חמשת המדדים", "en": "The five metrics"},
    "info_pref_higher": {"he": "מומלץ ערך גבוה", "en": "Higher is better"},
    "info_pref_lower": {"he": "מומלץ ערך נמוך", "en": "Lower is better"},
    "info_metric_avg_gap_all": {
        "he": "ממוצע מספר הימים בין כל זוג בחינות (חובה או בחירה) באותה תוכנית ובאותה שנה",
        "en": "The average number of days between every pair of exams (mandatory or elective) in the same program and year.",
    },
    "info_metric_min_gap_mandatory": {
        "he": "מספר הימים הקטן ביותר שמפריד בין שתי בחינות חובה כלשהן באותה תוכנית ובאותה שנה",
        "en": "The fewest days separating any two mandatory exams in the same program and year.",
    },
    "info_metric_elective_conflicts": {
        "he": "מספר זוגות קורסי הבחירה באותה תוכנית שנקבעו לאותו יום",
        "en": "The number of elective-course pairs in the same program scheduled on the same day.",
    },
    "info_metric_mandatory_span": {
        "he": "מספר הימים מבחינת החובה הראשונה ועד בחינת החובה האחרונה באותה תוכנית ובאותה שנה",
        "en": "The number of days from the first mandatory exam to the last, in the same program and year.",
    },
    "info_metric_max_exams_per_day": {
        "he": "מספר הבחינות הגדול ביותר שנקבעו לאותו יום בלוח",
        "en": "The largest number of exams scheduled on any single day.",
    },

    # --- Information popup: constraints and calendar controls (PLAN-582) ---
    "info_constraints_title": {"he": "אילוצי שיבוץ", "en": "Scheduling constraints"},
    "info_constraints_desc": {
        "he": "כפתור האילוצים פותח מסך הגדרות שמאפשר להפעיל או לכבות אילוצים חדשים ולהגדיר ערך מספרי לכל אילוץ שינוי אילוצים משפיע על הרצת המנוע הבאה, ולכן לא ניתן לשמור אילוצים בזמן שהמנוע עדיין רץ",
        "en": "The Constraints button opens a settings screen for enabling or disabling the new constraints and setting a k value for each one. Constraint changes affect the next engine run, so they cannot be saved while generation is still active.",
    },
    "info_constraint_min_days_mandatory": {
        "he": "כאשר האילוץ פעיל, המנוע מנסה לשמור לפחות את מספר הימים שהוגדר בין שתי בחינות חובה באותה תוכנית ובאותה שנה",
        "en": "When enabled, the engine tries to keep at least k days between two mandatory exams in the same program and year.",
    },
    "info_constraint_min_days_any": {
        "he": "כאשר האילוץ פעיל, המנוע מנסה לשמור לפחות את מספר הימים שהוגדר בין כל שתי בחינות באותה תוכנית ובאותה שנה, גם חובה וגם בחירה",
        "en": "When enabled, the engine tries to keep at least k days between any two exams in the same program and year, both mandatory and elective.",
    },
    "info_constraint_max_elective_conflicts": {
        "he": "כאשר האילוץ פעיל, המנוע מגביל את מספר ההתנגשויות המותרות בין קורסי בחירה לערך שהוגדר לכל היותר",
        "en": "When enabled, the engine limits the allowed number of elective-course conflicts to at most k.",
    },
    "info_constraint_span_mandatory": {
        "he": "כאשר האילוץ פעיל, המנוע מנסה להגביל את הטווח בין בחינת החובה הראשונה לאחרונה למספר הימים שהוגדר לכל היותר",
        "en": "When enabled, the engine tries to limit the span from the first mandatory exam to the last mandatory exam to at most k days.",
    },
    "info_constraint_max_exams_per_day": {
        "he": "כאשר האילוץ פעיל, המנוע מגביל את מספר הבחינות שניתן לשבץ באותו יום לערך שהוגדר לכל היותר",
        "en": "When enabled, the engine limits the number of exams scheduled on the same day to at most k.",
    },
    "info_calendar_buttons_title": {"he": "כפתורי מסך הלוח", "en": "Calendar view buttons"},
    "info_calendar_buttons_desc": {
        "he": "הכפתורים במסך הלוח מנהלים ניווט, מיון, עריכה ופעולות תצוגה כל פעולה עוברת דרך שכבת התיווך ואינה פונה ישירות למנוע או לאינדקס התוצאות",
        "en": "The calendar-view buttons control navigation, sorting, editing, and display actions. Each action goes through the Presenter and does not access the engine or result index directly.",
    },
    "info_button_navigation_title": {"he": "ניווט בין מערכות", "en": "Schedule navigation"},
    "info_button_navigation_desc": {
        "he": "כפתורי הקודם/הבא ושדה מספר העמוד מאפשרים לעבור בין המערכות שנוצרו בזמן שהמנוע רץ, הניווט מוגבל לחלון התוצאות הזמין; לאחר סיום הריצה ניתן לנווט בכל התוצאות",
        "en": "The previous/next buttons and page field move between generated schedules. While the engine is running, navigation is limited to the available result window; after completion, the full sorted result set can be browsed.",
    },
    "info_button_sort_selector_title": {"he": "בחירת מיון", "en": "Sort selector"},
    "info_button_sort_selector_desc": {
        "he": "כפתור בחירת המיון מאפשר לבחור כמה מדדים ולסדר אותם לפי עדיפות המיון משנה רק את סדר ההצגה ואינו מריץ מחדש את המנוע",
        "en": "The sort selector lets you choose multiple metrics and order them by priority. Sorting changes only the display order and does not re-run the engine.",
    },
    "info_button_metrics_title": {"he": "מדדים", "en": "Metrics"},
    "info_button_metrics_desc": {
        "he": "כפתור המדדים מציג את חמשת ערכי המדדים של המערכת הנוכחית לאחר עריכה ידנית, המדדים מחושבים מחדש לפי הלוח שמוצג בפועל",
        "en": "The Metrics button shows the five metric values for the current schedule. After a manual edit, the metrics are recalculated from the currently displayed calendar.",
    },
    "info_button_refresh_feed_title": {"he": "רענון תוצאות", "en": "Refresh feed"},
    "info_button_refresh_feed_desc": {
        "he": "כפתור רענון התוצאות טוען מחדש את חלון התוצאות הזמין לפי המיון הפעיל הוא לא יוצר מערכות חדשות ולא מריץ מחדש את המנוע",
        "en": "The refresh-feed button reloads the available result window using the active sorting criteria. It does not create new schedules and does not re-run the engine.",
    },
    "info_button_load_more_title": {"he": "טען עוד", "en": "Load more"},
    "info_button_load_more_desc": {
        "he": "כפתור טען עוד מבקש מהמערכת להמשיך ליצור מערכות נוספות מעבר למה שכבר נוצר, תוך שימוש בספירת דילוגים כדי לא להתחיל מהתחלה",
        "en": "The Load More button asks the engine to generate additional schedules beyond the existing results, using a skip count so generation does not restart from the beginning.",
    },
    "info_button_constraints_title": {"he": "אילוצים", "en": "Constraints"},
    "info_button_constraints_desc": {
        "he": "כפתור האילוצים פותח את חלון הגדרות האילוצים ניתן להפעיל אילוץ, לכבות אותו, ולשנות את הערך המספרי שלו לפני הרצת החישוב",
        "en": "The Constraints button opens the constraint settings window. You can enable a constraint, disable it, and change its k value before running generation.",
    },
    "info_button_edit_dates_title": {"he": "עריכת תאריכים", "en": "Edit dates"},
    "info_button_edit_dates_desc": {
        "he": "כפתור עריכת התאריכים מאפשר לעדכן ידנית את טווחי מועדי הבחינות המשמשים להצגת ולחישוב המערכות",
        "en": "The Edit Dates button lets you manually update the exam-period date ranges used for displaying and generating schedules.",
    },
    "info_button_exclude_title": {"he": "החרגת יום", "en": "Exclude date"},
    "info_button_exclude_desc": {
        "he": "כפתור ההחרגה מסמן יום שלא אמור לשמש לשיבוץ בחינות, בהתאם לפעולת המשתמש על הלוח",
        "en": "The Exclude Date button marks a day that should not be used for exam scheduling, according to the user's calendar action.",
    },
    "info_button_undo_title": {"he": "ביטול עריכה ידנית", "en": "Undo manual edit"},
    "info_button_undo_desc": {
        "he": "כפתור הביטול מחזיר את הלוח למצב האחרון לפני שינוי ידני, למשל לאחר גרירה או שינוי תאריך ידני",
        "en": "The Undo button restores the calendar to the previous state before a manual change, such as a drag-and-drop or manual date edit.",
    },
    "info_button_export_title": {"he": "ייצוא", "en": "Export"},
    "info_button_export_desc": {
        "he": "כפתור הייצוא פותח שתי אפשרויות: שמירת קובץ טקסט, או יצירת קובץ ICS תקני שניתן לפתוח ב-Google Calendar, Outlook או Apple Calendar. קובץ ה-ICS כולל רק אירועי מבחן מהלוח המוצג בפועל, ללא אילוצים פנימיים, ימי חג או נתוני חישוב",
        "en": "The Export button opens two options: save a text file, or create a standards-compliant ICS file that can be opened in Google Calendar, Outlook, or Apple Calendar. The ICS file contains only exam events from the currently displayed schedule, without internal constraints, holiday blocks, or calculation data.",
    },

    # --- Pruning constraints settings modal (PLAN-418) ---
    "constraints_button": {"he": "אילוצים", "en": "Constraints"},
    "constraints_tooltip": {"he": "הגדרות אילוצי שיבוץ", "en": "Scheduling constraints settings"},
    "constraints_title": {"he": "הגדרות אילוצי שיבוץ", "en": "Scheduling Constraints"},
    "constraints_header_name": {"he": "אילוץ", "en": "Constraint"},
    "constraints_header_enabled": {"he": "פעיל", "en": "Enabled"},
    "constraints_header_k": {"he": "ערך מספרי", "en": "k value"},
    "constraint_min_days_mandatory": {"he": "מרווח מינימלי בין מבחני חובה באותה תוכנית ושנה", "en": "Minimum days between mandatory exams in the same program/year"},
    "constraint_min_days_any": {"he": "מרווח מינימלי בין כל שתי בחינות באותה תוכנית ושנה", "en": "Minimum days between any two exams in the same program/year"},
    "constraint_max_elective_conflicts": {"he": "מקסימום התנגשויות בין קורסי בחירה", "en": "Maximum elective-elective conflicts"},
    "constraint_span_mandatory": {"he": "טווח מקסימלי בין מבחן חובה ראשון לאחרון", "en": "Maximum span from first to last mandatory exam"},
    "constraint_max_exams_per_day": {"he": "מקסימום בחינות באותו יום", "en": "Maximum exams on the same day"},
    "constraints_invalid": {"he": "הערך חייב להיות מספר שלם ולא שלילי", "en": "k must be a non-negative whole number"},
    "constraints_locked": {"he": "לא ניתן לשמור אילוצים בזמן שהמנוע רץ", "en": "Constraints cannot be saved while the engine is running"},
    "constraints_saved": {"he": "האילוצים נשמרו בהצלחה", "en": "Constraints saved successfully"},
}

def format_text(key: str, lang: str) -> str:
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    return f"\u200F{text}\u200F" if lang == "he" else text