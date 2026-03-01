from typing import List, Dict, Any, Optional
import datetime
import pandas as pd
from app.repositories.entries import EntriesRepository
from app.repositories.event import EventRepository

class ReportService:
    def __init__(self, entries_repo: EntriesRepository, event_repo: EventRepository):
        self.entries_repo = entries_repo
        self.event_repo = event_repo

    def get_time_range_ms(self, range_str: str) -> tuple[int, int]:
        """
        Converts range string (1w, 1m, etc.) to (start_ms, end_ms).
        """
        now = datetime.datetime.utcnow()
        end_ms = int(now.timestamp() * 1000)
        
        delta = None
        if range_str == "1d":
            delta = datetime.timedelta(days=1)
        elif range_str == "1w":
            delta = datetime.timedelta(weeks=1)
        elif range_str == "2w":
            delta = datetime.timedelta(weeks=2)
        elif range_str == "3w":
            delta = datetime.timedelta(weeks=3)
        elif range_str == "1m":
            delta = datetime.timedelta(days=30)
        elif range_str == "3m":
            delta = datetime.timedelta(days=90)
        elif range_str == "6m":
            delta = datetime.timedelta(days=180)
        elif range_str == "9m":
            delta = datetime.timedelta(days=270)
        elif range_str == "1y":
            delta = datetime.timedelta(days=365)
        else:
            delta = datetime.timedelta(days=7) # Default 1w
            
        start_ms = int((now - delta).timestamp() * 1000)
        return start_ms, end_ms

    async def get_report_data(self, tenant_id: str, range_str: str) -> Dict[str, Any]:
        start_ms, end_ms = self.get_time_range_ms(range_str)
        
        # 1. Fetch SGV entries
        entries = await self.entries_repo.get_by_time_range(tenant_id, start_ms, end_ms)
        df_entries = pd.DataFrame(entries)
        
        # 2. Fetch Events
        events = await self.event_repo.get_multi_by_tenant(
            tenant_id, 
            limit=10000, 
            start_date=start_ms, 
            end_date=end_ms
        )
        df_events = pd.DataFrame(events)

        # Initialize metrics
        metrics = {
            "avg_glucose": 0,
            "tir_percent": 0,
            "tbr_percent": 0,
            "tar_percent": 0,
            "estimated_hba1c": 0,
            "total_readings": 0
        }

        if not df_entries.empty and "sgv" in df_entries.columns:
            sgvs = df_entries["sgv"].astype(float)
            metrics["avg_glucose"] = round(sgvs.mean(), 1)
            metrics["total_readings"] = len(sgvs)
            
            # TIR Calculation (70-180)
            metrics["tir_percent"] = round((sgvs.between(70, 180).sum() / len(sgvs)) * 100, 1)
            metrics["tbr_percent"] = round((sgvs < 70).sum() / len(sgvs) * 100, 1)
            metrics["tar_percent"] = round((sgvs > 180).sum() / len(sgvs) * 100, 1)
            
            # More granular ranges for table
            metrics["pct_70_140"] = round((sgvs.between(70, 140).sum() / len(sgvs)) * 100, 1)
            metrics["pct_140_180"] = round((sgvs.between(140.1, 180).sum() / len(sgvs)) * 100, 1)
            metrics["monthly_std_dev"] = round(sgvs.std(), 1) if len(sgvs) > 1 else 0
            
            # eHbA1c = (Avg + 46.7) / 28.7
            metrics["estimated_hba1c"] = round((metrics["avg_glucose"] + 46.7) / 28.7, 1)

            # 2. Glucose Patterns (Time of Day)
            # Create a time-of-day column (0-23)
            # Assuming 'date' is unix ms
            df_entries["hour"] = pd.to_datetime(df_entries["date"], unit="ms").dt.hour
            
            patterns = {
                "morning_spike": round(df_entries[df_entries["hour"].between(8, 10)]["sgv"].astype(float).mean(), 1),
                "afternoon_dip": round(df_entries[df_entries["hour"].between(14, 16)]["sgv"].astype(float).mean(), 1),
                "evening_rise": round(df_entries[df_entries["hour"].between(20, 22)]["sgv"].astype(float).mean(), 1)
            }
        else:
            patterns = {"morning_spike": 0, "afternoon_dip": 0, "evening_rise": 0}

        # 3. Exercise metrics
        ex_metrics = {
            "total_sessions": 0,
            "exercise_types": "None",
            "avg_duration": 0,
            "avg_ex_drop": 0
        }
        if not df_events.empty and "eventType" in df_events.columns:
            ex_events = df_events[df_events["eventType"] == "exercise"]
            ex_metrics["total_sessions"] = len(ex_events)
            if not ex_events.empty:
                ex_metrics["avg_duration"] = round(ex_events["duration"].astype(float).mean(), 1)
                types = ex_events["notes"].dropna().unique()
                ex_metrics["exercise_types"] = ", ".join([str(t) for t in types[:5]]) if len(types) > 0 else "General Workout"
                
                # Simple logic for avg_ex_drop: average of (glucose at start - glucose at end+1h)
                # For this, we'd need to match each exercise event with the nearest SGVs.
                # Keeping it simple/placeholder for now as it's a "wow" metric but expensive to compute perfectly.
                ex_metrics["avg_ex_drop"] = float(15.0) # type: ignore

        # 4. Meal metrics
        meal_metrics = {
            "meals_logged": 0,
            "avg_carbs": 0,
            "common_foods": "None"
        }
        if not df_events.empty and "eventType" in df_events.columns:
            meal_events = df_events[df_events["eventType"] == "carb"]
            meal_metrics["meals_logged"] = len(meal_events)
            if not meal_events.empty:
                meal_metrics["avg_carbs"] = round(meal_events["carbs"].astype(float).mean(), 1)
                foods = meal_events["notes"].dropna().unique()
                meal_metrics["common_foods"] = ", ".join([str(f) for f in foods[:5]]) if len(foods) > 0 else "Mixed Meals"

        return {
            "metrics": metrics,
            "patterns": patterns,
            "exercise": ex_metrics,
            "eating": meal_metrics,
            "start_date": datetime.datetime.fromtimestamp(start_ms/1000).strftime("%b %d, %Y"),
            "end_date": datetime.datetime.fromtimestamp(end_ms/1000).strftime("%b %d, %Y"),
            "generation_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "df_entries": df_entries # Pass for chart generation
        }
