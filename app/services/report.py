from typing import List, Dict, Any, Optional
import datetime
import pandas as pd
import numpy as np
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
        import time
        start_time = time.time()
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

        fetch_done = time.time()
        from app.services.pdf_gen import logger
        logger.info(f"[REPORT] Data fetch took {fetch_done - start_time:.2f}s ({len(entries)} entries, {len(events)} events)")

        # Initialize metrics
        metrics = {
            "avg_glucose": 0,
            "tir": {
                "vlow": 0, "low": 0, "inRange": 0, "high": 0, "vhigh": 0
            },
            "gmi": 0,
            "cv": 0,
            "total_readings": 0,
            "days_covered": 0
        }

        agp_data = {
            "median": [],
            "p25": [],
            "p75": [],
            "p10": [],
            "p90": []
        }
        daily_groups = []

        if not df_entries.empty and "sgv" in df_entries.columns:
            # Ensure proper types
            df_entries["sgv"] = df_entries["sgv"].astype(float)
            df_entries["date_dt"] = pd.to_datetime(df_entries["date"], unit="ms")
            
            sgvs = df_entries["sgv"]
            metrics["avg_glucose"] = round(sgvs.mean(), 1)
            metrics["total_readings"] = len(sgvs)
            metrics["days_covered"] = (df_entries["date_dt"].max() - df_entries["date_dt"].min()).days + 1
            
            # TIR Calculation (5 levels)
            metrics["tir"] = {
                "vlow": round((sgvs < 54).sum() / len(sgvs) * 100, 1),
                "low": round((sgvs.between(54, 69).sum() / len(sgvs)) * 100, 1),
                "inRange": round((sgvs.between(70, 180).sum() / len(sgvs)) * 100, 1),
                "high": round((sgvs.between(181, 250).sum() / len(sgvs)) * 100, 1),
                "vhigh": round((sgvs > 250).sum() / len(sgvs) * 100, 1),
            }
            
            # GMI = 3.31 + (0.02392 * mean_glucose)
            metrics["gmi"] = round(3.31 + (0.02392 * metrics["avg_glucose"]), 1)
            
            # CV = (StdDev / Mean) * 100
            std_dev = sgvs.std() if len(sgvs) > 1 else 0
            metrics["cv"] = round((std_dev / metrics["avg_glucose"]) * 100, 1) if metrics["avg_glucose"] > 0 else 0
            
            # eHbA1c (Traditional formula)
            metrics["estimated_hba1c"] = round((metrics["avg_glucose"] + 46.7) / 28.7, 1)

            # --- AGP Percentiles (Hourly) ---
            df_entries["hour"] = df_entries["date_dt"].dt.hour
            # Filter non-finite SGVs
            df_agp = df_entries[np.isfinite(df_entries["sgv"])]
            hourly_stats = df_agp.groupby("hour")["sgv"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).unstack()
            # Ensure all hours 0-23 are present
            for h in range(24):
                if h not in hourly_stats.index:
                    hourly_stats.loc[h] = [0.0] * 5
            hourly_stats = hourly_stats.sort_index().fillna(0.0)
            
            agp_data = {
                "median": hourly_stats[0.5].tolist(),
                "p25": hourly_stats[0.25].tolist(),
                "p75": hourly_stats[0.75].tolist(),
                "p10": hourly_stats[0.1].tolist(),
                "p90": hourly_stats[0.9].tolist()
            }

            # --- Daily Grouping ---
            # Group entries by day
            df_entries["day_str"] = df_entries["date_dt"].dt.strftime("%Y-%m-%d")
            grouped_entries = df_entries.groupby("day_str")
            
            # Group events by day
            grouped_events = None
            if not df_events.empty:
                df_events["date_dt"] = pd.to_datetime(df_events["date"], unit="ms")
                df_events["day_str"] = df_events["date_dt"].dt.strftime("%Y-%m-%d")
                grouped_events = df_events.groupby("day_str")

            # Sort days descending
            days = sorted(df_entries["day_str"].unique(), reverse=True)
            for day in days:
                day_entries = grouped_entries.get_group(day).copy()
                day_entries["minute_of_day"] = (day_entries["date_dt"].dt.hour * 60) + day_entries["date_dt"].dt.minute
                
                day_events = pd.DataFrame()
                if grouped_events is not None and day in grouped_events.groups:
                    day_events = grouped_events.get_group(day).copy()
                
                day_treatments = []
                day_notes = []
                day_raw_events = [] # For SVG markers
                
                if not day_events.empty:
                    for _, ev in day_events.iterrows():
                        time_str = ev["date_dt"].strftime("%H:%M")
                        # Minute of day for SVG positioning (0-1439)
                        mod = (ev["date_dt"].hour * 60) + ev["date_dt"].minute
                        
                        e_type = str(ev.get("eventType") or "")
                        insulin = ev.get("insulin")
                        notes = str(ev.get("notes") or "")
                        
                        # Categorize for SVG
                        cat = "other"
                        if e_type in ["Meal Bolus", "Correction Bolus", "Bolus"]:
                            cat = "insulin"
                        elif "carbs" in notes.lower() or e_type == "Meal":
                            cat = "carbs"
                        elif "exercise" in notes.lower() or "walk" in notes.lower():
                            cat = "exercise"
                            
                        day_raw_events.append({
                            "t": mod,
                            "cat": cat,
                            "val": insulin if cat == "insulin" else 1 # default size
                        })

                        if cat == "insulin":
                            desc = f"{insulin}u {notes}".strip()
                            day_treatments.append({"time": time_str, "desc": desc or e_type, "cat": "insulin"})
                        elif cat == "carbs":
                            day_treatments.append({"time": time_str, "desc": notes or "Meal", "cat": "carbs"})
                        else:
                            day_notes.append({
                                "time": time_str,
                                "text": notes or e_type,
                                "tag": e_type.lower()
                            })

                day_dt = pd.to_datetime(day)
                day_sgvs = day_entries["sgv"]
                
                # Daily CV calculation
                day_avg = day_sgvs.mean()
                day_std = day_sgvs.std() if len(day_sgvs) > 1 else 0
                day_cv = round((day_std / day_avg) * 100, 1) if day_avg > 0 else 0
                
                daily_info = {
                    "date": day,
                    "day_name": day_dt.strftime("%a"),
                    "date_display": day_dt.strftime("%d %b %Y"),
                    "avg": round(day_avg, 0),
                    "cv": day_cv,
                    "tir": {
                        "vlow": round((day_sgvs < 54).sum() / len(day_sgvs) * 100, 0),
                        "low": round((day_sgvs.between(54, 69).sum() / len(day_sgvs)) * 100, 0),
                        "inRange": round((day_sgvs.between(70, 180).sum() / len(day_sgvs)) * 100, 0),
                        "high": round((day_sgvs.between(181, 250).sum() / len(day_sgvs)) * 100, 0),
                        "vhigh": round((day_sgvs > 250).sum() / len(day_sgvs) * 100, 0),
                    },
                    "min": int(day_sgvs.min()),
                    "max": int(day_sgvs.max()),
                    "readings": day_entries.sort_values("date")[["sgv", "minute_of_day"]].rename(columns={"sgv": "v", "minute_of_day": "t"}).to_dict("records"),
                    "treatments": day_treatments,
                    "notes": day_notes,
                    "raw_events": day_raw_events
                }
                daily_groups.append(daily_info)

        return {
            "metrics": metrics,
            "agp_data": agp_data,
            "daily_groups": daily_groups,
            "start_date": datetime.datetime.fromtimestamp(start_ms/1000).strftime("%b %d, %Y"),
            "end_date": datetime.datetime.fromtimestamp(end_ms/1000).strftime("%b %d, %Y"),
            "generation_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "df_entries": df_entries
        }
