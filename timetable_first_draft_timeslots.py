from ortools.sat.python import cp_model
import pandas as pd

# Initializing the example 'assignment problem' setup
model = cp_model.CpModel()

# Worker preference metric, each worker(row), ranks the shifts(column)
# from 1 to nrows, 1 being prefered shift.
pref = [
    [1,2,3],
    [2,1,3],
    [3,2,1],
    [2,1,3],
    [1,2,3],
    [2,3,1],
    [3,2,1]
]
# How many workers are required for each shift?
workers_per_shift = [2,1,1]

num_workers = len(pref)
num_shifts = len(pref[0])
num_days = 31 # hardcoding for the example - should depend on the month selected 
num_slots = num_days * num_shifts # flattening shifts and days into one dimensional 'slots' 

# Creating the variables
    # Whether worker i is assigned to the slot s
x = {}
for i in range(num_workers):
    for s in range(num_slots):
        x[i, s] = model.NewBoolVar(f"x_{i}_{s}")

    # Whether worker i works on day d
work_day = {}
for i in range(num_workers):
    for d in range(num_days):
        work_day[i, d] = model.NewBoolVar(f"work_day_{i}_{d}")
    
        shifts_this_day = [x[i, d * num_shifts + s] for s in range(num_shifts)]
        model.AddMaxEquality(work_day[i, d], shifts_this_day)


# Constraints:
    # Each shift is covered every day
for s in range(num_slots):
    model.Add(sum(x[i, s] for i in range(num_workers)) == workers_per_shift[s % num_shifts])

    # A worker cannot start a shift at least 12 hours (2 shifts) after the last one they did
for i in range(num_workers):
    for s in range(num_slots - 2):
        model.Add(sum(x[i, s + offset] for offset in [0, 1, 2]) <= 1)

    # A worker cannot work for more than 7 days straight 
for i in range(num_workers):
    for d in range(num_days - 6):
        # In any 7-day window, they must work 6 days or fewer
        model.Add(sum(work_day[i, d + offset] for offset in range(7)) <= 6)

    # Everyone gets to work between 15 and 20 shifts per month
for i in range(num_workers):
    model.Add(sum(x[i, s] for s in range(num_slots)) >= 15)
    model.Add(sum(x[i, s] for s in range(num_slots)) <= 20)

# Objective function
objective_terms = []
for i in range(num_workers):
    for s in range(num_slots):
        objective_terms.append(pref[i][s % num_shifts] * x[i,s])

model.Minimize(sum(objective_terms))

# Solvint the problem
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Outputting results
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("total preference score:", solver.ObjectiveValue())

    # Shifts and preference score per worker
    for i in range(num_workers):
        total_shifts = sum(solver.Value(x[i, s]) for s in range(num_slots))
        total_preference = sum(solver.Value(x[i, s]) * pref[i][s % num_shifts] for s in range(num_slots))
        print(f"Worker {i+1} total shifts: {total_shifts}, total score: {total_preference}")
    print("\n")

    # Creating and filling grid layout for final timetable
    timetable = [['F' for _ in range(num_days)] for _ in range(num_workers)]
    for s in range(num_slots):
        day = s // num_shifts
        shift_type = s % num_shifts
        for i in range(num_workers):
            if solver.Value(x[i, s]) > 0:
                timetable[i][day] = str(shift_type + 1) # +1 for human readability

    # Put it in a pandas dataframe
    column_names = [f"Day {d+1}" for d in range(num_days)]
    index_names = [f"Worker {i+1}" for i in range(num_workers)]
    df = pd.DataFrame(timetable, columns=column_names, index=index_names)
    print(df)

else: 
    print("no solution found")
    print(solver)
    print(status)