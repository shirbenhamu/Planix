import customtkinter as ctk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.ui.views.input_view import InputConfigurationView
from src.ui.views.calendar_view import CalendarGridView 

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Planix 2.0")
        self.geometry("1000x750") 
        
        ctk.set_appearance_mode("Dark") 
        ctk.set_default_color_theme("blue")
        
        self.top_bar = ctk.CTkFrame(self, height=40, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=10)
        
        self.lang_var = ctk.StringVar(value="he")
        self.lang_switch = ctk.CTkSwitch(
            self.top_bar, text="English", command=self._toggle_language,
            variable=self.lang_var, onvalue="en", offvalue="he", font=("Arial", 14, "bold")
        )
        self.lang_switch.pack(side="left")

        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(
            self.top_bar, text="מצב יום", command=self._toggle_theme,
            variable=self.theme_var, onvalue="Light", offvalue="Dark", font=("Arial", 14, "bold")
        )
        self.theme_switch.pack(side="right")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        # תוקן סדר המילים בטאבים!
        self.tab_input_name = "נתונים טעינתו קלט הגדרות"
        self.tab_calendar_name = "(פלט) מבחנים לוח"
        
        self.tabview.add(self.tab_input_name)
        self.tabview.add(self.tab_calendar_name)

        self.input_view = InputConfigurationView(self.tabview.tab(self.tab_input_name))
        self.input_view.pack(fill="both", expand=True)

        self.calendar_view = CalendarGridView(self.tabview.tab(self.tab_calendar_name))
        self.calendar_view.pack(fill="both", expand=True)

        self.tabview.set(self.tab_calendar_name)

        # ==========================================
        # הזרקת נתוני דמה לבדיקה בלבד
        # ==========================================
        dummy_programs = {
            "83101": "הנדסת מחשבים" if self.lang_var.get() == "he" else "Computer Engineering",
            "83102": "הנדסת חשמל" if self.lang_var.get() == "he" else "Electrical Engineering"
        }
        self.input_view.display_programs_list(dummy_programs)
        
        self.dummy_calendar_data = {
            "1-2": {"day_text": "1", "exams": [{"name": "מבני נתונים", "course_id": "83104", "type": "חובה"}]},
            "1-3": {"day_text": "2"},
            "1-4": {"day_text": "3"},
            "1-5": {"day_text": "4", "is_excluded": True}, 
            "1-6": {"day_text": "5", "is_excluded": True}, 
            
            "2-0": {"day_text": "6", "exams": [
                {"name": "אלגוריתמים", "course_id": "83105", "type": "חובה"},
                {"name": "הסתברות", "course_id": "83106", "type": "בחירה"} 
            ]},
            "2-1": {"day_text": "7"},
            "2-2": {"day_text": "8", "exams": [{"name": "מערכות הפעלה", "course_id": "83107", "type": "חובה"}]},
            "2-3": {"day_text": "9"},
            "2-4": {"day_text": "10", "is_excluded": True}, 
            "2-5": {"day_text": "11", "is_excluded": True},
            "2-6": {"day_text": "12", "is_excluded": True},
            
            "3-0": {"day_text": "13"},
            "3-1": {"day_text": "14", "exams": [{"name": "מבוא ל-AI", "course_id": "83110", "type": "בחירה"}]},
        }
        
        self.calendar_view.render_calendar_data(self.dummy_calendar_data)

        # ==========================================
        # לוגיקת פריזנטר "מדומה" לבדיקת הממשק
        # ==========================================
        
        def mock_exclude_handler(cell_key):
            if cell_key in self.dummy_calendar_data:
                current_status = self.dummy_calendar_data[cell_key].get("is_excluded", False)
                self.dummy_calendar_data[cell_key]["is_excluded"] = not current_status
            else:
                self.dummy_calendar_data[cell_key] = {"is_excluded": True}
            self.calendar_view.render_calendar_data(self.dummy_calendar_data)
        self.calendar_view.on_exclude_clicked = mock_exclude_handler

        self.calendar_view.on_range_update_clicked = lambda s, e: print(f"Update Range: {s} - {e}")
        self.calendar_view.on_filter_clicked = lambda: print("Filter Dialog Triggered")

        # --- לוגיקת ניווט מדומה חיה ---
        self.current_mock_page = 1
        self.total_mock_pages = 45
        self.calendar_view.update_pagination(self.current_mock_page, self.total_mock_pages)

        def mock_next():
            if self.current_mock_page < self.total_mock_pages:
                self.current_mock_page += 1
                self.calendar_view.update_pagination(self.current_mock_page, self.total_mock_pages)
                
        def mock_prev():
            if self.current_mock_page > 1:
                self.current_mock_page -= 1
                self.calendar_view.update_pagination(self.current_mock_page, self.total_mock_pages)

        def mock_page_jump(page_num):
            if 1 <= page_num <= self.total_mock_pages:
                self.current_mock_page = page_num
                self.calendar_view.update_pagination(self.current_mock_page, self.total_mock_pages)

        self.calendar_view.on_next_clicked = mock_next
        self.calendar_view.on_prev_clicked = mock_prev
        self.calendar_view.on_page_jump = mock_page_jump

        # --- ייצוא ושמירת קובץ אמיתית לבדיקה ---
        def mock_export(file_path):
            try:
                # אשכרה מייצר קובץ כדי שתוכל לראות שזה עובד!
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Planix 2.0 Export Test\n")
                    f.write(f"Exported schedule page: {self.current_mock_page}\n")
                    f.write("This proves the UI properly passed the path to the Presenter!")
                print(f"Success! File saved at: {file_path}")
            except Exception as e:
                print(f"Failed to save file: {e}")

        self.calendar_view.on_export_clicked = mock_export

    def _toggle_language(self):
        new_lang = self.lang_var.get()
        self.lang_switch.configure(text="עברית" if new_lang == "en" else "English")
        self.theme_switch.configure(text="מצב יום" if self.theme_var.get() == "Dark" else "מצב לילה" if new_lang == "he" else "Light Mode" if self.theme_var.get() == "Dark" else "Dark Mode")
        
        self.input_view.update_language(new_lang)
        self.calendar_view.update_language(new_lang)
        self.calendar_view.render_calendar_data(self.dummy_calendar_data)

    def _toggle_theme(self):
        self._fade_out(1.0, 0.90, self._apply_theme_switch)

    def _apply_theme_switch(self):
        new_theme = self.theme_var.get()
        ctk.set_appearance_mode(new_theme)
        
        is_hebrew = self.lang_var.get() == "he"
        if new_theme == "Light":
            self.theme_switch.configure(text="מצב לילה" if is_hebrew else "Dark Mode")
        else:
            self.theme_switch.configure(text="מצב יום" if is_hebrew else "Light Mode")
            
        self.update_idletasks() 
        self._fade_in(0.90, 1.0)

    def _fade_out(self, current_alpha, target_alpha, callback):
        if current_alpha > target_alpha:
            current_alpha -= 0.02 
            self.attributes("-alpha", current_alpha)
            self.after(10, lambda: self._fade_out(current_alpha, target_alpha, callback)) 
        else:
            callback()

    def _fade_in(self, current_alpha, target_alpha):
        if current_alpha < target_alpha:
            current_alpha += 0.02
            self.attributes("-alpha", current_alpha)
            self.after(10, lambda: self._fade_in(current_alpha, target_alpha))
        else:
            self.attributes("-alpha", 1.0)

if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()