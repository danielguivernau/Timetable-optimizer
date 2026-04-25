from calendar import monthcalendar
import pandas as pd
from ortools.sat.python import cp_model


def monthdata(year: int, month: int):
    """
    Get the date information necessary to fit the model constraints. Number of days and list of day number where monday = 0.

    Keyword arguments:
    year  -- the year to be used
    month -- the month to be used 
    """
    calendar = monthcalendar(year,month)
    days_data = []
    for week in calendar:
        for i, day in enumerate(week):
            if day > 0:
                #days_data.append(1 if i == 5 else 0)
                days_data.append(i)

    return len(days_data),days_data

def determine_num_shifts(weekly_hours: int, year: int, month: int):
    """
    Given the number of hours a worker must work a week, calculates how many shifts they should do on a particular month, rounding down.

    Keyword arguments:
    weekly_hours -- hours they should work per week
    year -- the year to be used
    month -- the month to be used
    """
    num_days, days = monthdata(year,month)
    weeks = num_days / 7
    shifts = (weekly_hours * weeks) // 8 # for now shifts are default 8 hours
    return shifts
 
def define_model(year: int, month:int, preferences: list[list[int]], workers_per_shift: list):
    """
    Defines the MILP model using ortools' cp_model.

    Keyword arguments:
    year -- year to be used
    month -- month to be used
    preferences -- List of list of worker preference for each shift. the lower the better.
    workers_per_shift -- List of how many workers should be assigned to each of the shifts.
    """

    # Input data dimensions must match
    if len(preferences[0]) != len(workers_per_shift):
        raise ValueError(
            f"Data mismatch: 'preferences' indicates {len(preferences[0])} shifts per day, "
            f"but 'workers_per_shift' provides requirements for {len(workers_per_shift)} shifts."
        )
    
    # Initializing model
    model = cp_model.CpModel()

    num_workers = len(preferences)
    num_shifts = len(preferences[0])
    num_days, days_data = monthdata(year,month)
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
            model.AddMaxEquality(work_day[i, d], shifts_this_day) #work_day[i,d] must equal the max value of the list (1 if they work one shift)

        # Whether worker i has the weekend starting on day d (d must be a saturday) fully off
    is_weekend_off = {} 
    for i in range(num_workers):
        for d in range(num_days):
            if days_data[d] == 5 and d + 1 < num_days:
                is_weekend_off[i, d] = model.NewBoolVar(f"off_{i}_{d}")
                
                model.Add(is_weekend_off[i, d] <= 1 - work_day[i, d])
                model.Add(is_weekend_off[i, d] <= 1 - work_day[i, d + 1])
                model.Add(is_weekend_off[i, d] >= 1 - (work_day[i, d] + work_day[i, d + 1]))

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
            model.Add(sum(work_day[i, d + offset] for offset in range(7)) <= 6) # In any 7-day window, they must work 6 days or fewer


        # A worker must have at least one weekend off 
    for i in range(num_workers):
        model.Add(sum(is_weekend_off[i,d] for d in range(num_days) if days_data[d] == 5 and d + 1 < num_days) >= 1)

        # A worker cannot have an isolated day off
    for i in range(num_workers):
        for d in range(1,num_days - 1):
            model.Add(work_day[i,d] >= work_day[i,d-1] + work_day[i,d+1] -1) #If a worker works the day before and the day after, they must work that day

        # Everyone gets to work between 15 and 20 shifts per month
    for i in range(num_workers):
        model.Add(sum(x[i, s] for s in range(num_slots)) >= 15)
        model.Add(sum(x[i, s] for s in range(num_slots)) <= 20)

    # Objective function
    objective_terms = []
    for i in range(num_workers):
        for s in range(num_slots):
            objective_terms.append(preferences[i][s % num_shifts] * x[i,s])

    model.Minimize(sum(objective_terms))

    return {
        "model": model,
        "variables": x,
        "num_workers": num_workers,
        "num_slots": num_slots,
        "num_days": num_days,
        "num_shifts": num_shifts,
        "preferences": preferences
    }

def fit_model(model_data):
    """
    Uses the ortools' solver to fit the model

    keyword_arguments:
    model_data -- dictionary outputted by define_model
    """
    solver = cp_model.CpSolver()
    status = solver.Solve(model_data['model'])    
    return status, solver

def output_results(status,solver,model_data):
    """
    Outputs the solver's result through the console and creates a .csv file with the schedule

    keyword_arguments:
    status -- ortools' status object returned by fit_model
    solver -- ortools' solver object returned by fit_model
    model_data -- dictionary outputted by define_model
    """
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        x = model_data["variables"]
        num_workers = model_data["num_workers"]
        num_slots = model_data["num_slots"]
        num_days = model_data["num_days"]
        num_shifts = model_data["num_shifts"]
        pref = model_data["preferences"]
        
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
        df.to_csv("results")

    else: 
        print("no solution found")
        print(solver)
        print(status)
