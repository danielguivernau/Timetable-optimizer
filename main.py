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
    sm.Shift(name="Evening", start=15, end=23, workers_required=1),
    sm.Shift(name="Night",     start=23, end=7,  workers_required=1)
]
shifts = sorted(shifts, key= lambda s : s.start)
break_hours = 12

# 3. Define Workers
preferences = [
    [1, 3, 4],
    [4, 2, 1],
    [4, 3, 1],
    [5, 3, 4],
    [20, 20, 20] # Management preferences
]
weekly_hours = [40, 40, 40, 40]

workers = []

# Add the regular workers
for i in range(len(preferences) -1):
    workers.append(
        sm.Worker(
            name=f"Worker {i+1}", 
            preferences=preferences[i], 
            weekly_hours=weekly_hours[i]
        )
    )

# Add the Management Worker
workers.append(
    sm.Worker(
        name="Management",
        preferences=preferences[3],
        weekly_hours=None,          # Managers don't have a fixed weekly hour target
        is_management=True,
        enforce_consecutivity=False,    # management_applicability = True
        works_weekends=False,        # management_weekends = True
        min_one_weekend_off=False,     # Give them a weekend off too!
        allowed_shifts=[True,True,False]
    )
)

# 4. Consecutivity automaton
max_works = 6
min_breaks = 2
automaton_data = sm.get_automaton_data(min_breaks, max_works)

# 5. Build and Solve the Model
print("Building the model...")
model_data = sm.define_model(
    year=year,
    month=month,
    shifts=shifts,
    workers=workers,
    flexibility=flexibility,
    break_hours= break_hours,
    automaton_data=automaton_data
)

print("Solving the model...")
status, solver = sm.fit_model(model_data, max_minutes)

# 6. Output Results
sm.output_results(status, solver, model_data)