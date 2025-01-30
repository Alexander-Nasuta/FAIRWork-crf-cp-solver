import pprint
from typing import List, Any, Dict
import re

import pandas

from utils.logger import log

import collections

from jsp_vis.console import gantt_chart_console
from ortools.sat.python import cp_model


def is_interval_included(target_interval, interval_list):
    """
    Check if a target interval is included or is a subinterval of any interval in a list.

    Parameters:
    - target_interval (tuple): The target interval to check, formatted as (start, end).
    - interval_list (list of tuples): A list of intervals, each formatted as (start, end).

    Returns:
    - bool: True if the target interval is included or is a subinterval of any interval in the list, False otherwise.
    """
    target_start, target_end = target_interval
    for start, end in interval_list:
        if start <= target_start and end >= target_end:
            return True
    return False


def extend_line_allocation_with_geometry_and_required_workers(line_allocation: list) -> list[dict]:
    order_details = {
        "Order 0": {"geometry": "geo1"},
        "Order 1": {"geometry": "geo2"},
        "Order 2": {"geometry": "geo5"},
        "Order 3": {"geometry": "geo1"},
        "Order 4": {"geometry": "geo4"},
        "Order 5": {"geometry": "geo2"},
        "Order 6": {"geometry": "geo3"},
        "Order 7": {"geometry": "geo5"},
        "Order 8": {"geometry": "geo1"},
        "Order 9": {"geometry": "geo4"},
        "Order 10": {"geometry": "geo2"},
        "Order 11": {"geometry": "geo3"},
        "Order 12": {"geometry": "geo5"},
        "Order 13": {"geometry": "geo1"},
        "Order 14": {"geometry": "geo4"},
        "Order 15": {"geometry": "geo2"},
        "Order 16": {"geometry": "geo3"},
        "Order 17": {"geometry": "geo5"},
        "Order 18": {"geometry": "geo1"},
        "Order 19": {"geometry": "geo4"},
        "Order 20": {"geometry": "geo2"},
        "Order 21": {"geometry": "geo3"},
        "Order 22": {"geometry": "geo5"},
        "Order 23": {"geometry": "geo1"},
        "Order 24": {"geometry": "geo4"},
        "Order 25": {"geometry": "geo2"}
    }
    required_workers_mapping = {
        'Line 0': {
            'geo1': 2,
            'geo2': 2,
            'geo3': 2,
            'geo4': 2,
            'geo5': 2,
        },
        'Line 1': {
            'geo1': 2,
            'geo2': 2,
            'geo3': 2,
            'geo4': 2,
            'geo5': 2,
        },
        'Line 2': {
            'geo1': 2,
            'geo2': 2,
            'geo3': 2,
            'geo4': 2,
            'geo5': 2,
        }
    }
    for order in line_allocation:
        order['geometry'] = order_details[order['Task']]['geometry']
        order['required_workers'] = required_workers_mapping[order['Resource']][order['geometry']]
    return line_allocation


def main_allocation(line_data: list[dict], worker_specific_data: dict, worker_availabilities: list[dict],
         preference_weight: int = 1, experience_weight: int = 1, resistance_weight: int = 1,
         staffing_weight: int = 1) -> dict[str, list[Any]]:
    model = cp_model.CpModel()

    # Calculate makespan
    # Change to minutes
    makespan = max(order['Finish'] for order in line_data)
    hours_per_day = 24
    full_days, remaining_hours = divmod(makespan, hours_per_day)
    total_days = full_days + (1 if remaining_hours > 0 else 0)

    log.info(f"""
    Days to complete all orders: {total_days} ({hours_per_day} hours per day)
    Days that are fully utilized: {full_days}
    Remaining hours in the last day: {remaining_hours}
        """)

    horizon = total_days * hours_per_day

    # Line data processing
    lines_names = []
    cp_ids_of_lines = {}
    lines_names_of_cp_ids = {}

    for data in line_data:
        line_name = data['Resource']
        if line_name and line_name not in lines_names:
            match = re.search(r"Line (\d+)", line_name)
            if match:
                number = int(match.group(1))
                lines_names.append(line_name)
                cp_ids_of_lines[line_name] = number
                lines_names_of_cp_ids[number] = line_name

    n_workers = len(worker_specific_data)

    # Generate intervals
    interval_bounds = {order['Start'] for order in line_data}
    interval_bounds.update(order['Finish'] for order in line_data)
    for worker in worker_availabilities:
        for w_availability_interval in worker['availability']:
            interval_bounds.add(w_availability_interval[0])
            interval_bounds.add(w_availability_interval[1])

    interval_bounds_ascending_list = sorted(interval_bounds)
    interval_tuple = [
        (start, end)
        for start, end in zip(interval_bounds_ascending_list[:-1], interval_bounds_ascending_list[1:])
    ]

    n_intervals = len(interval_tuple)
    log.info(f"The schedule is divided into {n_intervals} intervals: {interval_tuple}")

    # Variable stores
    cp_variable_store = {}  # (i_start, i_end, w_id) -> (experience, preference, resilience, allocation)
    cp_line_staff_variables = {}  # (i_start, i_end, line_id) -> staffing

    for interval_start, interval_end in interval_tuple:
        line_details_within_interval = {
            line_name: {
                "required_workers": 0,
                "geometry": None,
                "w_line_interval": []
            } for line_name in lines_names
        }

        # Relevant orders in the interval
        relevant_orders = [
            order for order in line_data if interval_start <= order['Start'] < interval_end
        ]

        for order_info in relevant_orders:
            if order_info['Resource'] in lines_names:
                line_name = order_info['Resource']
                line_details_within_interval[line_name]['required_workers'] = order_info['required_workers']
                line_details_within_interval[line_name]['geometry'] = order_info['geometry']

        # Worker processing
        for worker in worker_availabilities:
            worker_id = worker['Worker_id']
            assignment_possibilities = []

            # Variables for experience, preference, resilience, and allocation
            w_experience = model.NewIntVar(0, horizon * 100,
                                           f"w_{worker_id}_{interval_start}_{interval_end}_experience")
            w_preference = model.NewIntVar(0, horizon * 100,
                                           f"w_{worker_id}_{interval_start}_{interval_end}_preference")
            w_resilience = model.NewIntVar(0, horizon * 100,
                                           f"w_{worker_id}_{interval_start}_{interval_end}_resilience")
            w_allocation = model.NewIntVar(-1, len(lines_names) - 1,
                                           f"w_{worker_id}_{interval_start}_{interval_end}_allocation")

            cp_variable_store[(interval_start, interval_end, worker_id)] = (
            w_experience, w_preference, w_resilience, w_allocation)

            w_not_present = model.NewBoolVar(f"w_{worker_id}_{interval_start}_{interval_end}_not_present")
            model.Add(w_experience == 0).OnlyEnforceIf(w_not_present)
            model.Add(w_preference == 0).OnlyEnforceIf(w_not_present)
            model.Add(w_resilience == 0).OnlyEnforceIf(w_not_present)
            model.Add(w_allocation == -1).OnlyEnforceIf(w_not_present)

            assignment_possibilities.append(w_not_present)

            worker_is_present = is_interval_included((interval_start, interval_end), worker['availability'])
            if not worker_is_present:
                model.Add(w_not_present == 1)
                continue

            for line_name in lines_names:
                if line_details_within_interval[line_name]['required_workers'] == 0:
                    continue

                w_line_interval = model.NewBoolVar(
                    f"w_{worker_id}_{interval_start}_{interval_end}_{line_name.replace(' ', '_')}")
                assignment_possibilities.append(w_line_interval)

                line_geometry = line_details_within_interval[line_name]['geometry']
                interval_length = interval_end - interval_start
                resilience = worker_specific_data.get(worker_id, {}).get(line_geometry, {}).get('resilience',
                                                                                                0) * 100 * interval_length
                preference = worker_specific_data.get(worker_id, {}).get(line_geometry, {}).get('preference',
                                                                                                0) * 100 * interval_length
                experience = worker_specific_data.get(worker_id, {}).get(line_geometry, {}).get('experience',
                                                                                                0) * 100 * interval_length

                model.Add(w_resilience == resilience).OnlyEnforceIf(w_line_interval)
                model.Add(w_preference == preference).OnlyEnforceIf(w_line_interval)
                model.Add(w_experience == experience).OnlyEnforceIf(w_line_interval)

                cp_id_of_line = cp_ids_of_lines[line_name]
                model.Add(w_allocation == cp_id_of_line).OnlyEnforceIf(w_line_interval)

            model.AddExactlyOne(assignment_possibilities)

        # CONSTRAINT: required workers
        # Control the number of workers assigned to a line
        for line_name, entry in line_details_within_interval.items():
            required_workers = entry['required_workers']

            if required_workers == 0:
                continue
            # the number of workers assigned to the line must be at least the required number of workers
            log.info(f"[{interval_start}, {interval_end}] enforcing required workers for line {line_name}. "
                     f"required: {required_workers}")
            var_name = f"line_{line_name}_w_offset_in_interval_{interval_start}_{interval_end}"
            line_required_worker_offset = model.new_int_var(-required_workers, n_workers, f"line_required_worker_offset_{line_name}")

            model.Add(line_required_worker_offset == sum(entry['w_line_interval']) - required_workers)
            # model.add_min_equality(line_required_worker_offset, [0, sum(entry['w_line_interval']) - required_workers])

            # add staffing to cost instead of hard constraint, so that the model can still be solved
            cp_line_staff_variables[(interval_start, interval_end, line_name)] = line_required_worker_offset

            # model.Add(sum(entry['w_line_interval']) >= required_workers)

    total_preference = model.NewIntVar(0, horizon * 100 * n_workers, "total_preference")
    model.Add(total_preference == sum(w_preference for _, w_preference, _, _ in cp_variable_store.values()))

    total_experience = model.NewIntVar(0, horizon * 100 * n_workers, "total_experience")
    model.Add(total_experience == sum(w_experience for w_experience, _, _, _ in cp_variable_store.values()))

    total_resilience = model.NewIntVar(0, horizon * 100 * n_workers, "total_resilience")
    model.Add(total_resilience == sum(w_resilience for _, _, w_resilience, _ in cp_variable_store.values()))

    # Negative values indicate understaffing
    # Positive values indicate overstaffing
    # The cost function will try to maximize the total_staff_offset, so that understaffing is minimized
    total_staff_offset = model.NewIntVar(-n_workers * n_intervals, n_workers * n_intervals, "total_understaffing")
    model.Add(total_staff_offset == sum(line_staff_offset for line_staff_offset in cp_line_staff_variables.values()))

    sum_of_weights = preference_weight + experience_weight + resistance_weight + staffing_weight
    objective = model.NewIntVar(0, horizon * 100 * n_workers * 3 * (sum_of_weights), "objective")

    # Meet the staffing numbers first
    # Hard constraints preventing allocations
    # Look for alternatives
    # Check whether Sunday was taken into account in order to line
    model.Add(objective == (
            preference_weight * total_preference +
            experience_weight * total_experience +
            resistance_weight * total_resilience +
            staffing_weight * total_staff_offset
    ))

    # Maximize the objective function
    model.Maximize(objective)

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Extract the solution
    workers_list = {}

    # Return if no solution was found
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        log.info("No solution found")
        return workers_list

    # Iterate over cp_variable_store to get the results
    for key_tuple, val_tuple in cp_variable_store.items():
        # Deconstruct key tuple
        interval_start, interval_end, worker_id = key_tuple
        w_experience, w_preference, w_resilience, w_allocation = val_tuple

        if solver.Value(w_allocation) != -1:
            line_cp_id = solver.Value(w_allocation)
            line_name = lines_names_of_cp_ids[line_cp_id]
            if line_name not in workers_list:
                workers_list[line_name] = []
            workers_list[line_name].append(worker_id)
            log.info(
                f"[{interval_start}-{interval_end}] Worker {worker_id} is assigned to line {line_cp_id} ('{line_name}')"
            )
        else:
            log.info(f"[{interval_start}-{interval_end}] Worker {worker_id} is not assigned to any line")

    # Log the solution summary
    log.info(f"""
    Solution found: {status == cp_model.OPTIMAL or status == cp_model.FEASIBLE}
    Solution is optimal: {status == cp_model.OPTIMAL}

    Number of intervals: {n_intervals}

    Objective: {solver.Value(objective)}
    Total preference: {solver.Value(total_preference)}
    Total experience: {solver.Value(total_experience)}
    Total resilience: {solver.Value(total_resilience)}
    """)

    # Return the worker assignments
    return workers_list


if __name__ == '__main__':
    line_allocation_from_previous_step = [
        {'Task': 'Order 0', 'Start': 0, 'Finish': 27, 'Resource': 'Line 1'},
        {'Task': 'Order 1', 'Start': 36, 'Finish': 56, 'Resource': 'Line 0'},
        {'Task': 'Order 2', 'Start': 33, 'Finish': 48, 'Resource': 'Line 2'},
        {'Task': 'Order 3', 'Start': 16, 'Finish': 36, 'Resource': 'Line 0'},
        {'Task': 'Order 4', 'Start': 0, 'Finish': 10, 'Resource': 'Line 0'},
        {'Task': 'Order 5', 'Start': 37, 'Finish': 47, 'Resource': 'Line 1'},
        {'Task': 'Order 6', 'Start': 10, 'Finish': 16, 'Resource': 'Line 0'},
        {'Task': 'Order 7', 'Start': 8, 'Finish': 13, 'Resource': 'Line 2'},
        {'Task': 'Order 8', 'Start': 0, 'Finish': 8, 'Resource': 'Line 2'},
        {'Task': 'Order 9', 'Start': 13, 'Finish': 26, 'Resource': 'Line 2'},
        {'Task': 'Order 10', 'Start': 27, 'Finish': 37, 'Resource': 'Line 1'},
        {'Task': 'Order 11', 'Start': 73, 'Finish': 80, 'Resource': 'Line 0'},
        {'Task': 'Order 12', 'Start': 74, 'Finish': 79, 'Resource': 'Line 1'},
        {'Task': 'Order 13', 'Start': 67, 'Finish': 73, 'Resource': 'Line 0'},
        {'Task': 'Order 14', 'Start': 76, 'Finish': 80, 'Resource': 'Line 2'},
        {'Task': 'Order 15', 'Start': 72, 'Finish': 76, 'Resource': 'Line 2'},
        {'Task': 'Order 16', 'Start': 66, 'Finish': 72, 'Resource': 'Line 1'},
        {'Task': 'Order 17', 'Start': 52, 'Finish': 68, 'Resource': 'Line 2'},
        {'Task': 'Order 18', 'Start': 47, 'Finish': 51, 'Resource': 'Line 1'},
        {'Task': 'Order 19', 'Start': 59, 'Finish': 65, 'Resource': 'Line 1'},
        {'Task': 'Order 20', 'Start': 56, 'Finish': 60, 'Resource': 'Line 0'},
        {'Task': 'Order 21', 'Start': 26, 'Finish': 33, 'Resource': 'Line 2'},
        {'Task': 'Order 22', 'Start': 51, 'Finish': 59, 'Resource': 'Line 1'},
        {'Task': 'Order 23', 'Start': 60, 'Finish': 67, 'Resource': 'Line 0'},
        {'Task': 'Order 24', 'Start': 48, 'Finish': 52, 'Resource': 'Line 2'},
        {'Task': 'Order 25', 'Start': 68, 'Finish': 72, 'Resource': 'Line 2'}
    ]
    log.debug(f"line_allocation_from_previous_step: {pprint.pformat(line_allocation_from_previous_step)}")

    line_allocation_with_geometry_and_required_workers = extend_line_allocation_with_geometry_and_required_workers(
        line_allocation_from_previous_step)

    log.info(
        f"line_allocation_with_geometry_and_required_workers: {pprint.pformat(line_allocation_with_geometry_and_required_workers)}")

    worker_availabilities = [
        # first shift
        {'Worker_id': 1, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        {'Worker_id': 2, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        {'Worker_id': 3, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        {'Worker_id': 4, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        {'Worker_id': 5, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        {'Worker_id': 6, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        # first shift on some days (not full time)
        {'Worker_id': 7, "availability": [(0, 7), (16, 23), (32, 39)]},
        {'Worker_id': 8, "availability": [(0, 7), (16, 23), (32, 39)]},
        {'Worker_id': 9, "availability": [(48, 55), (64, 71)]},
        {'Worker_id': 10, "availability": [(0, 7), (16, 23), (32, 39)]},

        # second shift
        {'Worker_id': 11, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},
        {'Worker_id': 12, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},
        {'Worker_id': 13, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},
        {'Worker_id': 14, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},
        {'Worker_id': 15, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},
        {'Worker_id': 16, "availability": [(8, 15), (24, 31), (40, 47), (56, 63), (72, 79)]},

        # second shift on some days (not full time)
        {'Worker_id': 17, "availability": [(8, 15), (24, 31), (40, 47)]},
        {'Worker_id': 18, "availability": [(8, 15), (24, 31), (40, 47)]},
        {'Worker_id': 19, "availability": [(56, 63), (72, 79)]},
        {'Worker_id': 20, "availability": [(8, 15), (24, 31), (40, 47)]},
    ]

    worker_specific_data = {
        1: {
            "geo1": {
                "experience": 0.01,
                "preference": 0.19,
                "resilience": 0.09,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.46,
                "preference": 0.85,
                "resilience": 0.49,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.39,
                "preference": 0.99,
                "resilience": 0.06,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.62,
                "preference": 0.4,
                "resilience": 0.21,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.56,
                "preference": 0.42,
                "resilience": 0.78,
                "medical-condition": True,
            },
        },
        2: {
            "geo1": {
                "experience": 0.34,
                "preference": 0.94,
                "resilience": 0.06,
                "medical-condition": False,
            },
            "geo2": {
                "experience": 0.42,
                "preference": 0.49,
                "resilience": 0.81,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.79,
                "preference": 0.95,
                "resilience": 0.8,
                "medical-condition": False,
            },
            "geo4": {
                "experience": 0.86,
                "preference": 0.29,
                "resilience": 0.51,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.15,
                "preference": 0.94,
                "resilience": 0.65,
                "medical-condition": False,
            },
        },
        3: {
            "geo1": {
                "experience": 0.08,
                "preference": 0.4,
                "resilience": 0.61,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.41,
                "preference": 0.78,
                "resilience": 0.67,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.61,
                "preference": 0.64,
                "resilience": 0.6,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.43,
                "preference": 0.35,
                "resilience": 0.19,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.32,
                "preference": 0.86,
                "resilience": 0.92,
                "medical-condition": False,
            },
        },
        4: {
            "geo1": {
                "experience": 0.02,
                "preference": 0.89,
                "resilience": 0.43,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.41,
                "preference": 0.34,
                "resilience": 0.01,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.27,
                "preference": 0.42,
                "resilience": 0.98,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.47,
                "preference": 0.6,
                "resilience": 0.25,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.63,
                "preference": 0.35,
                "resilience": 0.15,
                "medical-condition": True,
            },
        },
        5: {
            "geo1": {
                "experience": 0.9,
                "preference": 0.88,
                "resilience": 0.75,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.84,
                "preference": 0.81,
                "resilience": 0.23,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.13,
                "preference": 0.73,
                "resilience": 0.12,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.17,
                "preference": 0.77,
                "resilience": 0.39,
                "medical-condition": False,
            },
            "geo5": {
                "experience": 0.56,
                "preference": 0.66,
                "resilience": 0.25,
                "medical-condition": False,
            },
        },
        6: {
            "geo1": {
                "experience": 0.29,
                "preference": 0.78,
                "resilience": 0.94,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.14,
                "preference": 0.95,
                "resilience": 0.83,
                "medical-condition": False,
            },
            "geo3": {
                "experience": 0.35,
                "preference": 0.18,
                "resilience": 0.98,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.41,
                "preference": 0.13,
                "resilience": 0.86,
                "medical-condition": False,
            },
            "geo5": {
                "experience": 0.35,
                "preference": 0.21,
                "resilience": 0.88,
                "medical-condition": True,
            },
        },
        7: {
            "geo1": {
                "experience": 0.87,
                "preference": 0.54,
                "resilience": 0.2,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.3,
                "preference": 0.47,
                "resilience": 0.09,
                "medical-condition": False,
            },
            "geo3": {
                "experience": 0.62,
                "preference": 0.16,
                "resilience": 0.69,
                "medical-condition": False,
            },
            "geo4": {
                "experience": 0.93,
                "preference": 0.67,
                "resilience": 0.14,
                "medical-condition": False,
            },
            "geo5": {
                "experience": 0.02,
                "preference": 0.6,
                "resilience": 0.18,
                "medical-condition": True,
            },
        },
        8: {
            "geo1": {
                "experience": 0.0,
                "preference": 0.11,
                "resilience": 0.31,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.88,
                "preference": 0.3,
                "resilience": 0.88,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.81,
                "preference": 0.11,
                "resilience": 0.14,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.63,
                "preference": 0.41,
                "resilience": 0.35,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.21,
                "preference": 0.19,
                "resilience": 0.74,
                "medical-condition": False,
            },
        },
        9: {
            "geo1": {
                "experience": 0.71,
                "preference": 0.57,
                "resilience": 0.42,
                "medical-condition": False,
            },
            "geo2": {
                "experience": 0.06,
                "preference": 0.13,
                "resilience": 0.57,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.37,
                "preference": 0.8,
                "resilience": 0.7,
                "medical-condition": False,
            },
            "geo4": {
                "experience": 0.12,
                "preference": 0.53,
                "resilience": 0.78,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.96,
                "preference": 0.69,
                "resilience": 0.15,
                "medical-condition": True,
            },
        },
        10: {
            "geo1": {
                "experience": 0.96,
                "preference": 0.37,
                "resilience": 0.72,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.38,
                "preference": 0.1,
                "resilience": 0.33,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.47,
                "preference": 0.34,
                "resilience": 0.31,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.12,
                "preference": 0.43,
                "resilience": 0.02,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.8,
                "preference": 0.14,
                "resilience": 0.01,
                "medical-condition": True,
            },
        },
        11: {
            "geo1": {
                "experience": 0.88,
                "preference": 0.6,
                "resilience": 0.74,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.51,
                "preference": 0.56,
                "resilience": 0.41,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.08,
                "preference": 0.49,
                "resilience": 0.76,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.18,
                "preference": 0.17,
                "resilience": 0.91,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.35,
                "preference": 0.52,
                "resilience": 0.53,
                "medical-condition": True,
            },
        },
        12: {
            "geo1": {
                "experience": 0.21,
                "preference": 0.4,
                "resilience": 0.34,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.51,
                "preference": 0.72,
                "resilience": 0.04,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.56,
                "preference": 0.03,
                "resilience": 0.62,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.43,
                "preference": 0.34,
                "resilience": 0.49,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.88,
                "preference": 0.86,
                "resilience": 0.93,
                "medical-condition": True,
            },
        },
        13: {
            "geo1": {
                "experience": 0.66,
                "preference": 0.05,
                "resilience": 0.96,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.48,
                "preference": 0.56,
                "resilience": 0.52,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.58,
                "preference": 0.26,
                "resilience": 0.57,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.51,
                "preference": 0.97,
                "resilience": 0.29,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.78,
                "preference": 0.88,
                "resilience": 0.62,
                "medical-condition": True,
            },
        },
        14: {
            "geo1": {
                "experience": 0.44,
                "preference": 0.04,
                "resilience": 0.92,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.36,
                "preference": 0.08,
                "resilience": 0.27,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.35,
                "preference": 0.42,
                "resilience": 0.23,
                "medical-condition": False,
            },
            "geo4": {
                "experience": 0.92,
                "preference": 0.09,
                "resilience": 0.41,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.48,
                "preference": 0.87,
                "resilience": 0.43,
                "medical-condition": False,
            },
        },
        15: {
            "geo1": {
                "experience": 0.68,
                "preference": 0.17,
                "resilience": 0.01,
                "medical-condition": False,
            },
            "geo2": {
                "experience": 0.55,
                "preference": 0.93,
                "resilience": 0.76,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.29,
                "preference": 0.24,
                "resilience": 0.1,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.96,
                "preference": 0.72,
                "resilience": 0.78,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.14,
                "preference": 0.67,
                "resilience": 0.43,
                "medical-condition": False,
            },
        },
        16: {
            "geo1": {
                "experience": 0.95,
                "preference": 0.19,
                "resilience": 0.86,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.0,
                "preference": 0.55,
                "resilience": 0.66,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.57,
                "preference": 0.09,
                "resilience": 0.84,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.42,
                "preference": 0.79,
                "resilience": 0.88,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.61,
                "preference": 0.75,
                "resilience": 0.12,
                "medical-condition": True,
            },
        },
        17: {
            "geo1": {
                "experience": 0.3,
                "preference": 0.98,
                "resilience": 0.89,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.67,
                "preference": 0.78,
                "resilience": 0.82,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.87,
                "preference": 0.09,
                "resilience": 0.71,
                "medical-condition": False,
            },
            "geo4": {
                "experience": 0.24,
                "preference": 0.31,
                "resilience": 0.47,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.35,
                "preference": 0.41,
                "resilience": 0.19,
                "medical-condition": True,
            },
        },
        18: {
            "geo1": {
                "experience": 0.0,
                "preference": 0.53,
                "resilience": 0.03,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.55,
                "preference": 0.05,
                "resilience": 0.44,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.96,
                "preference": 0.33,
                "resilience": 0.37,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.63,
                "preference": 0.38,
                "resilience": 0.7,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.94,
                "preference": 0.95,
                "resilience": 0.58,
                "medical-condition": False,
            },
        },
        19: {
            "geo1": {
                "experience": 0.57,
                "preference": 0.77,
                "resilience": 0.08,
                "medical-condition": False,
            },
            "geo2": {
                "experience": 0.57,
                "preference": 0.14,
                "resilience": 0.63,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.55,
                "preference": 0.73,
                "resilience": 0.82,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.44,
                "preference": 0.74,
                "resilience": 0.28,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.26,
                "preference": 0.3,
                "resilience": 0.67,
                "medical-condition": True,
            },
        },
        20: {
            "geo1": {
                "experience": 0.68,
                "preference": 0.02,
                "resilience": 0.04,
                "medical-condition": True,
            },
            "geo2": {
                "experience": 0.0,
                "preference": 0.15,
                "resilience": 0.77,
                "medical-condition": True,
            },
            "geo3": {
                "experience": 0.73,
                "preference": 0.49,
                "resilience": 0.03,
                "medical-condition": True,
            },
            "geo4": {
                "experience": 0.9,
                "preference": 0.94,
                "resilience": 0.99,
                "medical-condition": True,
            },
            "geo5": {
                "experience": 0.4,
                "preference": 0.48,
                "resilience": 0.68,
                "medical-condition": False,
            },
        },
    }

    worker_list = main_allocation(
        line_data=line_allocation_with_geometry_and_required_workers,
        worker_specific_data=worker_specific_data,
        worker_availabilities=worker_availabilities)

    df = pandas.DataFrame(line_allocation_with_geometry_and_required_workers)
    print(df.head(n=30))
