import scheduler_model as sm

year = 2026
month = 4
preferences = [
    [1,2,3,4],
    [4,3,2,1],
    [1,3,3,4],
    [1,3,2,4],
    [4,4,4,1],
    [1,10,2,3],
    [1,2,3,10],
    [20,20,20,20]
]
workers_per_shift = [1,1,1,1]
weekly_hours = [20,40,20,30,30,40,20]
flexibility = 1
shift_hours = [
    [7,15],
    [9,12],
    [15,23],
    [23,7+24]
]
break_hours = 12
max_works = 6
min_breaks = 2
management_shift_availability = [1,1,0,0]
management_weekends = True
management_applicability = True

max_minutes = 1                             

model_data = sm.define_model(year,
                             month,
                             preferences, 
                             workers_per_shift,
                             weekly_hours,
                             flexibility,
                             sm.calculate_shifts_lengths(shift_hours),
                             sm.calculate_shifts_incompatibilities(shift_hours,break_hours),
                             sm.get_automaton_data(min_breaks, max_works),
                             management_shift_availability,
                             management_weekends,
                             management_applicability
                             )

status, solver = sm.fit_model(model_data, max_minutes)

sm.output_results(status, solver, model_data)