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

def calculate_shifts_lengths(shift_hours: list[list[int]]):
    
    shift_lengths = []
    for i in shift_hours: shift_lengths.append(i[1] - i[0])
    
    return shift_lengths

def calculate_shifts_incompatibilities(shift_hours: list[list[int]], break_hours: int):
    """
    Calculates how many shifts a worker should be off after each shift.

    Keyword arguments:
    shift_hours -- List of 2-element lists with the start and end hours of each shift, both expressed using the first day's clock
    break_hours -- how many hours a worker must be off after a shift
    """    
    num_shifts = len(shift_hours)
    shift_incompatibilities = []
    for i in range(num_shifts):
        dif = 0
        result = 0
        end_hour = shift_hours[i][1]
        while dif < break_hours:
            current_shift = (i + result +1)%num_shifts
            days_passed = (i + result +1)//num_shifts
            start_hour = shift_hours[current_shift][0]

            dif = (start_hour + 24 * days_passed) - end_hour
            if dif < break_hours:
                result += 1
            
        shift_incompatibilities.append(result)

    return shift_incompatibilities
 
def define_model(
    year: int,
    month:int, 
    preferences: list[list[int]], 
    workers_per_shift: list, 
    weekly_hours: int,
    shift_lengths: list[int],
    shift_incompatibilities: list[int],
    management_shift_availability: list[int]|None = None,
    management_weekends: bool|None = None):
    """
    Defines the model using ortools' CP-SAT model.

    Keyword arguments:
    year -- year to be used
    month -- month to be used
    preferences -- list of list of worker preference for each shift. the lower the better.
    workers_per_shift -- list of how many workers should be assigned to each of the shifts.
    shift_lengths -- how long each shift is
    shift_incompatibilities -- how many shifts after each shift one isn't allowed to work
    management_shift_availability -- if available, binary list to indicate what shifts management can cover
    management_weekends -- if management can work weekends
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
    weeks = num_days / 7
    hours_to_work = int(weekly_hours * weeks)

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
        for s in range(num_slots):
            num_blocked = shift_incompatibilities[s % num_shifts]
            upper_bound = min(s + num_blocked + 1, num_slots) 
            model.Add(sum(x[i, slot] for slot in range(s, upper_bound)) <= 1)

        # A worker cannot work for more than 7 days straight 
    for i in range(num_workers):
        for d in range(num_days - 6):
            model.Add(sum(work_day[i, d + offset] for offset in range(7)) <= 6) # In any 7-day window, they must work 6 days or fewer

        # A worker must have at least one weekend off
    for i in range(num_workers):
        model.Add(sum(is_weekend_off[i,d] for d in range(num_days) if days_data[d] == 5 and d + 1 < num_days) >= 1)
    
        # Check if management must have all weekends off
    if management_weekends == False:
        model.Add(sum(work_day[num_workers-1,d] for d in range(num_days) if days_data[d] >= 5) == 0)

        # A worker cannot have an isolated day off - but management can
    management = int(management_shift_availability is not None) 
    for i in range(num_workers - management):
        for d in range(1,num_days - 1):
            model.Add(work_day[i,d] >= work_day[i,d-1] + work_day[i,d+1] -1) #If a worker works the day before and the day after, they must work that day

        # A worker has to work their assigned hours - two forms depending on wether management is available
    if management_shift_availability is not None:
        for i in range(num_workers - 1):
            #model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) == hours_to_work) #Exact hours
            model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) >= hours_to_work - 1 * max(shift_lengths))
            model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) <= hours_to_work + 1 * max(shift_lengths))        
    else: 
        for i in range(num_workers):
            model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) >= hours_to_work - 2 * max(shift_lengths))
            model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) <= hours_to_work + 2 * max(shift_lengths))

        # if management is available, they can only work on certain shifts
    if management_shift_availability is not None:
        model.Add(sum(x[num_workers - 1,s] for s in range(num_slots) if management_shift_availability[s % num_shifts] == 0) == 0)
        

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
        "days_data": days_data,
        "num_shifts": num_shifts,
        "workers_per_shift": workers_per_shift,
        "preferences": preferences,
        "management_shift_availability": management_shift_availability,
        "shift_lengths": shift_lengths,
        "weekly_hours": weekly_hours,
        "management_weekends": management_weekends
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

def print_feasibility_analysis(model_data):
    """
    Calculates and prints a comparison between required shift hours and available staff capacity.
    Includes checks for both hour deficits (too few staff) and hour surpluses (too many staff).

    Keyword arguments:
    model_data -- dictionary outputted by define_model
    """
    num_days = model_data["num_days"]
    days_data = model_data["days_data"]
    num_workers = model_data["num_workers"]
    workers_per_shift = model_data["workers_per_shift"]
    shift_lengths = model_data["shift_lengths"]
    weekly_hours = model_data["weekly_hours"]
    management_shift_availability = model_data["management_shift_availability"]
    management_weekends = model_data["management_weekends"]

    # Calculate total exact hours required to cover all shifts across the month
    daily_required_hours = sum(workers_per_shift[s] * shift_lengths[s] for s in range(len(workers_per_shift)))
    total_hours_to_cover = daily_required_hours * num_days

    # Calculate the worker hour target based on weeks in the month
    actual_weeks = num_days / 7
    hours_to_work = int(weekly_hours * actual_weeks)
    max_shift = max(shift_lengths)
    
    if management_shift_availability is not None:
        regular_worker_count = num_workers - 1
        # Range is +/- 1 * max_shift
        min_hours_per_worker = hours_to_work - (1 * max_shift)
        max_hours_per_worker = hours_to_work + (1 * max_shift)
    else:
        regular_worker_count = num_workers
        # Range is +/- 2 * max_shift
        min_hours_per_worker = hours_to_work - (2 * max_shift)
        max_hours_per_worker = hours_to_work + (2 * max_shift)

    # Total floor and ceiling for regular staff
    total_min_staff_supply = regular_worker_count * min_hours_per_worker
    total_max_staff_supply = regular_worker_count * max_hours_per_worker

    # Calculate management capacity
    management_max_capacity = 0
    if management_shift_availability is not None:
        if management_weekends == True:
            management_available_days = num_days
        else:
            management_available_days = sum(1 for day_type in days_data if day_type < 5)

        allowed_shift_lengths = [shift_lengths[s] for s, avail in enumerate(management_shift_availability) if avail == 1]
        if len(allowed_shift_lengths) > 0:
            management_max_capacity = management_available_days * max(allowed_shift_lengths)

    print("--- Feasibility Analysis ---")
    print(f"Total hours required to cover shifts: {total_hours_to_cover:.2f}")
    print(f"Minimum hours staff must work (Floor): {total_min_staff_supply:.2f}")
    print(f"Maximum hours staff can work (Ceiling): {total_max_staff_supply:.2f}")
    print(f"Management maximum capacity:           {management_max_capacity:.2f}")
    
    # Check for Deficit (Not enough hours available to cover shifts)
    if (total_max_staff_supply + management_max_capacity) < total_hours_to_cover:
        shortfall = total_hours_to_cover - (total_max_staff_supply + management_max_capacity)
        print(f"Status: Infeasible (DEFICIT). Shortfall of {shortfall:.2f} hours. Need more workers.")
    
    # Check for Surplus (Too many workers forced to work more hours than exist)
    elif total_min_staff_supply > total_hours_to_cover:
        surplus = total_min_staff_supply - total_hours_to_cover
        print(f"Status: Infeasible (SURPLUS). Staff are forced to work {surplus:.2f} hours more than shifts available.")
        print("Note: Decrease num_workers or lower the weekly_hours target.")
        
    else:
        print("Status: Mathematically feasible.")
        print(f"Current hour slack: {(total_max_staff_supply + management_max_capacity) - total_hours_to_cover:.2f} hours.")
    print("----------------------------\n")

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
        workers_per_shift = model_data["workers_per_shift"]
        pref = model_data["preferences"]
        manag = model_data["management_shift_availability"]
        
        print("Model adjusted : ", status)
        print("total preference score:", solver.ObjectiveValue())

        # Shifts and preference score per worker
        for i in range(num_workers):
            total_shifts = sum(solver.Value(x[i, s]) for s in range(num_slots))
            total_preference = sum(solver.Value(x[i, s]) * pref[i][s % num_shifts] for s in range(num_slots))
            if manag is not None and i == num_workers - 1:
                print(f"Management total shifts: {total_shifts}, total score: {total_preference}")
            else: 
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
        if manag is not None:
            index_names = [f"Worker {i+1}" for i in range(num_workers -1)] + ["Management"]
        else:
            index_names = [f"Worker {i+1}" for i in range(num_workers)]
        df = pd.DataFrame(timetable, columns=column_names, index=index_names)
        print(df)
        df.to_csv("results")

    else: 
        print("No solution found")
    
    print_feasibility_analysis(model_data)
        
    

