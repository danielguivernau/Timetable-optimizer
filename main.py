import scheduler_model as sm

# 1. General Configuration
year = 2026
month = 4
flexibility = 1
max_minutes = 1  

# 2. Define Shifts
# Note: The Night shift is just 23 to 7. The Shift class handles the +24 math for you!
shifts = [
    sm.Shift(name="Morning",   start=7,  end=15, workers_required=1),
    sm.Shift(name="Morning 2", start=10, end=18, workers_required=1),
    sm.Shift(name="Evening", start=15, end=23, workers_required=1),
    sm.Shift(name="Night",     start=23, end=7,  workers_required=1)
]
shifts = sorted(shifts, key= lambda s : s.start)
break_hours = 12

# 3. Define Workers
preferences = [
    [1, 1, 3, 4],
    [4, 4, 2, 1],
    [4, 3, 3, 1],
    [1, 5, 2, 2],
    [5, 1, 3, 4],
    [20, 20, 20, 20] # Management preferences
]
weekly_hours = [40, 40, 40, 40, 40]

holidays = [
    None,
    None,
    [5, 6, 7],
    None,
    None,
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
            holidays=holidays[i]
        )
    )

# Add the Management Worker
workers.append(
    sm.Worker(
        name="Management",
        preferences=preferences[5],
        weekly_hours=None,          # Managers don't have a fixed weekly hour target
        is_management=True,
        enforce_consecutivity=False,    
        works_weekends=True,      
        min_one_weekend_off=False,     
        allowed_shifts=[True,True,True,False],
        holidays=holidays[5]
    )
)

# 4. Consecutivity automaton
max_works = 6
min_breaks = 2
consecutivity_automaton_data = sm.get_consecutivity_automaton_data(min_breaks, max_works)

# 5. Build and Solve the Model
print("Building the model...")
model_data = sm.define_model(
    year=year,
    month=month,
    shifts=shifts,
    workers=workers,
    flexibility=flexibility,
    break_hours= break_hours,
    consecutivity_automaton_data=consecutivity_automaton_data
)

print("Solving the model...")
status, solver = sm.fit_model(model_data, max_minutes)

# 6. Output Results
sm.output_results(status, solver, model_data)