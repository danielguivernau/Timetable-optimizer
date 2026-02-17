from scipy import optimize
import numpy as np


# Running the sample problem on scipy.optimize documentation
sizes = np.array([21,11,15,9,34,25,41,52])
values = np.array([22,12,16,10,35,26,42,53])

bounds = optimize.Bounds(0,2)
integrality = np.full_like(values, True)

capacity = 100
constraints = optimize.LinearConstraint(A=sizes, lb=0, ub=capacity)

res = optimize.milp(c=-values, constraints = constraints,
                    integrality = integrality, bounds=bounds)


print(res)