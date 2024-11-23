import math

from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
import time
from datetime import datetime

from order_scheduling.cp_order_to_line import main

app = Flask(__name__)
api = Api(app, version="1.0.0", title="Example API",
          description="API documentation for processing planning data, with each field as a parameter.")

# Define the models for complex parameter types
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
    'alternative_lines': fields.List(fields.String, required=True, example=["line 17"], description="Alternative lines"),
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
    'medical_condition': fields.Boolean(required=True, example=True, description="Indicates if medical conditions exist"),
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
@api.route('/worker-assignment')
class WorkerAssignment(Resource):
    @api.doc('worker_allocation')
    @api.expect(request_body_model, validate=True)
    @api.response(200, 'Successfully processed the planning data.')
    @api.response(400, 'Invalid input data.')
    def post(self):
        # Here you would process the planning data
        data = request.json
        print(data)  # This will print the received JSON data to the console

        # Example of accessing specific fields from the JSON
        start_time_timestamp = data.get('start_time_timestamp')
        print(start_time_timestamp)
        order_data = data.get('order_data')
        print(order_data)
        order_list = []
        order_dict = {}
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []
            priority = 0
            if not order['priority']:
                priority = 1
            deadline_timestamp = int(
                time.mktime(datetime.strptime(order["deadline"], "%Y-%m-%d").timetuple())
            )
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to hours
            duration_hours = duration_seconds / 3600
            geometry_line_mapping = data.get('geometry_line_mapping')
            line_list = []
            for geometry in geometry_line_mapping:
                if geometry['geometry'] == order['geometry']:
                    line_list.append(geometry['main_line'])
                    line_list.extend(geometry['alternative_lines'])
            throughput_mapping_list = data.get('throughput_mapping')
            for throughput_mapping in throughput_mapping_list:
                temp = 0
                for line in line_list:
                    if throughput_mapping['line'] == line and throughput_mapping['geometry'] == order['geometry']:
                        duration = ((5 * order['mold']) + (
                                    15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        order_dict[order['order']].append(
                            (math.ceil(duration), temp, priority, math.ceil(duration_hours)))
                        temp = temp + 1
        for key, value in order_dict.items():
            order_list.append(value)
        solution_df = main(order_list=order_list)
        print(solution_df.head(n=30))
        solution_dict = solution_df.to_dict(orient='records')
        print(order_list)
        return {
            "message": "Successfully performed worker allocation operation.",
            "solution": solution_dict  # Include solution_dict in the response
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

        # Example of accessing specific fields from the JSON
        start_time_timestamp = data.get('start_time_timestamp')
        print(start_time_timestamp)
        order_data = data.get('order_data')
        print(order_data)
        order_list = []
        order_dict = {}
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []
            priority = 0
            if not order['priority']:
                priority = 1
            deadline_timestamp = int(
                time.mktime(datetime.strptime(order["deadline"], "%Y-%m-%d").timetuple())
            )
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to hours
            duration_hours = duration_seconds / 3600
            geometry_line_mapping = data.get('geometry_line_mapping')
            line_list = []
            for geometry in geometry_line_mapping:
                if geometry['geometry'] == order['geometry']:
                    line_list.append(geometry['main_line'])
                    line_list.extend(geometry['alternative_lines'])
            throughput_mapping_list = data.get('throughput_mapping')
            for throughput_mapping in throughput_mapping_list:
                temp = 0
                for line in line_list:
                    if throughput_mapping['line'] == line and throughput_mapping['geometry'] == order['geometry']:
                        duration = ((5 * order['mold']) + (15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        order_dict[order['order']].append((math.ceil(duration), temp, priority, math.ceil(duration_hours)))
                        temp = temp + 1
        for key, value in order_dict.items():
            order_list.append(value)
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
