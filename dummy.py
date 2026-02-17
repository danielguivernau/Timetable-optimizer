# This python script is me testing the google ortools library and seeing how it can optimize a 2D-variabled function

from ortools.sat.python import cp_model

# Initializing the example 'assignment problem' setup
model = cp_model.CpModel()

# Cost matrix, cost of assigning worker i to post j 
costs = [
    [10,20,30],
    [40,50,60],
    [70,80,95]
]
num_rows = len(costs)
num_cols = len(costs[0])

# Creating the variables - Whether worker i is assigned to post j
x = {}
for i in range(num_rows):
    for j in range(num_cols):
        x[i,j] = model.NewBoolVar(f"x_{i}_{j}")


# Constraints:
# Each worker is assigned to exactly one post
for i in range(num_rows):
    model.Add(sum(x[i,j] for j in range(num_cols)) == 1)
# Each post is assigned to exactly one worker
for j in range(num_cols):
    model.Add(sum(x[i,j] for i in range(num_rows)) == 1)

# Objective function
objective_terms = []
for i in range(num_rows):
    for j in range(num_cols):
        objective_terms.append(costs[i][j] * x[i,j])

model.Minimize(sum(objective_terms))

# Solvint the problem
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Outputting results
if status == cp_model.OPTIMAL or status == cp_model.FEASABLE:
    print("total cost: ", solver.ObjectiveValue())
    for i in range(num_rows):
        for j in range(num_cols):
            if solver.Value(x[i,j]) > 0:
                print(f"Worker {i} assigned to task {j}, incurring cost {costs[i][j]}")
else: 
    print("no solutions found")