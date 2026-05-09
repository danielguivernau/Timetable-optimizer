#from scheduler_model import monthdata
#from scheduler_model import calculate_shifts_lengths

lengths = [1,2,3]
workers = [2,1,1]

print(sum(lengths[i] * workers[i] for i in range(len(lengths))))
