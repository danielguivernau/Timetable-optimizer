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

def get_automaton_data(min_breaks: int, max_works: int):
    """
    Returns needed data in order to enforce the minimum consecutive break days and the maximum consecutive work days restrictions.

    Keyword_arguments:
    min_breaks -- minimum consecutive break days 
    max_works -- maximum consecutive work days 
    """
    
    h, k = max_works, min_breaks
    # 0 to (h-1): Working states. State 'i' means the worker has worked i+1 consecutive days.
    # h to (h + k - 2): Mandatory break corridor. Worker is trapped here until min_breaks is satisfied.
    # (h + k - 1): Stable Off state. Minimum break days have been consecutively fullfilled and now the worker can stay off or wo back to work

    transitions = []
    # working states (0 to h-1)
    for i in range(h):
        if i < h - 1:
            transitions.append((i, 1, i + 1)) # Can continue working
        transitions.append((i, 0, h)) # Can go on break

    # break corridor (h to h + k - 2)
    for i in range(h, h + k - 1):
        next_state = i + 1
        transitions.append((i, 0, next_state)) # Can stay on break

    # stable off state (h + k - 1)
    stable_off = h + k - 1
    transitions.append((stable_off, 0, stable_off))  # Can stay on break indefinitely
    transitions.append((stable_off, 1, 0))           # Can return to Work (State 0)

    return {
    "transitions": transitions,
    "stable_off": stable_off,
    "all_states": list(range(stable_off + 1))
    }

def define_model(
    year: int,
    month:int, 
    preferences: list[list[int]], 
    workers_per_shift: list, 
    weekly_hours: list[int],
    flexibility: int,
    shift_lengths: list[int],
    shift_incompatibilities: list[int],
    automaton_data: dict,
    management_shift_availability: list[int]|None = None,
    management_weekends: bool|None = None,
    management_applicability: bool|None = None):
    """
    Defines the model using ortools' CP-SAT model.

    Keyword arguments:
    year -- year to be used
    month -- month to be used
    preferences -- list of list of worker preference for each shift. the lower the better.
    workers_per_shift -- list of how many workers should be assigned to each of the shifts.
    weekly_hours -- weekly hours each worker should fullfill 
    flexibility -- flexibility in monthly number of longest shifts allowed per worker, increase if there's feasibility issues
    shift_lengths -- how long each shift is
    shift_incompatibilities -- how many shifts after each shift one isn't allowed to work
    max_works -- maximum number of days a worker can work consecutively 
    min_breaks -- minimum number of days a worker must have off consecutively
    management_shift_availability -- if available, binary list to indicate what shifts management can cover
    management_weekends -- if available, management can work weekends
    management_applicability -- if available, whether the consecutive break and work days restrictions apply to management
    """

    # Initializing model
    model = cp_model.CpModel()

    num_workers = len(preferences)
    num_shifts = len(preferences[0])
    num_days, days_data = monthdata(year,month)
    num_slots = num_days * num_shifts # flattening shifts and days into one dimensional 'slots' 
    management = int(management_shift_availability is not None) 
    management_applicability = int(management_applicability == True)

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

        # Workers can work at most max_works consecutively, and must go on break for at least min_breaks consecutively
    transitions = automaton_data["transitions"]
    stable_off = automaton_data["stable_off"]
    all_states = automaton_data["all_states"]
    
    for i in range(num_workers - management + management_applicability):
        # Starting in stable_off assumes they are ready to work on Day 1.
        timeline = [work_day[i, d] for d in range(num_days)]
        model.AddAutomaton(timeline, stable_off, all_states, transitions)

        # A worker must have at least one weekend off
    for i in range(num_workers - management + management_applicability):
        model.Add(sum(is_weekend_off[i,d] for d in range(num_days) if days_data[d] == 5 and d + 1 < num_days) >= 1)
    
        # Check if management must have all weekends off
    if management_weekends == False:
        model.Add(sum(work_day[num_workers-1,d] for d in range(num_days) if days_data[d] >= 5) == 0)

    weeks = num_days / 7
    hours_to_work = [int(i * weeks) for i in weekly_hours]

        # A worker has to work their assigned hours
    for i in range(num_workers - management):
        model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) >= hours_to_work[i] - flexibility * max(shift_lengths))
        model.Add(sum(x[i, s] * shift_lengths[s % num_shifts] for s in range(num_slots)) <= hours_to_work[i] + flexibility * max(shift_lengths))        

        # If management is available, they can only work on certain shifts
    if management == 1:
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
        "hours_to_work": hours_to_work,
        "flexibility": flexibility,
        "management_weekends": management_weekends
    }

def fit_model(model_data, max_minutes: int|None = None):
    """
    Uses the ortools' solver to fit the model

    keyword_arguments:
    model_data -- dictionary outputted by define_model
    max_minutes -- maximum minutes the solver can take to generate the timetable
    """
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.relative_gap_limit = 0.15 # Stop if the solution is within 15% of the theoretical best
    if max_minutes is not None:
        solver.parameters.max_time_in_seconds = max_minutes * 60 # Stop at 3 minutes of solver time
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
    num_shifts = model_data["num_shifts"]
    shift_lengths = model_data["shift_lengths"]
    hours_to_work = model_data["hours_to_work"]
    flexibility = model_data["flexibility"]
    management_shift_availability = model_data["management_shift_availability"]
    management_weekends = model_data["management_weekends"]

    # Calculate total exact hours of work needed
    daily_required_hours = sum(workers_per_shift[s] * shift_lengths[s] for s in range(num_shifts))
    total_hours_to_cover = daily_required_hours * num_days

    # Calculate floor and ceiling for worker hours
    max_shift = max(shift_lengths)    
    regular_worker_count = num_workers - int(management_shift_availability is not None)
        
    min_hours_per_worker = [i - (flexibility * max_shift) for i in hours_to_work]
    max_hours_per_worker = [i + (flexibility * max_shift) for i in hours_to_work]

    total_min_staff_supply = sum(min_hours_per_worker)
    total_max_staff_supply = sum(max_hours_per_worker)

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
        print(f"Infeasible due to DEFICIT. Shortfall of {shortfall:.2f} hours. Need more workers.")
    
    # Check for Surplus (Too many workers forced to work more hours than exist)
    elif total_min_staff_supply > total_hours_to_cover:
        surplus = total_min_staff_supply - total_hours_to_cover
        print(f"Infeasible due to SURPLUS. Staff are forced to work {surplus:.2f} hours more than shifts available.")
        print("Note: Decrease num_workers or lower the weekly_hours target.")
        
    else:
        print("Model should be mathematically feasible.")
        print(f"Current hour slack: {(total_max_staff_supply + management_max_capacity) - total_hours_to_cover:.2f} hours.")
        print("Try relaxing the conditions or increasing the flexibility parameter")
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
        days_data = model_data["days_data"]
        num_shifts = model_data["num_shifts"]
        workers_per_shift = model_data["workers_per_shift"]
        shift_lengths = model_data["shift_lengths"]
        pref = model_data["preferences"]
        manag = model_data["management_shift_availability"]
        hours_to_work = model_data["hours_to_work"]
        
        print("Model adjusted : ", status)
        print("total preference score:", solver.ObjectiveValue())

        # Shifts and preference score per worker
        for i in range(
            num_workers):
            total_shifts = sum(solver.Value(x[i, s]) for s in range(num_slots))
            total_preference = sum(solver.Value(x[i, s]) * pref[i][s % num_shifts] for s in range(num_slots))
            total_hours = sum(solver.Value(x[i, s]) * shift_lengths[s % num_shifts] for s in range(num_slots))

            if manag is not None and i == num_workers - 1:
                print(f"Management total shifts: {total_shifts}, total hours: {total_hours},  total score: {total_preference}")
            else: 
                print(f"Worker {i+1} total shifts: {total_shifts}, total hours: {total_hours}, target hours: {hours_to_work[i]}, total score: {total_preference}")
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
        column_names = [f"Day {d+1} (Weekend)" if days_data[d] >= 5 else f"Day {d+1}" for d in range(num_days)]
        if manag is not None:
            index_names = [f"Worker {i+1}" for i in range(num_workers -1)] + ["Management"]
        else:
            index_names = [f"Worker {i+1}" for i in range(num_workers)]
        df = pd.DataFrame(timetable, columns=column_names, index=index_names)
        print(df)
        df.to_csv("results.csv")

    else: 
        print("No solution found")
        print_feasibility_analysis(model_data)
    
        
    

