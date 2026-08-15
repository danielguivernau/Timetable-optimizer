
My girlfriend works in a hotel whose reception has workers present around the clock. This means that each month, their management has to put together a schedule to cover all the shifts, taking into account both labour regulations and each worker's preferences. 

Wanting to get back in touch with Operation Research and improve my programming skills, and knowing that scheduling is a classic optimization problem, I wanted to try and create a piece of software that could create these schedules.

I have included some particularities that might only apply to hotels (or perhaps only my girlfriend's), but they are included as optional parameters that can otherwise be ignored.

# How to use it

This program is given data describing the shifts, workers and labour law restrictions, and for a given month, outputs, if possible, the schedule that maximizes worker preferences.

This section will be further developed in the future when a frontend is decided on.

# How it works

## Backend: *scheduler_model.py*
The program is centered around two dataclasses, which I have made as flexible as possible so that they can be adapted to the particular characteristics of each user. Then, these are combined with some general parameters and the optimization problem is defined and solved.

Let's look at the dataclasses first.

### The `Shift` Dataclass

Represents a defined work block. Time parameters and calculations are handled strictly as integers (representing minutes from midnight) to comply with the requirements of the solver used.

| Parameter / Property | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique identifier for the shift type (e.g., `"Night shift"`). |
| `start` | `int` | Shift start time expressed in minutes from midnight (e.g., `1410` for 23:30). |
| `end` | `int` | Shift end time expressed in minutes from midnight (e.g., `450` for 07:30) |
| `workers_required` | `int` | The number of staff members needed for this shift. |
| `@property length` | `int` | **Computed:** Total duration of the shift in minutes, correctly overnight shifts |
| `@property end_abs` | `int` | **Computed:** The absolute end time on a continuous 24h+ clock, used for calculating shift incompatibility. |

**Example:**

```yaml
name: "Night shift"
start: 1410
end: 450
workers_required: 1
```
This would encode a night shift starting at 23:30 and ending the following day at 7:30.

All shifts are then passed in a list sorted by start (ascending) to the model definition function, `define_model()`

### The `Worker` Dataclass

Represents an individual staff member, their role, contract charasteristics, labor law constraints, and shift preferences.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str` | *Required* | The employee's full name or unique identifier. |
| `preferences` | `list[int]` | *Required* | A list of integer scores mapping to each shift. It is used in the model's objective function to minimize unfavorable schedules. |
| `weekly_hours` | `Optional[int]` | `None` | How many weekly hours the worker has to do. |
| `is_management` | `bool` | `False` | A flag indicating a management role. It exempts the worker from the mandatory `weekly_hours` requirement and operates without a strict monthly hours target. |
| `enforce_consecutivity`| `bool` | `True` | If `True`, the model applies automaton transitions to enforce rules around maximum consecutive working days and minimum consecutive break days. |
| `works_weekends` | `bool` | `True` | If `False`, the worker is restricted from working on weekends. |
| `min_one_weekend_off` | `bool` | `True` | If `True`, ensures the worker has at least one completely free weekend (no shifts assigned) during the scheduling period. |
| `allowed_shifts` | `list[bool]` | `None` | A boolean list mapping permissions to available shifts. If an index is `False`, the solver prohibits assigning that specific shift type to the worker. |
| `holidays` | `list[int]` | `None` | A list of specific days (integers) the worker has off. It prevents shifts on those days, displays them as "H" on the timetable, and prorates the required working hours for the month. |

**Example:**

```yaml
name: "Joseph"
preferences: [1,4,2,10]
weekly_hours: 40
is_managemenent: False
enforce_consecutivity: True
works_weekends: True
min_one_weekend_off: True
allowed_shifts: [True,True,True,True]
holidays: [4,5,8,9,10]
```
This encodes the object for Joseph. They aren't management, are hired to work 40 hours a week, work on weekends and can be assigned to all four shift types. Consecutivity constraints must be enforced on them and they should have at least one weekend off this month. Additionally, they have asked for the 4th, 5th, 8th, 9th & 10th of this month as paid time off. Despite being able to work on shifts, we can see that they really prefer the first shift, and deeply dislike the last shift. 
Mathematically, when it comes to the optiomization function, assigning Joseph one of the last shifts would be equivalent to giving them 10 of the first!

### Global Configuration Parameters

Alongside the structural entities, the execution environment requires several global parameters to construct the calendar horizon, configure labor bounds, and manage solver constraints.

| Parameter | Type | Description | 
| :--- | :--- | :--- | 
| `year` | `int` | The calendar year for the target schedule. Used by `monthdata()` to correctly align days and weekend indexes. | 
| `month` | `int` | The calendar month for the target schedule. Used by `monthdata()` to correctly align days and weekend indexes.| 
| `break_hours` | `int` | The minimum mandatory rest window in hours required between the end of one shift and the start of another. | 
| `max_works` | `int` | The maximum number of consecutive days a worker is legally or contractually permitted to work before a break. | 
| `min_breaks` | `int` | The minimum number of consecutive rest days a worker must be given once they complete a work cycle. | 
| `flexibility` | `int` | A buffer scaling factor used to relax monthly target hour limits. Multiplied by the longest shift length to establish an acceptable range, preventing solver crashes due to minor mathematical tight-spots. | 
| `max_fitting_minutes` | `int` | The strict time limit (in minutes) assigned to the CP-SAT solver. The engine will return the best feasible solution found within this window if an optimal one isn't reached. |

#### Data Pre-processing Functions
Before these parameters hit the CP-SAT constraint engine, they are parsed by three foundational pre-processing scripts:
*   **`monthdata(year, month)`:** Uses Python's calendar utilities to generate the month's duration and maps days to weekday integer coordinates (where Monday = 0, Sunday = 6).
*   **`calculate_shifts_incompatibilities(shifts, break_hours)`:** Dynamically translates the raw `break_hours` requirement into an absolute minute matrix, defining exactly how many subsequent shift slots must be locked out after a specific assignment.
*   **`get_consecutivity_automaton_data(min_breaks, max_works)`:** Takes the consecutive limits and maps them into a structural **Finite State Automaton**. This creates an explicit layout of valid worker paths (working states, a mandatory break corridor, and stable rest states) that the solver enforces via a sequence tracking constraint.