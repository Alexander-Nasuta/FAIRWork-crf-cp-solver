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


medical_flag = False  # Global flag


def main_allocation(line_data: List[Dict], worker_specific_data: Dict, worker_availabilities: List[Dict],
                    preference_weight: int = 1, experience_weight: int = 1, resistance_weight: int = 1,
                    staffing_weight: int = 1) -> Dict[str, List[Any]]:
    global medical_flag  # Using the global flag variable to retry if no valid solution is found with medical condition

    model = cp_model.CpModel()
    hours_per_day = 24
    makespan = max(order['Finish'] for order in line_data)  # Maximum time for all line tasks
    full_days, remaining_hours = divmod(makespan, hours_per_day)  # Calculate full days and remaining hours
    total_days = full_days + (1 if remaining_hours > 0 else 0)  # Total days for the schedule
    horizon = total_days * hours_per_day  # Total horizon in hours

    line_names = list({order['Resource'] for order in line_data})  # Extract unique line names

    # Calculate the minimum and maximum number of workers per line

    min_workers_per_line = {}
    max_workers_per_line = {}

    for line in line_names:
        line_orders = [order for order in line_data if order['Resource'] == line]
        min_workers_per_line[line] = max(order['required_workers'] for order in line_orders)
        max_workers_per_line[line] = sum(order['required_workers'] for order in line_orders)

    # Created an assignment variables for each worker and each line (whether the worker is assigned to that line or not)
    assignment_vars = {}
    for worker in worker_specific_data:
        worker_id = worker
        assignment_vars[worker_id] = {}
        for line in line_names:
            assignment_vars[worker_id][line] = model.NewBoolVar(f"assign_worker_{worker_id}_to_{line}")

    # Add constraint that each worker can be assigned to at most one line at any given time
    for worker in worker_specific_data:
        worker_id = worker
        model.Add(sum(assignment_vars[worker_id][line] for line in line_names) <= 1)

    # Add constraints to ensure each line has the required number of workers within [min,max]
    for line in line_names:
        model.Add(
            sum(assignment_vars[worker_id][line] for worker_id in worker_specific_data) >= min_workers_per_line[line])
        model.Add(
            sum(assignment_vars[worker_id][line] for worker_id in worker_specific_data) <= max_workers_per_line[line])

    # Hard Constraint
    # Add constraints for workers, ensuring they are only assigned to lines during their available intervals
    for worker in worker_availabilities:
        worker_id = worker['Worker_id']
        for availability in worker['availability']:
            start, end = availability
            availability_var = model.NewBoolVar(f"worker_{worker_id}_available_{start}_{end}")
            for line in line_names:
                model.Add(assignment_vars[worker_id][line] == 1).OnlyEnforceIf(availability_var)

    # Hard constraint: workers with a medical condition cannot be assigned to specific lines based on the geometry
    # This block is skipped if medical_flag is True (When no valid solution was found using medical flag)
    if not medical_flag:
        for worker_id, worker_data in worker_specific_data.items():
            for geo, geo_data in worker_data.items():
                if geo_data.get("medical-condition", False):  # Only apply to workers with a medical condition
                    for line in line_names:
                        if any(order['Resource'] == line and order.get('geometry') == geo for order in line_data):
                            model.Add(assignment_vars[worker_id][line] == 0)

    # Soft constraints: deviations from the ideal assignment based on preference, experience, resistance, and staffing
    preference_total = []
    experience_total = []
    resistance_total = []
    staffing_total = []
    for worker in worker_specific_data:
        worker_id = worker
        for line in line_names:
            preference = model.NewIntVar(0, 10 * horizon, f"preference_penalty_{worker_id}_{line}")
            experience = model.NewIntVar(0, 10 * horizon, f"experience_penalty_{worker_id}_{line}")
            resistance = model.NewIntVar(0, 10 * horizon, f"resistance_penalty_{worker_id}_{line}")
            staffing = model.NewIntVar(0, 10 * horizon, f"staffing_penalty_{worker_id}_{line}")

            model.Add(preference == preference_weight).OnlyEnforceIf(assignment_vars[worker_id][line])
            model.Add(experience == experience_weight).OnlyEnforceIf(assignment_vars[worker_id][line])
            model.Add(resistance == resistance_weight).OnlyEnforceIf(assignment_vars[worker_id][line])
            model.Add(staffing == staffing_weight).OnlyEnforceIf(assignment_vars[worker_id][line])

            preference_total.append(preference)
            experience_total.append(experience)
            resistance_total.append(resistance)
            staffing_total.append(staffing)

    # Calculate the total number of workers assigned
    total_workers_assigned = sum(
        assignment_vars[worker_id][line] for worker_id in worker_specific_data for line in line_names
    )

    # Add slack variable to handle over or under-staffing and ensure value close to required workers
    staffing_slack = model.NewIntVar(0, sum(max_workers_per_line.values()), "staffing_slack")
    model.Add(staffing_slack == sum(
        sum(assignment_vars[worker_id][line] for worker_id in worker_specific_data) - min_workers_per_line[line]
        for line in line_names
    ))

    # Define the objective: maximize the weighted sum of preference, experience, resistance, and staffing
    objective = model.NewIntVar(0, 100000, "objective")
    model.Add(objective == sum(preference_total) + sum(experience_total) + sum(resistance_total) + sum(
        staffing_total))

    # Staffing constraints ensuring number of workers as close to required number for line and prevent over-staffing
    model.Maximize(objective + staffing_weight * staffing_slack - staffing_weight * total_workers_assigned)

    # For more staff allocation (Over-staffing) better constraint is:
    # model.Maximize(objective + staffing_weight * staffing_slack)

    # Solve the model using the CP solver
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    workers_list = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for worker in worker_specific_data:
            worker_id = worker
            for line in line_names:
                if solver.Value(assignment_vars[worker_id][line]):
                    if line not in workers_list:
                        workers_list[line] = []
                    workers_list[line].append(worker_id)

    # If no workers are assigned and medical_condition is False
    # then retry with medical_condition true to get a valid solution
    if not workers_list and not medical_flag:
        medical_flag = True  # Set flag to True and retry
        return main_allocation(line_data, worker_specific_data, worker_availabilities,
                               preference_weight, experience_weight, resistance_weight, staffing_weight)

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

    print(f"Worker Allocation is as follows: {worker_list}")
    df = pandas.DataFrame(line_allocation_with_geometry_and_required_workers)
    print(df.head(n=30))
