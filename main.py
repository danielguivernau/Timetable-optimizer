import scheduler_model as sm

year = 2026
month = 5
pref = [
    [1,2,3],
    [2,1,3],
    [3,2,1],
    [2,1,3],
    [1,2,3],
    [1,1,999],
    [999,999,1]
]
wps = [2,1,1]

model_data = sm.define_model(year, month, pref, wps)
status, solver = sm.fit_model(model_data)

sm.output_results(status, solver, model_data)