p_vars = {'workers': 8}

input_data = {
    'start_date': '',
    'end_date': '',
    'branch_id': '',
    'teams': [],
    'daily': False,
    'multi': False,
    'is_lunch': True,
    'is_break': False
}

import multiprocessing

num_cores = multiprocessing.cpu_count()
print(f"Number of CPU cores: {num_cores}")
