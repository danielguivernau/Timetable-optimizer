import scheduler_model as sm
import logging

# Configure logger behavior globally
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),               # Print logs to console
        logging.FileHandler("scheduler.log")   # Save logs to file
    ]
)

# 1. General Configuration
year = 2026
month = 4
flexibility = 1
max_fitting_minutes = 1  

# 2. Define Shifts
# Note: The Night shift is just 23 to 7. The Shift class handles the +24 math for you!
shifts = [
    sm.Shift(name="Morning",   start=7 * 60,  end=15 * 60, workers_required=1),
    sm.Shift(name="Morning 2", start=10 * 60 + 30, end=18 * 60 + 30, workers_required=1),
    sm.Shift(name="Evening", start=15 * 60, end=23 * 60, workers_required=1),
    sm.Shift(name="Night",     start=23 * 60 + 1, end=7 * 60 + 1,  workers_required=1)
]
shifts = sorted(shifts, key= lambda s : s.start)

# 3. Define Workers
preferences = [
    [1, 1, 3, 4],
    [4, 4, 2, 1],
    [4, 3, 3, 1],
    [1, 5, 2, 2],
    [5, 1, 3, 4],
    [2, 2, 3, 1],
    [20, 20, 20, 20] # Management preferences
]
weekly_hours = [40, 40, 40, 40, 20, 40]

holidays = [
    None,
    None,
    [5, 6, 7],
    None,
    None,
    [20,21,22,23],
    None # Management preferences
]

workers = []

# Add the regular workers
for i in range(len(preferences) -1):
    workers.append(
        sm.Worker(
            name=f"Worker {i+1}", 
            preferences=preferences[i], 
            weekly_hours=weekly_hours[i],
            holidays=holidays[i],
            break_hours=12,
            max_consec_works = 6,
            min_consec_breaks = 2
        )
    )

# Add the Management Worker
workers.append(
    sm.Worker(
        name="Management",
        preferences=preferences[5],
        weekly_hours=None,          # Managers don't have a fixed weekly hour target
        is_management=True,
        works_weekends=True,      
        min_one_weekend_off=False,     
        allowed_shifts=[True,True,True,False],
        holidays=holidays[5],
        break_hours = 12
    )
)

# 4. Build and Solve the Model
logging.info("Building the model...")
model_data = sm.define_model(
    year=year,
    month=month,
    shifts=shifts,
    workers=workers,
    flexibility=flexibility
)

logging.info("Solving the model...")
status, solver = sm.fit_model(model_data, max_fitting_minutes)

# 5. Output Results
sm.output_results(status, solver, model_data)