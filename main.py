import scheduler_model as sm
import logging

# Configure logger behavior globally
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler()               # Print logs to console
    ]
)

# 1. General Configuration
year = 2026
month = 4
flexibility = 2
max_fitting_minutes = 1  

# 2. Define Shifts
shifts = [
    sm.Shift(name="Morning",   start=7 * 60,  end=15 * 60, workers_required=1),
    sm.Shift(name="Morning 2", start=10 * 60 + 30, end=18 * 60 + 30, workers_required=1),
    sm.Shift(name="Evening", start=15 * 60, end=23 * 60, workers_required=1),
    sm.Shift(name="Night",     start=23 * 60 + 1, end=7 * 60 + 1,  workers_required=1)
]
shifts = sorted(shifts, key= lambda s : s.start)

# 3. Define the workers
w1 = sm.Worker(
    name=f"Joseph", 
    preferences=[1, 1, 3, 4], 
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w2 = sm.Worker(
    name=f"Jotaro", 
    preferences=[4, 4, 2, 1],
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w3 = sm.Worker(
    name=f"Polnaref", 
    preferences=[4, 3, 3, 1],
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=[5, 6, 7],
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w4 = sm.Worker(
    name=f"Avdol", 
    preferences=[2, 2, 3, 1],
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w4 = sm.Worker(
    name=f"Kakyoin", 
    preferences=[5, 1, 3, 4],
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=[20,21,22,23],
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w5 = sm.Worker(
    name=f"Iggy", 
    preferences=[1, 5, 2, 2],
    weekly_hours=20,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w6 = sm.Worker(
    name=f"Suzi", 
    preferences=[1, 1, 2, 4],
    weekly_hours=40,
    is_management=False,
    works_weekends=True,      
    min_one_weekend_off=True,     
    allowed_shifts=[True,True,True,True],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

w7 = sm.Worker(
    name=f"Dio", 
    preferences=[20, 20, 20, 20],
    weekly_hours=None,
    is_management=True,
    works_weekends=True,      
    min_one_weekend_off=False,     
    allowed_shifts=[True,True,True,False],
    holidays=None,
    break_hours=12,
    max_consec_works = 6,
    min_consec_breaks = 2
    )

workers = [w1,w2,w3,w4,w5,w6,w7]

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