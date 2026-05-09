import scheduler_model as sm

year = 2026
month = 5
preferences = [
    [1,1,2,3],
    [2,1,1,3],
    [3,1,2,1],
    [2,1,1,3],
    [1,1,1,1],
    [1,1,1,1],
    [1000,1000,1000,1000]
]
workers_per_shift = [1,1,2,1]
weekly_hours = 40
flexibility = 1
shift_hours = [
    [7,15],
    [9,15],
    [15,23],
    [23,7+24]
]
break_hours = 12
management_shift_availability = [1,1,0,0]
management_weekends = True

model_data = sm.define_model(year,
                             month,
                             preferences, 
                             workers_per_shift,
                             weekly_hours,
                             flexibility,
                             sm.calculate_shifts_lengths(shift_hours),
                             sm.calculate_shifts_incompatibilities(shift_hours,break_hours),
                             management_shift_availability,
                             management_weekends
                             )
status, solver = sm.fit_model(model_data)

sm.output_results(status, solver, model_data)