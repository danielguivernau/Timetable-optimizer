import streamlit as st
import pandas as pd
import scheduler_model as sm
from ortools.sat.python import cp_model

st.set_page_config(page_title="Timetable Optimizer", page_icon="📅", layout="wide")
st.title("📅 Dani's Timetable Optimizer")

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

def on_roster_upload():
    """Callback triggered whenever a file is uploaded to the roster uploader."""
    uploaded_file = st.session_state.get("roster_file_uploader")
    if uploaded_file is not None:
        try:
            st.session_state["workers_df"] = pd.read_csv(uploaded_file).fillna("")
            st.session_state["upload_error"] = None
            st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
        except Exception as e:
            st.session_state["upload_error"] = str(e)

# Default data values
def get_default_shifts():
    return pd.DataFrame([
        {"Name": "Morning", "Start Time": "07:00", "End Time": "15:00", "Workers Required": 1},
        {"Name": "Morning 2", "Start Time": "10:30", "End Time": "18:30", "Workers Required": 1},
        {"Name": "Evening", "Start Time": "15:00", "End Time": "23:00", "Workers Required": 1},
        {"Name": "Night", "Start Time": "23:00", "End Time": "07:00", "Workers Required": 1},
    ])

def get_default_workers():
    return pd.DataFrame([
        {"Name": "Joseph", "Preferences": "1, 1, 3, 4", "Weekly Hours": 40.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "1,2,3", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Jotaro", "Preferences": "4, 4, 2, 1", "Weekly Hours": 40.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Polnareff", "Preferences": "4, 3, 3, 1", "Weekly Hours": 40.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "5, 6, 7", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Avdol", "Preferences": "2, 2, 3, 1", "Weekly Hours": 40.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Kakyoin", "Preferences": "5, 1, 3, 4", "Weekly Hours": 20.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "20, 21, 22, 23", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Iggy", "Preferences": "1, 5, 2, 2", "Weekly Hours": 20.0, "Is Management": False, "Works Weekends": False, "Min 1 Weekend Off": False, "Allowed Shifts": "True, True, True, False", "Holidays": "", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Suzi", "Preferences": "1, 1, 2, 4", "Weekly Hours": 20.0, "Is Management": False, "Works Weekends": True, "Min 1 Weekend Off": True, "Allowed Shifts": "True, True, True, True", "Holidays": "", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2},
        {"Name": "Dio", "Preferences": "3, 1, 2, 0", "Weekly Hours": 0.0, "Is Management": True, "Works Weekends": True, "Min 1 Weekend Off": False, "Allowed Shifts": "True, True, True, False", "Holidays": "", "Break Hours": 12, "Max Works": 6, "Min Breaks": 2}
    ])

# Tabs
tab1, tab2, tab3 = st.tabs(["Global Settings & Shifts", "Workers", "Generate Schedule"])

with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Global configuration")
        year = st.number_input("Year", min_value=2024, max_value=2030, value=2026)
        month = st.number_input("Month", min_value=1, max_value=12, value=9)
        flexibility = st.slider(
            "Flexibility (Number of shifts each worker can deviate from their monthly hours target)", 
            min_value=0, 
            max_value=5, 
            value=1
        )
        max_minutes = st.number_input(
            "Time limit for the solver to run (Minutes)", 
            min_value=1, 
            max_value=10, 
            value=1
        )
    
    with col2:
        st.subheader("Shifts")
        st.markdown("Edit the table below to configure shifts.")
        edited_shifts_df = st.data_editor(get_default_shifts(), num_rows="dynamic", use_container_width=True)

with tab2:
    st.subheader("Worker configuration")

    # Column hint dropdown
    with st.content_expander("What do these columns mean?") if hasattr(st, "content_expander") else st.expander("What do these columns mean?"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
            * Preferences: A comma-separated list of scores (positive integers) for each shift type (ordered by start date). The lower the score the better, so workers may rank shifts by preference.
            * Weekly Hours: The target number of hours this employee should work per week.
            * Is Management: Whether the worker is management. Management roles bypass standard hourly targets and are only included in the schedule if absolutely necessary.
            * Works Weekends: Whether the worker is available to work on Saturdays and Sundays.
            * Min 1 Weekend Off: Ensures the worker gets at least one full weekend off during the month.
            """)
        with col_b:
            st.markdown("""
            * Allowed Shifts: A comma-separated list of `True/False` values indicating which shifts (ordered by start date) the worker can work.
            * Holidays: A comma-separated list of the specific days of the month where the worker is completely unavailable.
            * Break Hours: Minimum rest hours required between finishing one shift and starting another.
            * Max Works: The maximum number of consecutive days a worker can be scheduled to work.
            * Min Breaks: The minimum number of consecutive break days required once a worker starts their rest period.
            """)

    # Session state initialization
    if "workers_df" not in st.session_state:
        st.session_state["workers_df"] = get_default_workers()

    if "editor_version" not in st.session_state:
        st.session_state["editor_version"] = 0

    if st.session_state.get("upload_error"):
        st.error(f"Error reading CSV file: {st.session_state['upload_error']}")

    # Interactive Data Editor Table
    edited_workers_df = st.data_editor(
        st.session_state["workers_df"], 
        num_rows="dynamic", 
        use_container_width=True,
        key=f"workers_editor_{st.session_state['editor_version']}"
    )

    # Upload - Download buttons
    col_upload, col_download = st.columns(2)

    with col_upload:
        st.file_uploader(
            "📂 Upload saved configuration (CSV)", 
            type=["csv"], 
            help="Upload a worker configuration CSV from a previous month",
            key="roster_file_uploader",
            on_change=on_roster_upload
        )

    with col_download:
        st.markdown("<br>", unsafe_allow_html=True) # Align with upload box
        st.download_button(
            label="💾 Download current configuration (CSV)",
            data=edited_workers_df.to_csv(index=False).encode('utf-8'),
            file_name="worker_roster.csv",
            mime="text/csv",
            use_container_width=True
        )

with tab3:
    st.subheader("Run the solver")
    if st.button("Generate schedule", type="primary", use_container_width=True):
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
                        workers_required=int(row["Workers Required"])
                    ))
                shifts = sorted(shifts, key=lambda s: s.start)

                workers = []
                for _, row in edited_workers_df.iterrows():
                    prefs = [int(x.strip()) for x in str(row["Preferences"]).split(",")]
                    allowed = [x.strip().lower() == 'true' for x in str(row["Allowed Shifts"]).split(",")]
                    hols = [int(x.strip()) for x in str(row["Holidays"]).split(",") if x.strip()]
                    
                    workers.append(sm.Worker(
                        name=row["Name"],
                        preferences=prefs,
                        weekly_hours=None if row["Is Management"] else float(row["Weekly Hours"]),
                        is_management=bool(row["Is Management"]),
                        works_weekends=bool(row["Works Weekends"]),
                        min_one_weekend_off=bool(row["Min 1 Weekend Off"]),
                        allowed_shifts=allowed,
                        holidays=hols if hols else None,
                        break_hours=int(row["Break Hours"]),
                        max_consec_works=int(row["Max Works"]) if pd.notna(row["Max Works"]) else None,
                        min_consec_breaks=int(row["Min Breaks"]) if pd.notna(row["Min Breaks"]) else None
                    ))

                # 2. Build and Solve Model
                model_data = sm.define_model(year, month, shifts, workers, flexibility)
                status, solver = sm.fit_model(model_data, max_minutes)
                
                # 3. Output logic
                if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    sm.output_results(status, solver, model_data) # Generates the CSV locally
                                        
                    st.success(f"Success! Status: **{solver.StatusName(status)}** | Total penalty score: **{solver.ObjectiveValue()}**")
                    if status == cp_model.FEASIBLE: 
                        st.info("The solver has managed to obtain a feasable solution but it cannot guarantee its optimality. You may increase the time limit in the first page.")

                    # Extract and display individual worker performance summaries
                    st.subheader("Worker summary")
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
                    
                    # Main grid
                    st.subheader("Monthly generated timetable")
                    df_results = pd.read_csv("results.csv", index_col=0)
                    st.dataframe(df_results, use_container_width=True)
                    
                    st.download_button(
                        label="💾 Download generated timetable (CSV)",
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