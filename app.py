import streamlit as st
import pandas as pd
import scheduler_model as sm
from ortools.sat.python import cp_model

st.set_page_config(page_title="Timetable Optimizer", page_icon="📅", layout="wide")
st.title("📅 Dani's Scheduler")

def time_to_minutes(time_str: str) -> int:
    """Converts a time string like '06:30' or '6:30' to minutes from midnight."""
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) != 2:
            raise ValueError
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError):
        raise ValueError(f"Invalid time format: '{time_str}'. Please use HH:MM format (e.g., 14:30).")

# --- Default Data Generators ---
# In a real app, you might load this from a saved CSV database
def get_default_shifts():
    return pd.DataFrame([
        {"Name": "Morning", "Start Time": "07:00", "End Time": "15:00", "Workers Req": 1},
        {"Name": "Morning 2", "Start Time": "10:30", "End Time": "18:30", "Workers Req": 1},
        {"Name": "Evening", "Start Time": "15:00", "End Time": "23:00", "Workers Req": 1},
        {"Name": "Night", "Start Time": "23:00", "End Time": "07:00", "Workers Req": 1},
    ])

def get_default_workers():
    return pd.DataFrame([
        {"Name": "Joseph", "Preferences": "1, 1, 3, 4", "Weekly Hrs": 40.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "1,2,3", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Jotaro", "Preferences": "4, 4, 2, 1", "Weekly Hrs": 40.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Polnaref", "Preferences": "4, 3, 3, 1", "Weekly Hrs": 40.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "5, 6, 7", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Avdol", "Preferences": "2, 2, 3, 1", "Weekly Hrs": 40.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Kakyoin", "Preferences": "5, 1, 3, 4", "Weekly Hrs": 20.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "20, 21, 22, 23", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Iggy", "Preferences": "1, 5, 2, 2", "Weekly Hrs": 20.0, "Is Mgmt": False, "Works Wknds": False, "Min 1 Wknd Off": False, "Allowed Shifts": "True, True, True, False", "Holidays": "", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Suzi", "Preferences": "1, 1, 2, 4", "Weekly Hrs": 20.0, "Is Mgmt": False, "Works Wknds": True, "Min 1 Wknd Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Dio", "Preferences": "3, 1, 2, 0", "Weekly Hrs": 0.0, "Is Mgmt": True, "Works Wknds": True, "Min 1 Wknd Off": False, "Allowed Shifts": "True, True, True, False", "Holidays": "", "Break Hrs": 12, "Max Works": 6, "Min Breaks": 2}
    ])

# --- UI Setup: Tabs ---
tab1, tab2, tab3 = st.tabs(["Global Settings & Shifts", "Workers", "Generate Schedule"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Global Configuration")
        year = st.number_input("Year", min_value=2024, max_value=2030, value=2026)
        month = st.number_input("Month", min_value=1, max_value=12, value=4)
        flexibility = st.slider("Flexibility (Number of shifts per month)", min_value=0, max_value=5, value=1)
        max_minutes = st.number_input("Time limit for the solver to run (Minutes)", min_value=1, max_value=10, value=1)
    
    with col2:
        st.subheader("Shifts")
        st.markdown("Edit the table below to configure shifts.")
        edited_shifts_df = st.data_editor(get_default_shifts(), num_rows="dynamic", use_container_width=True)

with tab2:
    st.subheader("Worker Configuration")
    st.markdown("Enter preferences and allowed shifts as comma-separated values (e.g., `1,1,3,4`). Make sure to include as many terms as shifts you defined in the previous page.")
    edited_workers_df = st.data_editor(get_default_workers(), num_rows="dynamic", use_container_width=True)

with tab3:
    st.subheader("Run the Solver")
    if st.button("Generate Schedule", type="primary", use_container_width=True):
        with st.spinner("Compiling data and running optimization..."):
            
            try:
                # 1. Parse DataFrames back into Dataclasses
                shifts = []
                for _, row in edited_shifts_df.iterrows():
                    start_mins = time_to_minutes(row["Start Time"])
                    end_mins = time_to_minutes(row["End Time"])
                    
                    shifts.append(sm.Shift(
                        name=row["Name"], 
                        start=start_mins, 
                        end=end_mins, 
                        workers_required=int(row["Workers Req"])
                    ))
                shifts = sorted(shifts, key=lambda s: s.start)

                workers = []
                for _, row in edited_workers_df.iterrows():
                    # Helper to parse comma-separated strings
                    prefs = [int(x.strip()) for x in str(row["Preferences"]).split(",")]
                    allowed = [x.strip().lower() == 'true' for x in str(row["Allowed Shifts"]).split(",")]
                    hols = [int(x.strip()) for x in str(row["Holidays"]).split(",") if x.strip()]
                    
                    workers.append(sm.Worker(
                        name=row["Name"],
                        preferences=prefs,
                        weekly_hours=None if row["Is Mgmt"] else float(row["Weekly Hrs"]),
                        is_management=bool(row["Is Mgmt"]),
                        works_weekends=bool(row["Works Wknds"]),
                        min_one_weekend_off=bool(row["Min 1 Wknd Off"]),
                        allowed_shifts=allowed,
                        holidays=hols if hols else None,
                        break_hours=int(row["Break Hrs"]),
                        max_consec_works=int(row["Max Works"]) if pd.notna(row["Max Works"]) else None,
                        min_consec_breaks=int(row["Min Breaks"]) if pd.notna(row["Min Breaks"]) else None
                    ))

                # 2. Build and Solve Model
                model_data = sm.define_model(year, month, shifts, workers, flexibility)
                status, solver = sm.fit_model(model_data, max_minutes)
                
                # 3. Output logic
                if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    sm.output_results(status, solver, model_data) # Generates the CSV locally
                                        
                    st.success(f"Success! Status: **{solver.StatusName(status)}** | Total Penalty Score: **{solver.ObjectiveValue()}**")
                    if status == cp_model.FEASIBLE: 
                        st.info("The solver has managed to obtain a feasable solution but it cannot guarantee its optimality. You may increase the time limit in the first page.")

                    # Extract and display individual worker performance summaries
                    st.subheader("Worker Summary")
                    summary_data = []
                    
                    num_slots = model_data["num_slots"]
                    num_shifts = model_data["num_shifts"]
                    num_days = model_data["num_days"]
                    x = model_data["variables"]
                    
                    for i, worker in enumerate(workers):
                        total_shifts = sum(solver.Value(x[i, s]) for s in range(num_slots))
                        total_hours = sum(solver.Value(x[i, s]) * shifts[s % num_shifts].length for s in range(num_slots)) / 60
                        total_preference = sum(solver.Value(x[i, s]) * worker.preferences[s % num_shifts] for s in range(num_slots))
                        
                        if worker.is_management:
                            summary_data.append({
                                "Worker": f"{worker.name} (Mgmt)",
                                "Total Shifts": total_shifts,
                                "Total Hours": round(total_hours, 1),
                                "Target Hours": "N/A",
                                "Preference Score": total_preference,
                                "Holidays": 0
                            })
                        else:
                            target_hours = worker.get_target_minutes(num_days) / 60
                            num_holidays = len(worker.holidays) if worker.holidays is not None else 0
                            summary_data.append({
                                "Worker": worker.name,
                                "Total Shifts": total_shifts,
                                "Total Hours": round(total_hours, 1),
                                "Target Hours": round(target_hours, 1),
                                "Preference Score": total_preference,
                                "Holidays": num_holidays
                            })
                    
                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                    
                    # --- Main Timetable Grid ---
                    st.subheader("Monthly Timetable Grid")
                    df_results = pd.read_csv("results.csv", index_col=0)
                    st.dataframe(df_results, use_container_width=True)
                    
                    st.download_button(
                        label="📥 Download Timetable (CSV)",
                        data=df_results.to_csv().encode('utf-8'),
                        file_name=f"schedule_{year}_{month}.csv",
                        mime="text/csv",
                    )
                else:
                    st.error("The solver could not find a valid schedule. See the analysis below.")
                    analysis_report = sm.get_feasibility_analysis(model_data)
                    st.warning(analysis_report)

            except Exception as e:
                st.error(f"Data formatting error: {e}")
                st.info("Check your comma-separated lists to ensure they match the number of shifts!")