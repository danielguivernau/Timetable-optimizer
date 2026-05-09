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