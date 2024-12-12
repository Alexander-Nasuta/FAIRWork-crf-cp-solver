import math

from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
import time
from datetime import datetime

from order_scheduling.cp_order_to_line import main
from worker_allocation.cp_woker_allocation import main_allocation
from worker_allocation.cp_woker_allocation import extend_line_allocation_with_geometry_and_required_workers

app = Flask(__name__)
api = Api(app, version="1.0.0", title="Example API",
          description="API documentation for processing planning data, with each field as a parameter.")

# Define the models for complex parameter types with example values to tell the user about the input type
order_data_model = api.model('OrderData', {
    'order': fields.String(required=True, example="example order 1", description="Order identifier"),
    'geometry': fields.String(required=True, example="geo1", description="Geometry associated with the order"),
    'amount': fields.Integer(required=True, example=3000, description="Order amount"),
    'deadline': fields.String(required=True, example="2021-12-31", description="Order deadline (YYYY-MM-DD)"),
    'priority': fields.Boolean(required=True, example=True, description="Order priority"),
    'mold': fields.Integer(required=True, example=4, description="Mold type")
})

geometry_line_mapping_model = api.model('GeometryLineMapping', {
    'geometry': fields.String(required=True, example="geo1", description="Geometry name"),
    'main_line': fields.String(required=True, example="line 7", description="Main production line"),
    'alternative_lines': fields.List(fields.String, required=True, example=["line 17"],
                                     description="Alternative lines"),
    'number_of_workers': fields.Integer(required=True, example=3, description="Number of workers")
})

throughput_mapping_model = api.model('ThroughputMapping', {
    'line': fields.String(required=True, example="line 7", description="Production line name"),
    'geometry': fields.String(required=True, example="geo1", description="Geometry name"),
    'throughput': fields.Integer(required=True, example=3000, description="Throughput value")
})

human_factor_model = api.model('HumanFactor', {
    'geometry': fields.String(required=True, example="geo1", description="Geometry name"),
    'preference': fields.Float(required=True, example=0.5, description="Worker preference value"),
    'resilience': fields.Float(required=True, example=0.9, description="Worker resilience value"),
    'medical_condition': fields.Boolean(required=True, example=True,
                                        description="Indicates if medical conditions exist"),
    'experience': fields.Float(required=True, example=0.9, description="Worker experience value"),
    'worker': fields.String(required=True, example="worker 1", description="Worker identifier")
})

availabilities_model = api.model('Availabilities', {
    'date': fields.String(required=True, example="2024-12-31", description="Availability date (YYYY-MM-DD)"),
    'from_timestamp': fields.Integer(required=True, example=234, description="Start time in Unix timestamp"),
    'end_timestamp': fields.Integer(required=True, example=123123, description="End time in Unix timestamp"),
    'worker': fields.String(required=True, example="worker 1", description="Worker identifier")
})

hardcoded_allocation_model = api.model('HardcodedAllocation', {
    'geometry': fields.String(required=True, example="geo1", description="Geometry name"),
    'line': fields.String(required=True, example="line 7", description="Production line"),
    'start_timestamp': fields.Integer(required=True, example=123, description="Start time in Unix timestamp"),
    'end_timestamp': fields.Integer(required=True, example=123, description="End time in Unix timestamp")
})

# Combine all models into a single request body model
request_body_model = api.model('WorkerAssignmentRequest', {
    'start_time_timestamp': fields.Integer(required=True, example=1630454400,
                                           description="Start time of the planning window in Unix timestamp format."),
    'order_data': fields.List(fields.Nested(order_data_model), required=True,
                              description="List of orders with their details."),
    'geometry_line_mapping': fields.List(fields.Nested(geometry_line_mapping_model), required=True,
                                         description="Mapping of geometries to production lines."),
    'throughput_mapping': fields.List(fields.Nested(throughput_mapping_model), required=True,
                                      description="List of throughput mappings for each line.",
                                      example=[
                                          {
                                              "line": "line 7",
                                              "geometry": "geo1",
                                              "throughput": 3000
                                          },
                                          {
                                              "line": "line 17",
                                              "geometry": "geo1",
                                              "throughput": 3000
                                          }
                                      ]),
    'human_factor': fields.List(fields.Nested(human_factor_model), required=True,
                                description="Human factor details for workers and geometries."),
    'availabilities': fields.List(fields.Nested(availabilities_model), required=True,
                                  description="Availability details for workers."),
    'hardcoded_allocation': fields.List(fields.Nested(hardcoded_allocation_model), required=True,
                                        description="Hardcoded allocation of geometries to production lines.")
})


# Define the resource and parameters
# API for worker assignment
@api.route('/worker-assignment')
class WorkerAssignment(Resource):
    @api.doc('worker_allocation')
    @api.expect(request_body_model, validate=True)
    @api.response(200, 'Successfully processed the planning data.')
    @api.response(400, 'Invalid input data.')
    def post(self):
        # Here we would process the planning data
        data = request.json
        print(data)  # This will print the received JSON data to the console

        # Accessing specific fields from the JSON
        start_time_timestamp = data.get('start_time_timestamp')
        print(start_time_timestamp)
        # Accessing order_data
        order_data = data.get('order_data')
        print(order_data)
        # Store the values for each order in order_list like: (duration [h], line_id, priority, due_date [h])
        order_list = []
        # order_dict to uniquely identify the order based on id
        order_dict = {}
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []  # if order is not in the dictionary we create an enry for it
            priority = 0
            if order['priority'] == 'false':
                priority = 1
            # Convert the time into seconds format
            deadline_timestamp = int(
                time.mktime(datetime.strptime(order["deadline"], "%Y-%m-%d").timetuple())
            )
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to hours
            duration_hours = duration_seconds / 3600

            # Use the geometry_line_mapping to identify the available lines for the given order
            geometry_line_mapping = data.get('geometry_line_mapping')
            line_list = []
            for geometry in geometry_line_mapping:
                if geometry['geometry'] == order['geometry']:
                    line_list.append(geometry['main_line'])  # add the possible line for the order to the line list.
                    line_list.extend(geometry['alternative_lines'])

            # Iterate through the throughput mapping list and find the entry for which
            # line and geometry match with the order
            throughput_mapping_list = data.get('throughput_mapping')
            for throughput_mapping in throughput_mapping_list:
                temp = 0
                for line in line_list:
                    if throughput_mapping['line'] == line and throughput_mapping['geometry'] == order['geometry']:
                        duration = ((5 * order['mold']) + (
                                15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        # add the entry (duration [h], line_id, priority, due_date [h])
                        # to the order_dict for the given order
                        order_dict[order['order']].append(
                            (math.ceil(duration), temp, priority, math.ceil(duration_hours)))
                        temp = temp + 1
        for key, value in order_dict.items():
            order_list.append(value)

        # Replace the hard coded EXAMPLE_ORDER_INSTANCE with the order list generated in the previous step
        # and call the function main() from cp_order_to_line
        solution_df = main(order_list=order_list)
        print(solution_df.head(n=30))

        # Retrieve the order_to_line results
        solution_dict = solution_df.to_dict(orient='records')
        order_to_line = solution_dict
        print(order_list)
        worker_specific_data = {}
        human_factor = data.get('human_factor')
        worker_list = []

        # Extract the worker ids and store them in a list
        for factor in human_factor:
            worker_list.append(factor['worker'])
        index = 1

        # Iterate through the workers and store the
        # "experience" "preference" "resilience" and "medical-condition" for each worker
        for worker in worker_list:
            if index not in worker_specific_data:
                worker_specific_data[index] = {}
            for factor in human_factor:
                if worker == factor['worker']:
                    worker_specific_data[index][factor['geometry']] = {}
                    medical_condition = True
                    if factor['medical_condition'] == 'false':
                        medical_condition = False
                    new_data = {
                        "experience": factor['experience'],
                        "preference": factor['preference'],
                        "resilience": factor['resilience'],
                        "medical-condition": medical_condition
                    }
                    worker_specific_data[index][factor['geometry']] = new_data
            index = index + 1
        print(order_list)

        # Retrieve all orders and map them in the format "Order i" where i is the index for a unique order
        order_details = {}
        order_list = data.get('order_data')
        order_dicts = {}
        temp = 0

        for order in order_list:
            if order['order'] not in order_dicts:
                order_dicts[order['order']] = temp
                temp = temp + 1
            order_val = "Order " + str(order_dicts[order['order']])
            if order_val not in order_details:
                order_details[order_val] = []
            order_details[order_val].append(order['geometry'])

        worker_availabilities = [
            # first shift
            {'Worker_id': 1, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        ]

        # Create the required_workers_mapping by mapping the Line with geometry and required number of workers
        # (see required_workers_mapping in cp_worker_allocation)
        geometry_worker_count = {}
        geometry_line = data.get('geometry_line_mapping')

        for items in geometry_line:
            geometry_worker_count[items['geometry']] = items['number_of_workers']

        required_workers_mapping = {}
        throughput_mapping_lists = data.get('throughput_mapping')
        for items in throughput_mapping_lists:
            if items['line'] not in required_workers_mapping:
                required_workers_mapping[items['line']] = {}
            geometry_val = {items['geometry']: geometry_worker_count[items['geometry']]}
            # For each line we append geometry and required number of workers
            required_workers_mapping[items['line']].update(geometry_val)

        # Create a mapping for each line number with Line 0, Line 1, Line 2 ....
        line_mapping = {}
        temp_required_workers_mapping = {}
        temp = 0
        for key, value in required_workers_mapping.items():
            temp_line = "Line " + str(temp)
            temp = temp + 1
            temp_required_workers_mapping[temp_line] = value
            line_mapping[temp_line] = key
        required_workers_mapping = temp_required_workers_mapping

        # Retrieve the worker availabilities
        availabilities = data.get('availabilities')
        worker_availabilities = []
        # Transform the worker availabilities into tuple format
        for availability in availabilities:
            worker_id = availability["worker"].split()[-1]  # Extract worker ID (assuming format "worker <id>")

            # Assume the from_time and end_time is relative to start_time_timestamp
            from_timestamp = start_time_timestamp + availability["from_timestamp"]
            end_timestamp = start_time_timestamp + availability["end_timestamp"]

            # Calculate relative times in hours, rounded up
            from_relative = math.floor((from_timestamp - start_time_timestamp) / 3600)  # Rounded down
            end_relative = math.ceil((end_timestamp - start_time_timestamp) / 3600)  # Rounded up

            # Ensure values are natural numbers
            from_relative = max(0, from_relative)
            end_relative = max(0, end_relative)

            # Append worker availability as tuple
            worker_availabilities.append({
                "Worker_id": int(worker_id),
                "availability": [(from_relative, end_relative)]
            })

        # Hard coded worker_availabilities example not to be used
        worker_availabilities = [
            # first shift
            {'Worker_id': 1, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        ]

        # For each task (Order) in the result obtained from order_to_line, we add the list of possible geometries
        # see hardcoded order_details in cp_worker_allocation.py for more information
        line_allocation = []
        for order in order_to_line:
            geo_list = order_details[order['Task']]
            for geo in geo_list:
                temp_order = order
                temp_order['geometry'] = geo
                temp_order['required_workers'] = required_workers_mapping[order['Resource']][temp_order['geometry']]
                line_allocation.append(temp_order)

        #    order['required_workers'] = required_workers_mapping[order['Resource']][order['geometry']]
        # line_allocation_with_geometry_and_required_workers = extend_line_allocation_with_geometry_and_required_workers(
        #    order_to_line

        # We perform the worker_allocation by running the solver
        allocation_list = main_allocation(
            line_data=line_allocation,
            worker_specific_data=worker_specific_data,
            worker_availabilities=worker_availabilities)

        # Extract the results and convert into the desired output format
        for items in line_allocation:
            if items['Resource'] in allocation_list:
                temp_worker_allocation_data = allocation_list[items['Resource']]
                worker_allocation_data = []
                for i in temp_worker_allocation_data:
                    # append 100000 to stick to the given worker list format but can be removed later
                    worker_allocation_data.append(i + 100000)
                items['workers'] = worker_allocation_data
            else:
                items['workers'] = []

        for items in line_allocation:
            items['Resource'] = line_mapping[items['Resource']]

        return {
            "message": "Successfully performed worker allocation operation.",
            "solution": line_allocation  # Final result
        }, 200


@api.route('/order-to-line')
class WorkerAssignment(Resource):
    @api.doc('order_scheduling')
    @api.expect(request_body_model, validate=True)
    @api.response(200, 'Successfully processed the planning data.')
    @api.response(400, 'Invalid input data.')
    def post(self):
        # Here you would process the planning data
        data = request.json
        print(data)  # This will print the received JSON data to the console

        # Accessing specific fields from the JSON
        start_time_timestamp = data.get('start_time_timestamp')
        print(start_time_timestamp)
        # Accessing order_data
        order_data = data.get('order_data')
        print(order_data)
        # Store the values for each order in order_list like: (duration [h], line_id, priority, due_date [h])
        order_list = []
        # order_dict to uniquely identify the order based on id
        order_dict = {}
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []  # if order is not in the dictionary we create an enry for it
            priority = 0
            if not order['priority']:
                priority = 1
            # Convert the time into seconds format
            deadline_timestamp = int(
                time.mktime(datetime.strptime(order["deadline"], "%Y-%m-%d").timetuple())
            )
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to hours
            duration_hours = duration_seconds / 3600

            # Use the geometry_line_mapping to identify the available lines for the given order
            geometry_line_mapping = data.get('geometry_line_mapping')
            line_list = []
            for geometry in geometry_line_mapping:
                if geometry['geometry'] == order['geometry']:
                    line_list.append(geometry['main_line'])  # add the possible line for the order to the line list.
                    line_list.extend(geometry['alternative_lines'])

            # Iterate through the throughput mapping list and find the entry for which
            # line and geometry match with the order
            throughput_mapping_list = data.get('throughput_mapping')
            for throughput_mapping in throughput_mapping_list:
                temp = 0
                for line in line_list:
                    if throughput_mapping['line'] == line and throughput_mapping['geometry'] == order['geometry']:
                        duration = ((5 * order['mold']) + (
                                15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        # add the entry (duration [h], line_id, priority, due_date [h])
                        # to the order_dict for the given order
                        order_dict[order['order']].append(
                            (math.ceil(duration), temp, priority, math.ceil(duration_hours)))
                        temp = temp + 1
        for key, value in order_dict.items():
            order_list.append(value)

        # Replace the hard coded EXAMPLE_ORDER_INSTANCE with the order list generated in the previous step
        # and call the function main() from cp_order_to_line
        solution_df = main(order_list=order_list)
        print(solution_df.head(n=30))
        solution_dict = solution_df.to_dict(orient='records')
        print(order_list)
        return {
            "message": "Successfully performed order-to-line operation.",
            "solution": solution_dict  # Include solution_dict in the response
        }, 200


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
