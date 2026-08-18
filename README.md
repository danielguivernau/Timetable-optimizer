
My girlfriend works in a hotel whose reception has workers present around the clock. This means that each month, their management has to put together a schedule to cover all the shifts, taking into account both labour regulations and each worker's preferences. 

Wanting to get back in touch with Operations Research and improve my programming skills, and knowing that scheduling is a classic optimization problem, I wanted to try and create a piece of software that could create these schedules.

I have included some particularities that might only apply to hotels (or perhaps only my girlfriend's), but they are included as optional parameters that can otherwise be ignored.

# How to use it

You may run the app through its streamlit interface (which is defined in `app.py`) by clicking on this [link](https://danis-timetable-optimizer.streamlit.app/). Otherwise, you can load this repository on your computer and run `main.py` after including your own data there.

# How it works

## Backend: *scheduler_model.py*
The program is centered around two dataclasses, which I have made as flexible as possible so that they can be adapted to the particular characteristics of each user. Then, these are combined with some general parameters and the optimization problem is defined and solved.

Let's look at the dataclasses first.

### The `Shift` Dataclass

Represents a defined work block. Time parameters and calculations are handled strictly as integers (representing minutes from midnight) to comply with the requirements of the solver used.

| Parameter / Property | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique identifier for the shift type. |
| `start` | `int` | Shift start time expressed in minutes from midnight (e.g., `1410` for 23:30). |
| `end` | `int` | Shift end time expressed in minutes from midnight (e.g., `450` for 07:30) |
| `workers_required` | `int` | The number of staff members needed for this shift. |
| `@property length` | `int` | **Computed:** Total duration of the shift in minutes, correctly overnight shifts |
| `@property end_abs` | `int` | **Computed:** The absolute end time on a continuous 24h+ clock, used for calculating shift incompatibility. |

All shifts are then passed in a list sorted by start (ascending) to the model definition function, `define_model()`

### The `Worker` Dataclass

Represents an individual staff member, their role, contract characteristics, labor law constraints, and shift preferences.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | The employee's full name or unique identifier. |
| `preferences` | `list[int]` | A list of integer scores ranking the preference for each shift (ordered by `start_time`). It is used in the model's objective function to minimize unfavorable schedules. |
| `weekly_hours` | `Optional[int]` | How many weekly hours the worker has to do. |
| `is_management` | `bool` | A flag indicating a management role. It exempts the worker from the mandatory `weekly_hours` requirement and operates without a strict monthly hours target. |
| `works_weekends` | `bool` | If `False`, the worker is restricted from working on weekends. |
| `min_one_weekend_off` | `bool` | If `True`, ensures the worker has at least one completely free weekend (no shifts assigned) during the scheduling period. |
| `allowed_shifts` | `list[bool]` | A boolean list of whether the worker can be assigned each shift (ordered by `start_time`). If an index is `False`, the solver prohibits assigning that specific shift type to the worker. |
| `holidays` | `list[int]` | A list of specific days (integers) the worker has off. It prevents shifts on those days, displays them as "H" on the timetable, and prorates the required working hours for the month. |
| `break_hours` | `Optional[int]` | How many hours the worker must be off before they can clock in again. If empty, 0 break hours are enforced |
| `max_consec_works` | `Optional[int]` | Maximum number of consecutive days the worker can work. If empty, no limit is enforced. If included, `min_consec_breaks` must also be included.|
| `min_consec_breaks` | `Optional[int]` | Minimum number of consecutive break days the worker must have every time they go on break. If empty, no limit is enforced. If included, `max_consec_works` must also be included.|


### Global Configuration Parameters

Alongside the structural entities, the execution environment requires several global parameters to construct the calendar horizon, configure labor bounds, and manage solver constraints.

| Parameter | Type | Description | 
| :--- | :--- | :--- | 
| `year` | `int` | The calendar year for the target schedule. Used by `monthdata()` to correctly align days and weekend indexes. | 
| `month` | `int` | The calendar month for the target schedule. Used by `monthdata()` to correctly align days and weekend indexes.| 
| `flexibility` | `int` | A buffer scaling factor used to relax monthly target hour limits. Multiplied by the longest shift length to establish an acceptable range, preventing solver crashes due to minor mathematical tight-spots. | 
| `max_fitting_minutes` | `int` | The strict time limit (in minutes) assigned to the CP-SAT solver. The engine will return the best feasible solution found within this window if an optimal one isn't reached. |

### Data Pre-processing Functions
Before these parameters hit the CP-SAT constraint engine, they are parsed by three foundational pre-processing scripts:
*   **`monthdata(year, month)`:** Uses Python's calendar utilities to generate the month's duration and maps days to weekday integer coordinates (where Monday = 0, Sunday = 6).
*   **`calculate_shifts_incompatibilities(list[Shift], Worker.break_hours)`:** Dynamically translates the raw `break_hours` requirement into an absolute minute matrix, defining exactly how many subsequent shift slots must be locked out after a specific assignment.
*   **`get_consecutivity_automaton_data(Worker.min_consec_breaks, Worker.max_consec_works)`:** Takes the consecutive limits and maps them into a structural **Finite State Automaton**. This creates an explicit layout of valid worker paths (working states, a mandatory break corridor, and stable rest states) that the solver enforces via a sequence tracking constraint.

### The Optimization Model (CP-SAT)

Given the data described above, the program relies on Google OR-Tools' Constraint Programming solver (`cp_model.CpModel`) to build and solve the scheduling problem. The model formulation is divided into variables, constraints, an objective function, and the solver parameters.

#### 1. Variables
The engine tracks the schedule using a multidimensional matrix of boolean variables generated via `model.NewBoolVar()`:
*   **Shift assignments (`x[i, s]`):** A boolean determining whether worker `i` is assigned to a specific shift slot `s`. 
*   **Daily attendance (`work_day[i, d]`):** A boolean tracking if a worker is scheduled for *any* shift on calendar day `d`. This is linked to the shift assignments using `model.AddMaxEquality()`.
*   **Weekend tracking (`is_weekend_off[i, d]`):** A boolean tracking whether a worker has a fully free weekend, contingent on neither Saturday nor Sunday having active `work_day` assignments.

#### 2. Constraints
To ensure the schedule respects the contractual obligations of all workers and fulfills all the shifts' needs, the script translates our rules into strict mathematical boundaries using `model.Add()`:
*   **Strict coverage:** The sum of workers assigned to any given shift slot must exactly equal its `workers_required` parameter.
*   **Single daily shift:** The sum of shifts assigned to a single worker on any given calendar day must be less than or equal to 1. This condition will generally be made redundant by a normal `Worker.break_hours` parameter.
*   **Mandatory rest:** Using the calculated incompatibilities matrix, the model limits the sum of assigned shifts within a worker's `break_hours` window to a maximum of 1.
*   **Consecutivity automaton:** If consecutive rules are defined, the program uses CP-SAT's specialized `model.AddAutomaton()` constraint. This forces the worker's schedule to follow the valid state transitions (working days, break corridors, and stable rest) mapped during pre-processing.
*   **Target hours:** The total length of all shifts assigned to a standard worker is bounded between a minimum and maximum minute threshold. This threshold is centered on their `weekly_hours` target and padded by the `flexibility` parameter.
*   **Absences & permissions:** If a shift type is restricted in a worker's `allowed_shifts`, scheduled on a worker's `holidays`, or falls on a weekend for a worker with `works_weekends == False`, the model hardcodes that specific assignment variable to 0.

#### 3. Objective function
We use an objective function defined through `model.Minimize()`:
*   **Preference scoring:** Every potential shift assignment is multiplied by the worker's `preferences` rating for that shift. The solver actively seeks a timetable that results in the lowest possible overall score.
*   **Management penalties:** To ensure managers are only scheduled as a last resort, the script calculates the highest preference penalty among regular staff, doubles it, and adds it to the management's base preferences. This mathematically guarantees that assigning a shift to management is always the most "expensive" decision the solver can make.

#### 4. Solving the model
Once constructed, the model is passed to `cp_model.CpSolver()`:
*   **Gap limit:** The solver is instructed to stop searching if it finds a schedule that is within a 15% relative gap limit of the theoretical mathematical optimum.
*   **Time limit:** If the problem is highly complex, the search process is strictly capped by the user-defined `max_fitting_minutes` parameter.