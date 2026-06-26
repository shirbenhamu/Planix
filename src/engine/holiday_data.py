# src/engine/holiday_data.py
from datetime import date
from typing import Dict, List
import holidays

def get_holidays_for_religions(selected_religions: List[str], year: int = 2026) -> Dict[date, str]:
    """
    PLAN-555: Dynamically computes and returns a dictionary of holidays 
    for the selected religions and given academic calendar year.
    """
    holiday_cache: Dict[date, str] = {}
    if not selected_religions:
        return holiday_cache

    for religion in selected_religions:
        if religion == "Jewish":
            for holiday_date, name in holidays.IL(years=year).items():
                holiday_cache[holiday_date] = f"Jewish: {name}"
                
        elif religion == "Christian":
            for holiday_date, name in holidays.EuropeanCentralBank(years=year).items():
                if any(x in name for x in ["Christmas", "Good Friday", "Easter"]):
                    holiday_cache[holiday_date] = f"Christian: {name}"
                    
        elif religion == "Muslim":
            for holiday_date, name in holidays.Egypt(years=year).items():
                if "Eid" in name or "New Year" in name:
                    holiday_cache[holiday_date] = f"Muslim: {name}"

    return holiday_cache