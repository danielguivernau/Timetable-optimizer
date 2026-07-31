from calendar import monthcalendar
import pandas as pd
from ortools.sat.python import cp_model
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass(frozen=True)
class Shift:
    name: str
    start: int 
    end: int 
    workers_required: int

    @property
    def length(self) -> int:
        """Returns duration, correctly handling overnight shifts"""
        return (self.end if self.end > self.start else self.end + (24 * 60)) - self.start

    @property
    def end_abs(self) -> int:
        """Returns the end hour on the start day's 24h clock for shift incompatibility calculation"""
        return self.end if self.end > self.start else self.end + (24 * 60)

@dataclass 
class Worker:
    name: str
    preferences: list[int]
    weekly_hours: Optional[int] = None
    is_management: bool = False
    enforce_consecutivity: bool = True
    works_weekends: bool = True
    min_one_weekend_off: bool = True
    allowed_shifts: list[bool] = None #If it is empty, they can work any shift
    holidays: list[int] = None

    def get_target_minutes(self, num_days: int) -> float:
        """Returns the hours this worker should work on a month with num_days days"""
        if self.weekly_hours is not None:
            if self.holidays is not None:
                return self.weekly_hours * 60 * ((num_days-len(self.holidays)) / 7) 
            else:
                return self.weekly_hours * 60 * (num_days / 7) 
        else:
            return None 

    def __post_init__(self):
        """Check that regular workers have weekly hours assigned."""
        if not self.is_management and self.weekly_hours is None:
            raise ValueError(f"Worker '{self.name}' is not management and must have weekly_hours defined.")
    

def monthdata(year: int, month: int) -> Tuple[int, list[int]]:
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

def calculate_shifts_incompatibilities(shifts: list[Shift], break_hours: int):
    """
    Calculates how many shifts a worker should be off after each shift.

    Keyword arguments:
    shifts - vector with all shifts defined, must be sorted by start
    """    
    num_shifts = len(shifts)
    shift_incompatibilities = []
    for i in range(num_shifts):
        dif = 0
        result = 0
        while dif < break_hours:
            current_shift = shifts[(i + result +1)%num_shifts]
            days_passed = (i + result +1)//num_shifts        
            start_hour = current_shift.start / 60

            dif = (start_hour + 24 * days_passed) - (shifts[i].end_abs / 60)
            if dif < break_hours:
                result += 1
            
        shift_incompatibilities.append(result)

    return shift_incompatibilities

def get_consecutivity_automaton_data(min_breaks: int, max_works: int):
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
    shifts: list[Shift],
    workers: list[Worker],
    flexibility: int,
    break_hours: int,
    consecutivity_automaton_data: dict):
    """
    Defines the model using ortools' CP-SAT model.

    Keyword arguments:
    year -- year to be used
    month -- month to be used
    shifts -- defined shifts
    workers -- defined workers
    flexibility -- flexibility in monthly number of longest shifts allowed per worker, increase if there's feasibility issues
    break_hours -- minimum hours all workers should rest after each shift before they can be start another
    consecutivity_automaton_data -- Tuple with needed data to apply to consecutivity constraints
    """

    # Initializing model
    model = cp_model.CpModel()

    num_workers = len(workers)
    num_shifts = len(shifts)
    num_days, days_data = monthdata(year,month)
    num_slots = num_days * num_shifts # flattening shifts and days into one dimensional 'slots' 
    
    incompatibilities = calculate_shifts_incompatibilities(shifts, break_hours)

    # 1. Creating the variables
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
            model.AddMaxEquality(work_day[i, d], [x[i, d * num_shifts + s] for s in range(num_shifts)])

    # Whether worker i has the weekend starting on day d (d must be a saturday) fully off
    is_weekend_off = {} 
    for i in range(num_workers):
        for d in range(num_days):
            if days_data[d] == 5 and d + 1 < num_days:
                is_weekend_off[i, d] = model.NewBoolVar(f"off_{i}_{d}")
                model.Add(is_weekend_off[i, d] <= 1 - work_day[i, d])
                model.Add(is_weekend_off[i, d] <= 1 - work_day[i, d + 1])
                model.Add(is_weekend_off[i, d] >= 1 - (work_day[i, d] + work_day[i, d + 1]))


    # 2. Constraints:

    # Each shift is covered every day
    for s in range(num_slots):
        model.Add(sum(x[i, s] for i in range(num_workers)) == shifts[s % num_shifts].workers_required)

    # Worker constraints
    for i, worker in enumerate(workers):

        # Enforcing break hours after each shift
        for s in range(num_slots):
            num_blocked = incompatibilities[s % num_shifts]
            upper_bound = min(s + num_blocked + 1, num_slots) 
            model.Add(sum(x[i, slot] for slot in range(s, upper_bound)) <= 1)

        # Consecutivity constraints
        if worker.enforce_consecutivity: 
            transitions = consecutivity_automaton_data["transitions"]
            stable_off = consecutivity_automaton_data["stable_off"]
            all_states = consecutivity_automaton_data["all_states"]
            model.AddAutomaton([work_day[i, d] for d in range(num_days)], stable_off, all_states, transitions)

        # At least one weekend off
        if worker.min_one_weekend_off:
            model.Add(sum(is_weekend_off[i,d] for d in range(num_days) if days_data[d] == 5 and d + 1 < num_days) >= 1)
    
        # Check if worker must have all weekends off 
        if not worker.works_weekends:
            for d in range(num_days):
                if days_data[d] >= 5: model.Add(work_day[i, d] == 0)

        # Worker must work their target minutes 
        target_minutes = worker.get_target_minutes(num_days)
        if target_minutes is not None:
            max_shift_len = max(shift.length for shift in shifts) 
            total_minutes = sum(x[i, s] * shifts[s % num_shifts].length for s in range(num_slots))
            model.Add(total_minutes >= int(target_minutes - (flexibility * max_shift_len)))
            model.Add(total_minutes <= int(target_minutes + (flexibility * max_shift_len)))

        # Workers may only be able to work certain shifts 
        if worker.allowed_shifts is not None:
            for shift_idx, is_allowed in enumerate(worker.allowed_shifts):
                if not is_allowed:
                    # If not allowed, the worker cannot work this shift type on ANY day
                    for d in range(num_days):
                        model.Add(x[i, d * num_shifts + shift_idx] == 0)
                
        # Worker can't work on holidays
        if worker.holidays is not None:
            for hol_ind in worker.holidays:
                model.Add(work_day[i, hol_ind-1] == 0)

    # Objective function
    objective_terms = [x[i, s] * worker.preferences[s % num_shifts] for i, worker in enumerate(workers) for s in range(num_slots)]
    model.Minimize(sum(objective_terms))

    return {
        "model": model,
        "variables": x,
        "num_workers": num_workers,
        "num_slots": num_slots,
        "num_days": num_days,
        "days_data": days_data,
        "num_shifts": num_shifts,
        "workers": workers,
        "shifts": shifts,
        "flexibility": flexibility,
    }

def fit_model(model_data, max_fitting_minutes: int|None = None):
    """
    Uses the ortools' solver to fit the model

    keyword_arguments:
    model_data -- dictionary outputted by define_model
    max_fitting_minutes -- maximum minutes the solver can take to generate the timetable
    """
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.relative_gap_limit = 0.15 # Stop if the solution is within 15% of the theoretical best
    if max_fitting_minutes is not None:
        solver.parameters.max_time_in_seconds = max_fitting_minutes * 60 # User time limit
    status = solver.Solve(model_data['model'])    
    return status, solver

def print_feasibility_analysis(model_data): #TRANSITION TO MINUTES NOT DONE YET
    """
    Calculates and prints a comparison between required shift time and available staff capacity.
    Includes checks for both hour deficits (too few staff) and hour surpluses (too many staff).

    Keyword arguments:
    model_data -- dictionary outputted by define_model
    """
    num_days = model_data["num_days"]
    days_data = model_data["days_data"]
    workers = model_data["workers"]
    shifts = model_data["shifts"]
    flexibility = model_data["flexibility"] 

    # 1. Calculate total exact hours of work needed
    daily_required_hours = sum(shift.workers_required * shift.length for shift in shifts) / 60
    total_hours_to_cover = daily_required_hours * num_days

    # 2. Calculate floor and ceiling for worker hours
    max_shift_len = max(shift.length for shift in shifts) / 60
    
    total_min_staff_supply = 0
    total_max_staff_supply = 0
    management_max_capacity = 0

    for worker in workers:
        target_minutes = worker.get_target_minutes(num_days)
        
        # If they have a target (Regular workers)
        if target_minutes is not None:
            target_hours = target_minutes / 60
            total_min_staff_supply += max(0, target_hours - (flexibility * max_shift_len))
            total_max_staff_supply += target_hours + (flexibility * max_shift_len)
            
        # If they DON'T have a target (Management)
        else:
            available_days = num_days if worker.works_weekends else sum(1 for d in days_data if d < 5)
            # Find the longest shift they are allowed to work
            if worker.allowed_shifts is not None:
                allowed_lengths = [shifts[i].length / 60 for i, is_allowed in enumerate(worker.allowed_shifts) if is_allowed]
            else:
                allowed_lengths = [s.length / 60 for s in shifts]
            # Maximum capacity of management    
            management_max_capacity += available_days * max(allowed_lengths)

    print("--- Feasibility Analysis ---")
    print(f"Total hours required to cover shifts: {total_hours_to_cover:.2f}")
    print(f"Minimum hours staff must work (Floor): {total_min_staff_supply:.2f}")
    print(f"Maximum hours staff can work (Ceiling): {total_max_staff_supply:.2f}")
    print(f"Management max potential capacity:     {management_max_capacity:.2f}")
    
    # Check for Deficit
    if (total_max_staff_supply + management_max_capacity) < total_hours_to_cover:
        shortfall = total_hours_to_cover - (total_max_staff_supply + management_max_capacity)
        print(f"Infeasible due to DEFICIT. Shortfall of {shortfall:.2f} hours. Need more workers.")
    
    # Check for Surplus
    elif total_min_staff_supply > total_hours_to_cover:
        surplus = total_min_staff_supply - total_hours_to_cover
        print(f"Infeasible due to SURPLUS. Staff are forced to work {surplus:.2f} hours more than shifts available.")
        print("Note: Decrease num_workers or lower the weekly_hours target.")
        
    else:
        print("Model should be mathematically feasible.")
        slack = (total_max_staff_supply + management_max_capacity) - total_hours_to_cover
        print(f"Current hour slack: {slack:.2f} hours.")
        print("Try relaxing the conditions or increasing the flexibility parameter if solver fails.")
    print("----------------------------\n")

def output_results(status,solver,model_data):
    """
    Outputs the solver's result through the console and creates a .csv file with the schedule

    keyword_arguments:
    status -- ortools' status object returned by fit_model
    solver -- ortools' solver object returned by fit_model
    model_data -- dictionary outputted by define_model
    """
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        x = model_data["variables"]
        workers = model_data["workers"]
        shifts = model_data["shifts"]
        num_days = model_data["num_days"]
        days_data = model_data["days_data"]
        num_shifts = model_data["num_shifts"]
        num_slots = model_data["num_slots"]
        
        print(f"Model adjusted: {solver.StatusName(status)}")
        print(f"Total preference score: {solver.ObjectiveValue()}\n")

        # 1. Shifts and preference score per worker
        for i, worker in enumerate(workers):
            total_shifts = sum(solver.Value(x[i, s]) for s in range(num_slots))
            total_hours = sum(solver.Value(x[i, s]) * shifts[s % num_shifts].length for s in range(num_slots)) / 60
            total_preference = sum(solver.Value(x[i, s]) * worker.preferences[s % num_shifts] for s in range(num_slots))
            
            if worker.is_management:
                print(f"{worker.name} (Mgmt) - Shifts: {total_shifts}, Hours: {total_hours}, Score: {total_preference}")
            else: 
                target_hours = worker.get_target_minutes(num_days) / 60
                holidays = worker.holidays
                print(f"{worker.name} - Shifts: {total_shifts}, Hours: {total_hours}, Target: {target_hours:.1f}, Score: {total_preference}, Days on holidays: {len(holidays) if holidays is not None else 0}")
        print("\n")

        # 2. Creating and filling grid layout for final timetable
        # Using 'F' for free/off days as in your original code
        timetable = [['F' for _ in range(num_days)] for _ in range(len(workers))]
        
        for s in range(num_slots):
            day = s // num_shifts
            shift_type = s % num_shifts
            for i in range(len(workers)):
                if solver.Value(x[i, s]) > 0:
                    # Using the actual Shift Name instead of an index number for better readability
                    timetable[i][day] = shifts[shift_type].name 

        for i, worker in enumerate(workers): 
            if worker.holidays is not None:
                for d in worker.holidays:
                    timetable[i][d-1] = "H" 

        # 3. Put it in a pandas dataframe
        column_names = [f"Day {d+1} (Weekend)" if days_data[d] >= 5 else f"Day {d+1}" for d in range(num_days)]
        index_names = [worker.name for worker in workers]
        
        df = pd.DataFrame(timetable, columns=column_names, index=index_names)
        print(df)
        df.to_csv("results.csv")

    else: 
        print("No solution found.")
        print_feasibility_analysis(model_data)
    
        
    

