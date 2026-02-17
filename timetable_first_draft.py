from ortools.sat.python import cp_model

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
    [2,3,1]
]
# How many workers are required for each shift?
workers_per_shift = [2,1,1]

num_workers = len(pref)
num_shifts = len(pref[0])
num_days = 31 # hardcoding for the example - should depend on the month selected 


# Creating the variables - Whether worker i is assigned to shift j in the day k
x = {}
for i in range(num_workers):
    for j in range(num_shifts):
        for k in range(num_days):
            x[i,j,k] = model.NewBoolVar(f"x_{i}_{j}_{k}")
# To add: a worker can only work once a day (or, next two shifts should be zero)

# Constraints:
# Each shift is covered every day
for k in range(num_days):
    for j in range(num_shifts):
        model.Add(sum(x[i,j,k] for i in range(num_workers)) == workers_per_shift[j])

# Objective function
objective_terms = []
for i in range(num_workers):
    for j in range(num_shifts):
        objective_terms.append(sum(pref[i][j] * x[i,j,k] for k in range(num_days)))

model.Minimize(sum(objective_terms))

# Solvint the problem
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Outputting results
if status == cp_model.OPTIMAL or status == cp_model.FEASABLE:
    print("total preference score:", solver.ObjectiveValue())
    for k in range(num_days):
        print(f"Day {k}:")
        for j in range(num_shifts):
            for i in range(num_workers):
                if solver.Value(x[i,j,k]) > 0:
                    print(f"Shift {j} assigned to worker {i}, (preference = {pref[i][j]})")