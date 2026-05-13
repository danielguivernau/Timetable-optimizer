from scheduler_model import monthdata

llista = [1,2,3,4,5]

break_hours = 8
shift_hours = [[7,15],[9,13],[15,23],[23,24+7]]
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

print(shift_incompatibilities)


        # A worker cannot work for more than 7 days straight 
    for i in range(num_workers):
        for d in range(num_days - 6):
            model.Add(sum(work_day[i, d + offset] for offset in range(7)) <= 6) # In any 7-day window, they must work 6 days or fewer

        # A worker cannot have an isolated day off - but management can
    management = int(management_shift_availability is not None) 
    for i in range(num_workers - management):
        for d in range(1,num_days - 1):
            model.Add(work_day[i,d] >= work_day[i,d-1] + work_day[i,d+1] -1) #If a worker works the day before and the day after, they must work that day