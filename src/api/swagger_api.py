import math

from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
import time
from datetime import datetime
import warnings

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
    'deadline': fields.Float(required=True, example=1693605540.0, description="Order deadline (YYYY-MM-DD)"),
    'priority': fields.Boolean(required=True, example=True, description="Order priority"),
    'mold': fields.Integer(required=True, example=4, description="Mold type")
})

geometry_line_mapping_model = api.model('GeometryLineMapping', {
    'geometry': fields.String(required=True, example="geo1", description="Geometry name"),
    'main_line': fields.Integer(required=True, example= 7, description="Main production line"),
    'alternative_lines': fields.List(fields.Integer, required=True, example=[17],
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
    'from_timestamp': fields.Float(required=True, example=234, description="Start time in Unix timestamp"),
    'end_timestamp': fields.Float(required=True, example=123123, description="End time in Unix timestamp"),
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
    'start_time_stamp': fields.Float(required=True, example=1630454400.0,
                                           description="Start time of the planning window in Unix timestamp format."),
    'order-data': fields.List(fields.Nested(order_data_model), required=True,
                              description="List of orders with their details.",
                              example=[
        {
            "order": "SEV - 35",
            "geometry": "1340746080/8080",
            "amount": 4120,
            "deadline": 1693605540.0,
            "mold": 4,
            "priority": False
        },
        {
            "order": "SEV - 35",
            "geometry": "468634640",
            "amount": 450,
            "deadline": 1693605540.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "CAS - 35",
            "geometry": "505469840/505518110",
            "amount": 1165,
            "deadline": 1693605540.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1344640080/4711080",
            "amount": 9890,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "533908540",
            "amount": 6800,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "MIR - 36",
            "geometry": "521392800/970",
            "amount": 2610,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1340750080",
            "amount": 11750,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1342266080",
            "amount": 3070,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "501527470",
            "amount": 4250,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1343314080",
            "amount": 2940,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "531359140",
            "amount": 2600,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1343327080",
            "amount": 3440,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "534259180",
            "amount": 5850,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "534259080",
            "amount": 6560,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "MIR - 36",
            "geometry": "522216940",
            "amount": 2220,
            "deadline": 1694210340.0,
            "mold": 4,
            "priority": False
        },
        {
            "order": "MIR - 36",
            "geometry": "521402240",
            "amount": 1920,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1342236080",
            "amount": 7350,
            "deadline": 1694210340.0,
            "mold": 4,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1342238080",
            "amount": 2350,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "1340746080/8080",
            "amount": 6780,
            "deadline": 1694210340.0,
            "mold": 4,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "468634640",
            "amount": 9000,
            "deadline": 1694210340.0,
            "mold": 6,
            "priority": False
        },
        {
            "order": "SEV - 36",
            "geometry": "531359170",
            "amount": 4000,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        },
        {
            "order": "CAS - 36",
            "geometry": "505597580",
            "amount": 1500,
            "deadline": 1694210340.0,
            "mold": 5,
            "priority": False
        }
    ]),
    'geometry_line_mapping': fields.List(fields.Nested(geometry_line_mapping_model), required=True,
                                         description="Mapping of geometries to production lines.",
                                         example=[
        {
            "geometry": "1340746080/8080",
            "main_line": 17,
            "alternative_lines": [],
            "number_of_workers": 4
        },
        {
            "geometry": "468634640",
            "main_line": 20,
            "alternative_lines": [
                16,
                21
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "505469840/505518110",
            "main_line": 17,
            "alternative_lines": [
                18
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1344640080/4711080",
            "main_line": 17,
            "alternative_lines": [
                3404
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "533908540",
            "main_line": 24,
            "alternative_lines": [
                20
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "521392800/970",
            "main_line": 17,
            "alternative_lines": [
                18
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1340750080",
            "main_line": 20,
            "alternative_lines": [
                24
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1342266080",
            "main_line": 20,
            "alternative_lines": [],
            "number_of_workers": 4
        },
        {
            "geometry": "501527470",
            "main_line": 24,
            "alternative_lines": [
                19
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1343314080",
            "main_line": 17,
            "alternative_lines": [
                19
            ],
            "number_of_workers": 6
        },
        {
            "geometry": "531359140",
            "main_line": 17,
            "alternative_lines": [
                18
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1343327080",
            "main_line": 20,
            "alternative_lines": [],
            "number_of_workers": 4
        },
        {
            "geometry": "534259180",
            "main_line": 24,
            "alternative_lines": [
                20
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "534259080",
            "main_line": 24,
            "alternative_lines": [
                20
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "522216940",
            "main_line": 17,
            "alternative_lines": [
                18
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "521402240",
            "main_line": 17,
            "alternative_lines": [
                18
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1342236080",
            "main_line": 20,
            "alternative_lines": [
                16
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "1342238080",
            "main_line": 20,
            "alternative_lines": [
                24
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "531359170",
            "main_line": 24,
            "alternative_lines": [
                20
            ],
            "number_of_workers": 4
        },
        {
            "geometry": "505597580",
            "main_line": 24,
            "alternative_lines": [],
            "number_of_workers": 4
        }
    ]),
    'throughput_mapping': fields.List(fields.Nested(throughput_mapping_model), required=True,
                                      description="List of throughput mappings for each line.",
                                      example=[
        {
            "line": "Line 17",
            "geometry": "1340746080/8080",
            "throughput": 350
        },
        {
            "line": "Line 20",
            "geometry": "468634640",
            "throughput": 0
        },
        {
            "line": "Line 17",
            "geometry": "505469840/505518110",
            "throughput": 360
        },
        {
            "line": "Line 17",
            "geometry": "1344640080/4711080",
            "throughput": 440
        },
        {
            "line": "Line 24",
            "geometry": "533908540",
            "throughput": 540
        },
        {
            "line": "Line 20",
            "geometry": "521392800/970",
            "throughput": 300
        },
        {
            "line": "Line 20",
            "geometry": "1340750080",
            "throughput": 550
        },
        {
            "line": "Line 24",
            "geometry": "1340750080",
            "throughput": 0
        },
        {
            "line": "Line 20",
            "geometry": "1342266080",
            "throughput": 420
        },
        {
            "line": "Line 24",
            "geometry": "501527470",
            "throughput": 540
        },
        {
            "line": "Line 17",
            "geometry": "1343314080",
            "throughput": 323
        },
        {
            "line": "Line 17",
            "geometry": "531359140",
            "throughput": 420
        },
        {
            "line": "Line 20",
            "geometry": "1343327080",
            "throughput": 400
        },
        {
            "line": "Line 24",
            "geometry": "534259180",
            "throughput": 550
        },
        {
            "line": "Line 24",
            "geometry": "534259080",
            "throughput": 550
        },
        {
            "line": "Line 17",
            "geometry": "522216940",
            "throughput": 300
        },
        {
            "line": "Line 17",
            "geometry": "521402240",
            "throughput": 300
        },
        {
            "line": "Line 20",
            "geometry": "1342236080",
            "throughput": 400
        },
        {
            "line": "Line 20",
            "geometry": "1342238080",
            "throughput": 0
        },
        {
            "line": "Line 24",
            "geometry": "531359170",
            "throughput": 0
        },
        {
            "line": "Line 20",
            "geometry": "531359170",
            "throughput": 515
        },
        {
            "line": "Line 24",
            "geometry": "505597580",
            "throughput": 380
        }
    ]),
    'human_factor': fields.List(fields.Nested(human_factor_model), required=True,
                                description="Human factor details for workers and geometries.",
                                example=[
        {
            "geometry": "1340746080/8080",
            "preference": 0.64,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15014209"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.74,
            "resilience": 0.68,
            "medical_condition": False,
            "experience": 0.09,
            "worker": "15014212"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.42,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.51,
            "worker": "15014727"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.03,
            "resilience": 0.2,
            "medical_condition": True,
            "experience": 0.54,
            "worker": "15014729"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.22,
            "resilience": 0.59,
            "medical_condition": True,
            "experience": 0.01,
            "worker": "15014964"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.81,
            "resilience": 0.7,
            "medical_condition": True,
            "experience": 0.16,
            "worker": "15015125"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.96,
            "resilience": 0.34,
            "medical_condition": True,
            "experience": 0.1,
            "worker": "15015261"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.85,
            "resilience": 0.6,
            "medical_condition": True,
            "experience": 0.73,
            "worker": "15015261"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.54,
            "resilience": 0.97,
            "medical_condition": True,
            "experience": 0.55,
            "worker": "15015264"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.83,
            "resilience": 0.62,
            "medical_condition": False,
            "experience": 0.58,
            "worker": "15015349"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.7,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.29,
            "worker": "15015351"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.08,
            "resilience": 0.23,
            "medical_condition": True,
            "experience": 0.28,
            "worker": "15015351"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.64,
            "resilience": 0.36,
            "medical_condition": True,
            "experience": 0.21,
            "worker": "15015514"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.27,
            "resilience": 0.94,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15015568"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.17,
            "resilience": 0.73,
            "medical_condition": True,
            "experience": 0.38,
            "worker": "15015650"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.99,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.68,
            "worker": "15015652"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.84,
            "resilience": 0.78,
            "medical_condition": True,
            "experience": 0.03,
            "worker": "15015653"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.32,
            "resilience": 0.27,
            "medical_condition": True,
            "experience": 0.94,
            "worker": "15004479"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.88,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.4,
            "worker": "15016112"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.91,
            "resilience": 0.46,
            "medical_condition": True,
            "experience": 0.25,
            "worker": "15016591"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.56,
            "resilience": 0.26,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15016633"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.4,
            "resilience": 0.22,
            "medical_condition": False,
            "experience": 0.51,
            "worker": "15017049"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.09,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.63,
            "worker": "15004696"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.79,
            "resilience": 0.42,
            "medical_condition": True,
            "experience": 0.38,
            "worker": "15009882"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 1.0,
            "resilience": 0.53,
            "medical_condition": False,
            "experience": 0.86,
            "worker": "15009935"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.01,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.54,
            "worker": "15040627"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.27,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.43,
            "worker": "15028961"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.45,
            "resilience": 0.95,
            "medical_condition": False,
            "experience": 0.26,
            "worker": "15028786"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.5,
            "resilience": 0.18,
            "medical_condition": False,
            "experience": 0.87,
            "worker": "15028790"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.3,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.15,
            "worker": "15028837"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.76,
            "resilience": 0.54,
            "medical_condition": True,
            "experience": 0.53,
            "worker": "15028914"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.0,
            "resilience": 0.32,
            "medical_condition": True,
            "experience": 0.93,
            "worker": "15097932"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.88,
            "resilience": 0.83,
            "medical_condition": True,
            "experience": 0.06,
            "worker": "15013130"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.88,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.49,
            "worker": "15013367"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.07,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.13,
            "worker": "15013533"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.48,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.87,
            "worker": "15013870"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.42,
            "resilience": 0.21,
            "medical_condition": True,
            "experience": 0.73,
            "worker": "15015510"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.2,
            "resilience": 0.31,
            "medical_condition": False,
            "experience": 0.65,
            "worker": "15015554"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.44,
            "resilience": 0.52,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15015610"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.34,
            "resilience": 0.59,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15017042"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.07,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.91,
            "worker": "15004666"
        },
        {
            "geometry": "1340746080/8080",
            "preference": 0.86,
            "resilience": 0.07,
            "medical_condition": True,
            "experience": 0.67,
            "worker": "15020309"
        },
        {
            "geometry": "468634640",
            "preference": 0.21,
            "resilience": 0.13,
            "medical_condition": False,
            "experience": 0.57,
            "worker": "15014209"
        },
        {
            "geometry": "468634640",
            "preference": 0.47,
            "resilience": 0.78,
            "medical_condition": True,
            "experience": 0.19,
            "worker": "15014212"
        },
        {
            "geometry": "468634640",
            "preference": 0.1,
            "resilience": 0.43,
            "medical_condition": True,
            "experience": 0.47,
            "worker": "15014727"
        },
        {
            "geometry": "468634640",
            "preference": 0.73,
            "resilience": 0.67,
            "medical_condition": False,
            "experience": 0.1,
            "worker": "15014729"
        },
        {
            "geometry": "468634640",
            "preference": 0.4,
            "resilience": 0.34,
            "medical_condition": False,
            "experience": 0.25,
            "worker": "15014964"
        },
        {
            "geometry": "468634640",
            "preference": 0.19,
            "resilience": 0.45,
            "medical_condition": True,
            "experience": 0.28,
            "worker": "15015125"
        },
        {
            "geometry": "468634640",
            "preference": 0.25,
            "resilience": 0.92,
            "medical_condition": True,
            "experience": 0.86,
            "worker": "15015261"
        },
        {
            "geometry": "468634640",
            "preference": 0.55,
            "resilience": 0.05,
            "medical_condition": False,
            "experience": 0.84,
            "worker": "15015261"
        },
        {
            "geometry": "468634640",
            "preference": 0.97,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.17,
            "worker": "15015264"
        },
        {
            "geometry": "468634640",
            "preference": 0.49,
            "resilience": 0.21,
            "medical_condition": True,
            "experience": 0.06,
            "worker": "15015349"
        },
        {
            "geometry": "468634640",
            "preference": 0.38,
            "resilience": 0.99,
            "medical_condition": True,
            "experience": 0.78,
            "worker": "15015351"
        },
        {
            "geometry": "468634640",
            "preference": 0.46,
            "resilience": 0.42,
            "medical_condition": False,
            "experience": 1.0,
            "worker": "15015351"
        },
        {
            "geometry": "468634640",
            "preference": 0.56,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.3,
            "worker": "15015514"
        },
        {
            "geometry": "468634640",
            "preference": 0.97,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15015568"
        },
        {
            "geometry": "468634640",
            "preference": 0.06,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.85,
            "worker": "15015650"
        },
        {
            "geometry": "468634640",
            "preference": 0.16,
            "resilience": 0.96,
            "medical_condition": True,
            "experience": 0.19,
            "worker": "15015652"
        },
        {
            "geometry": "468634640",
            "preference": 0.6,
            "resilience": 0.68,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15015653"
        },
        {
            "geometry": "468634640",
            "preference": 0.89,
            "resilience": 0.25,
            "medical_condition": True,
            "experience": 0.62,
            "worker": "15004479"
        },
        {
            "geometry": "468634640",
            "preference": 0.42,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.93,
            "worker": "15016112"
        },
        {
            "geometry": "468634640",
            "preference": 0.2,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.4,
            "worker": "15016591"
        },
        {
            "geometry": "468634640",
            "preference": 0.67,
            "resilience": 0.3,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15016633"
        },
        {
            "geometry": "468634640",
            "preference": 0.07,
            "resilience": 0.46,
            "medical_condition": False,
            "experience": 1.0,
            "worker": "15017049"
        },
        {
            "geometry": "468634640",
            "preference": 0.07,
            "resilience": 0.21,
            "medical_condition": True,
            "experience": 0.93,
            "worker": "15004696"
        },
        {
            "geometry": "468634640",
            "preference": 0.88,
            "resilience": 0.88,
            "medical_condition": True,
            "experience": 0.16,
            "worker": "15009882"
        },
        {
            "geometry": "468634640",
            "preference": 0.83,
            "resilience": 0.7,
            "medical_condition": True,
            "experience": 0.99,
            "worker": "15009935"
        },
        {
            "geometry": "468634640",
            "preference": 0.65,
            "resilience": 0.01,
            "medical_condition": True,
            "experience": 0.3,
            "worker": "15040627"
        },
        {
            "geometry": "468634640",
            "preference": 0.66,
            "resilience": 0.94,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15028961"
        },
        {
            "geometry": "468634640",
            "preference": 0.11,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.6,
            "worker": "15028786"
        },
        {
            "geometry": "468634640",
            "preference": 0.72,
            "resilience": 0.2,
            "medical_condition": True,
            "experience": 0.26,
            "worker": "15028790"
        },
        {
            "geometry": "468634640",
            "preference": 0.49,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.09,
            "worker": "15028837"
        },
        {
            "geometry": "468634640",
            "preference": 0.42,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.77,
            "worker": "15028914"
        },
        {
            "geometry": "468634640",
            "preference": 0.64,
            "resilience": 0.26,
            "medical_condition": True,
            "experience": 0.55,
            "worker": "15097932"
        },
        {
            "geometry": "468634640",
            "preference": 0.43,
            "resilience": 0.01,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15013130"
        },
        {
            "geometry": "468634640",
            "preference": 0.9,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.58,
            "worker": "15013367"
        },
        {
            "geometry": "468634640",
            "preference": 0.15,
            "resilience": 0.13,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15013533"
        },
        {
            "geometry": "468634640",
            "preference": 0.8,
            "resilience": 0.86,
            "medical_condition": False,
            "experience": 0.21,
            "worker": "15013870"
        },
        {
            "geometry": "468634640",
            "preference": 0.25,
            "resilience": 0.1,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15015510"
        },
        {
            "geometry": "468634640",
            "preference": 0.41,
            "resilience": 0.62,
            "medical_condition": True,
            "experience": 0.93,
            "worker": "15015554"
        },
        {
            "geometry": "468634640",
            "preference": 0.86,
            "resilience": 0.98,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15015610"
        },
        {
            "geometry": "468634640",
            "preference": 0.02,
            "resilience": 0.74,
            "medical_condition": True,
            "experience": 0.93,
            "worker": "15017042"
        },
        {
            "geometry": "468634640",
            "preference": 0.8,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15004666"
        },
        {
            "geometry": "468634640",
            "preference": 0.79,
            "resilience": 0.11,
            "medical_condition": False,
            "experience": 0.86,
            "worker": "15020309"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.22,
            "resilience": 0.82,
            "medical_condition": True,
            "experience": 0.31,
            "worker": "15014209"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.8,
            "resilience": 0.23,
            "medical_condition": True,
            "experience": 0.19,
            "worker": "15014212"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.33,
            "resilience": 0.86,
            "medical_condition": False,
            "experience": 0.28,
            "worker": "15014727"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.64,
            "resilience": 0.4,
            "medical_condition": False,
            "experience": 0.54,
            "worker": "15014729"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.94,
            "resilience": 0.12,
            "medical_condition": False,
            "experience": 0.18,
            "worker": "15014964"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.96,
            "resilience": 0.27,
            "medical_condition": True,
            "experience": 0.43,
            "worker": "15015125"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.73,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.51,
            "worker": "15015261"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.39,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.71,
            "worker": "15015261"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.0,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.72,
            "worker": "15015264"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.74,
            "resilience": 0.67,
            "medical_condition": True,
            "experience": 0.07,
            "worker": "15015349"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.66,
            "resilience": 0.33,
            "medical_condition": True,
            "experience": 0.85,
            "worker": "15015351"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.72,
            "resilience": 0.3,
            "medical_condition": True,
            "experience": 0.41,
            "worker": "15015351"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.4,
            "resilience": 0.3,
            "medical_condition": True,
            "experience": 0.42,
            "worker": "15015514"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.94,
            "resilience": 0.68,
            "medical_condition": False,
            "experience": 0.62,
            "worker": "15015568"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.3,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.29,
            "worker": "15015650"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.43,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.46,
            "worker": "15015652"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.44,
            "resilience": 0.21,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15015653"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.8,
            "resilience": 0.17,
            "medical_condition": True,
            "experience": 0.52,
            "worker": "15004479"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.63,
            "resilience": 0.34,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15016112"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.67,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.02,
            "worker": "15016591"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.24,
            "resilience": 0.48,
            "medical_condition": True,
            "experience": 0.07,
            "worker": "15016633"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.41,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.7,
            "worker": "15017049"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.49,
            "resilience": 0.24,
            "medical_condition": True,
            "experience": 0.01,
            "worker": "15004696"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.75,
            "resilience": 0.77,
            "medical_condition": True,
            "experience": 0.43,
            "worker": "15009882"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.18,
            "resilience": 0.96,
            "medical_condition": True,
            "experience": 0.05,
            "worker": "15009935"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.25,
            "resilience": 0.85,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15040627"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.67,
            "resilience": 0.99,
            "medical_condition": True,
            "experience": 0.95,
            "worker": "15028961"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.89,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15028786"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.83,
            "resilience": 0.55,
            "medical_condition": False,
            "experience": 0.74,
            "worker": "15028790"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.47,
            "resilience": 0.26,
            "medical_condition": True,
            "experience": 0.64,
            "worker": "15028837"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.77,
            "resilience": 0.52,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15028914"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.08,
            "resilience": 0.29,
            "medical_condition": True,
            "experience": 0.32,
            "worker": "15097932"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.54,
            "resilience": 0.14,
            "medical_condition": True,
            "experience": 0.69,
            "worker": "15013130"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.71,
            "resilience": 0.06,
            "medical_condition": True,
            "experience": 0.54,
            "worker": "15013367"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.42,
            "resilience": 0.21,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15013533"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.58,
            "resilience": 0.7,
            "medical_condition": False,
            "experience": 0.77,
            "worker": "15013870"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.38,
            "resilience": 0.01,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15015510"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.85,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15015554"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.55,
            "resilience": 0.6,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15015610"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.44,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.68,
            "worker": "15017042"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.4,
            "resilience": 0.17,
            "medical_condition": True,
            "experience": 0.13,
            "worker": "15004666"
        },
        {
            "geometry": "505469840/505518110",
            "preference": 0.62,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.56,
            "worker": "15020309"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.03,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.46,
            "worker": "15014209"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.05,
            "resilience": 0.38,
            "medical_condition": True,
            "experience": 0.33,
            "worker": "15014212"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.76,
            "resilience": 0.38,
            "medical_condition": True,
            "experience": 0.83,
            "worker": "15014727"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.25,
            "resilience": 0.08,
            "medical_condition": True,
            "experience": 0.54,
            "worker": "15014729"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 1.0,
            "resilience": 0.35,
            "medical_condition": True,
            "experience": 0.78,
            "worker": "15014964"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.65,
            "resilience": 0.75,
            "medical_condition": False,
            "experience": 0.2,
            "worker": "15015125"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.02,
            "resilience": 0.15,
            "medical_condition": True,
            "experience": 0.67,
            "worker": "15015261"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.56,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.77,
            "worker": "15015261"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.17,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.11,
            "worker": "15015264"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.82,
            "resilience": 0.96,
            "medical_condition": True,
            "experience": 0.03,
            "worker": "15015349"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.31,
            "resilience": 0.68,
            "medical_condition": False,
            "experience": 0.4,
            "worker": "15015351"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.72,
            "resilience": 0.08,
            "medical_condition": True,
            "experience": 0.63,
            "worker": "15015351"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.1,
            "resilience": 0.77,
            "medical_condition": False,
            "experience": 0.6,
            "worker": "15015514"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.12,
            "resilience": 0.98,
            "medical_condition": True,
            "experience": 0.35,
            "worker": "15015568"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.43,
            "resilience": 0.37,
            "medical_condition": True,
            "experience": 0.34,
            "worker": "15015650"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.85,
            "resilience": 0.82,
            "medical_condition": True,
            "experience": 0.96,
            "worker": "15015652"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.64,
            "resilience": 0.83,
            "medical_condition": True,
            "experience": 0.44,
            "worker": "15015653"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.73,
            "resilience": 0.97,
            "medical_condition": True,
            "experience": 0.81,
            "worker": "15004479"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.54,
            "resilience": 0.48,
            "medical_condition": True,
            "experience": 0.73,
            "worker": "15016112"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.27,
            "resilience": 0.85,
            "medical_condition": True,
            "experience": 0.09,
            "worker": "15016591"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.88,
            "resilience": 0.24,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15016633"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.38,
            "resilience": 0.03,
            "medical_condition": False,
            "experience": 0.18,
            "worker": "15017049"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.21,
            "resilience": 0.8,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15004696"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.7,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.95,
            "worker": "15009882"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.09,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.76,
            "worker": "15009935"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.69,
            "resilience": 0.65,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15040627"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.09,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.31,
            "worker": "15028961"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.58,
            "resilience": 0.47,
            "medical_condition": True,
            "experience": 0.43,
            "worker": "15028786"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.75,
            "resilience": 0.33,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15028790"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.25,
            "resilience": 0.12,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15028837"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.54,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15028914"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.48,
            "resilience": 0.72,
            "medical_condition": False,
            "experience": 0.52,
            "worker": "15097932"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.28,
            "resilience": 0.1,
            "medical_condition": True,
            "experience": 0.23,
            "worker": "15013130"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.18,
            "resilience": 0.01,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15013367"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.97,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.13,
            "worker": "15013533"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.87,
            "resilience": 0.49,
            "medical_condition": False,
            "experience": 0.57,
            "worker": "15013870"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.47,
            "resilience": 0.44,
            "medical_condition": True,
            "experience": 0.05,
            "worker": "15015510"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.94,
            "resilience": 0.48,
            "medical_condition": True,
            "experience": 0.4,
            "worker": "15015554"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.07,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.15,
            "worker": "15015610"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.56,
            "resilience": 0.3,
            "medical_condition": False,
            "experience": 0.12,
            "worker": "15017042"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.76,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.23,
            "worker": "15004666"
        },
        {
            "geometry": "1344640080/4711080",
            "preference": 0.52,
            "resilience": 0.45,
            "medical_condition": True,
            "experience": 0.86,
            "worker": "15020309"
        },
        {
            "geometry": "533908540",
            "preference": 0.99,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15014209"
        },
        {
            "geometry": "533908540",
            "preference": 0.74,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.21,
            "worker": "15014212"
        },
        {
            "geometry": "533908540",
            "preference": 0.66,
            "resilience": 0.16,
            "medical_condition": True,
            "experience": 0.08,
            "worker": "15014727"
        },
        {
            "geometry": "533908540",
            "preference": 0.0,
            "resilience": 0.45,
            "medical_condition": True,
            "experience": 0.29,
            "worker": "15014729"
        },
        {
            "geometry": "533908540",
            "preference": 0.23,
            "resilience": 0.71,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15014964"
        },
        {
            "geometry": "533908540",
            "preference": 0.69,
            "resilience": 0.92,
            "medical_condition": True,
            "experience": 0.63,
            "worker": "15015125"
        },
        {
            "geometry": "533908540",
            "preference": 0.66,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.54,
            "worker": "15015261"
        },
        {
            "geometry": "533908540",
            "preference": 0.65,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.07,
            "worker": "15015261"
        },
        {
            "geometry": "533908540",
            "preference": 0.17,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.57,
            "worker": "15015264"
        },
        {
            "geometry": "533908540",
            "preference": 0.29,
            "resilience": 0.12,
            "medical_condition": True,
            "experience": 0.7,
            "worker": "15015349"
        },
        {
            "geometry": "533908540",
            "preference": 0.94,
            "resilience": 0.5,
            "medical_condition": True,
            "experience": 0.08,
            "worker": "15015351"
        },
        {
            "geometry": "533908540",
            "preference": 0.04,
            "resilience": 0.43,
            "medical_condition": True,
            "experience": 0.25,
            "worker": "15015351"
        },
        {
            "geometry": "533908540",
            "preference": 0.09,
            "resilience": 0.96,
            "medical_condition": True,
            "experience": 0.58,
            "worker": "15015514"
        },
        {
            "geometry": "533908540",
            "preference": 0.95,
            "resilience": 1.0,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15015568"
        },
        {
            "geometry": "533908540",
            "preference": 0.04,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.65,
            "worker": "15015650"
        },
        {
            "geometry": "533908540",
            "preference": 0.92,
            "resilience": 0.18,
            "medical_condition": True,
            "experience": 0.63,
            "worker": "15015652"
        },
        {
            "geometry": "533908540",
            "preference": 0.49,
            "resilience": 0.09,
            "medical_condition": True,
            "experience": 0.33,
            "worker": "15015653"
        },
        {
            "geometry": "533908540",
            "preference": 0.67,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.69,
            "worker": "15004479"
        },
        {
            "geometry": "533908540",
            "preference": 0.29,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.55,
            "worker": "15016112"
        },
        {
            "geometry": "533908540",
            "preference": 0.45,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.97,
            "worker": "15016591"
        },
        {
            "geometry": "533908540",
            "preference": 0.4,
            "resilience": 0.51,
            "medical_condition": False,
            "experience": 0.66,
            "worker": "15016633"
        },
        {
            "geometry": "533908540",
            "preference": 0.54,
            "resilience": 0.41,
            "medical_condition": True,
            "experience": 0.36,
            "worker": "15017049"
        },
        {
            "geometry": "533908540",
            "preference": 0.76,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.2,
            "worker": "15004696"
        },
        {
            "geometry": "533908540",
            "preference": 0.55,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.7,
            "worker": "15009882"
        },
        {
            "geometry": "533908540",
            "preference": 0.12,
            "resilience": 0.97,
            "medical_condition": True,
            "experience": 0.24,
            "worker": "15009935"
        },
        {
            "geometry": "533908540",
            "preference": 0.16,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.09,
            "worker": "15040627"
        },
        {
            "geometry": "533908540",
            "preference": 0.99,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15028961"
        },
        {
            "geometry": "533908540",
            "preference": 0.83,
            "resilience": 0.5,
            "medical_condition": True,
            "experience": 0.51,
            "worker": "15028786"
        },
        {
            "geometry": "533908540",
            "preference": 0.27,
            "resilience": 0.83,
            "medical_condition": False,
            "experience": 0.24,
            "worker": "15028790"
        },
        {
            "geometry": "533908540",
            "preference": 0.55,
            "resilience": 0.38,
            "medical_condition": False,
            "experience": 0.51,
            "worker": "15028837"
        },
        {
            "geometry": "533908540",
            "preference": 0.88,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15028914"
        },
        {
            "geometry": "533908540",
            "preference": 0.41,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.82,
            "worker": "15097932"
        },
        {
            "geometry": "533908540",
            "preference": 0.28,
            "resilience": 0.3,
            "medical_condition": True,
            "experience": 1.0,
            "worker": "15013130"
        },
        {
            "geometry": "533908540",
            "preference": 0.49,
            "resilience": 0.15,
            "medical_condition": True,
            "experience": 0.35,
            "worker": "15013367"
        },
        {
            "geometry": "533908540",
            "preference": 0.55,
            "resilience": 0.54,
            "medical_condition": True,
            "experience": 0.32,
            "worker": "15013533"
        },
        {
            "geometry": "533908540",
            "preference": 0.19,
            "resilience": 0.7,
            "medical_condition": True,
            "experience": 0.23,
            "worker": "15013870"
        },
        {
            "geometry": "533908540",
            "preference": 0.78,
            "resilience": 0.04,
            "medical_condition": True,
            "experience": 0.71,
            "worker": "15015510"
        },
        {
            "geometry": "533908540",
            "preference": 0.81,
            "resilience": 0.39,
            "medical_condition": True,
            "experience": 0.82,
            "worker": "15015554"
        },
        {
            "geometry": "533908540",
            "preference": 0.98,
            "resilience": 0.5,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15015610"
        },
        {
            "geometry": "533908540",
            "preference": 0.59,
            "resilience": 0.87,
            "medical_condition": False,
            "experience": 0.44,
            "worker": "15017042"
        },
        {
            "geometry": "533908540",
            "preference": 0.53,
            "resilience": 0.46,
            "medical_condition": True,
            "experience": 0.41,
            "worker": "15004666"
        },
        {
            "geometry": "533908540",
            "preference": 0.65,
            "resilience": 0.15,
            "medical_condition": True,
            "experience": 0.97,
            "worker": "15020309"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.34,
            "resilience": 0.69,
            "medical_condition": True,
            "experience": 0.85,
            "worker": "15014209"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.85,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.32,
            "worker": "15014212"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.72,
            "resilience": 0.76,
            "medical_condition": False,
            "experience": 0.04,
            "worker": "15014727"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.07,
            "resilience": 0.63,
            "medical_condition": False,
            "experience": 1.0,
            "worker": "15014729"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.75,
            "resilience": 0.43,
            "medical_condition": True,
            "experience": 0.63,
            "worker": "15014964"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.87,
            "resilience": 0.44,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15015125"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.05,
            "resilience": 0.8,
            "medical_condition": True,
            "experience": 0.37,
            "worker": "15015261"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.15,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15015261"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.17,
            "resilience": 0.08,
            "medical_condition": False,
            "experience": 0.62,
            "worker": "15015264"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.24,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.46,
            "worker": "15015349"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.25,
            "resilience": 0.26,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15015351"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.9,
            "resilience": 0.68,
            "medical_condition": True,
            "experience": 0.44,
            "worker": "15015351"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.35,
            "resilience": 0.59,
            "medical_condition": True,
            "experience": 0.42,
            "worker": "15015514"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.25,
            "resilience": 0.85,
            "medical_condition": True,
            "experience": 0.38,
            "worker": "15015568"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.48,
            "resilience": 0.24,
            "medical_condition": True,
            "experience": 0.57,
            "worker": "15015650"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.99,
            "resilience": 0.3,
            "medical_condition": False,
            "experience": 0.66,
            "worker": "15015652"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.27,
            "resilience": 0.57,
            "medical_condition": True,
            "experience": 0.74,
            "worker": "15015653"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.05,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15004479"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.29,
            "resilience": 0.8,
            "medical_condition": True,
            "experience": 0.35,
            "worker": "15016112"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.64,
            "resilience": 0.62,
            "medical_condition": True,
            "experience": 0.72,
            "worker": "15016591"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.66,
            "resilience": 0.84,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15016633"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.65,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.58,
            "worker": "15017049"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.73,
            "resilience": 0.09,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15004696"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.18,
            "resilience": 0.13,
            "medical_condition": True,
            "experience": 0.97,
            "worker": "15009882"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.53,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.26,
            "worker": "15009935"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.82,
            "resilience": 0.48,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15040627"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.34,
            "resilience": 0.12,
            "medical_condition": False,
            "experience": 0.14,
            "worker": "15028961"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.97,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.98,
            "worker": "15028786"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.97,
            "resilience": 0.8,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15028790"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.01,
            "resilience": 0.54,
            "medical_condition": True,
            "experience": 0.67,
            "worker": "15028837"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.67,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.94,
            "worker": "15028914"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.11,
            "resilience": 0.23,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15097932"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.56,
            "resilience": 0.92,
            "medical_condition": True,
            "experience": 0.06,
            "worker": "15013130"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.82,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.41,
            "worker": "15013367"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.14,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.49,
            "worker": "15013533"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.1,
            "resilience": 0.89,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15013870"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.67,
            "resilience": 0.74,
            "medical_condition": False,
            "experience": 0.42,
            "worker": "15015510"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.74,
            "resilience": 0.15,
            "medical_condition": True,
            "experience": 0.1,
            "worker": "15015554"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.49,
            "resilience": 0.41,
            "medical_condition": False,
            "experience": 0.03,
            "worker": "15015610"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.37,
            "resilience": 0.44,
            "medical_condition": False,
            "experience": 0.86,
            "worker": "15017042"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.1,
            "resilience": 0.69,
            "medical_condition": True,
            "experience": 0.98,
            "worker": "15004666"
        },
        {
            "geometry": "521392800/970",
            "preference": 0.36,
            "resilience": 0.4,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15020309"
        },
        {
            "geometry": "1340750080",
            "preference": 0.85,
            "resilience": 0.45,
            "medical_condition": True,
            "experience": 0.64,
            "worker": "15014209"
        },
        {
            "geometry": "1340750080",
            "preference": 0.6,
            "resilience": 0.02,
            "medical_condition": True,
            "experience": 0.24,
            "worker": "15014212"
        },
        {
            "geometry": "1340750080",
            "preference": 0.13,
            "resilience": 0.56,
            "medical_condition": True,
            "experience": 0.77,
            "worker": "15014727"
        },
        {
            "geometry": "1340750080",
            "preference": 0.21,
            "resilience": 0.22,
            "medical_condition": False,
            "experience": 0.33,
            "worker": "15014729"
        },
        {
            "geometry": "1340750080",
            "preference": 0.15,
            "resilience": 0.9,
            "medical_condition": True,
            "experience": 0.86,
            "worker": "15014964"
        },
        {
            "geometry": "1340750080",
            "preference": 0.14,
            "resilience": 0.13,
            "medical_condition": True,
            "experience": 0.17,
            "worker": "15015125"
        },
        {
            "geometry": "1340750080",
            "preference": 0.66,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15015261"
        },
        {
            "geometry": "1340750080",
            "preference": 0.24,
            "resilience": 0.32,
            "medical_condition": True,
            "experience": 0.05,
            "worker": "15015261"
        },
        {
            "geometry": "1340750080",
            "preference": 0.74,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.48,
            "worker": "15015264"
        },
        {
            "geometry": "1340750080",
            "preference": 0.78,
            "resilience": 0.51,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15015349"
        },
        {
            "geometry": "1340750080",
            "preference": 0.95,
            "resilience": 0.04,
            "medical_condition": True,
            "experience": 0.87,
            "worker": "15015351"
        },
        {
            "geometry": "1340750080",
            "preference": 0.52,
            "resilience": 0.46,
            "medical_condition": False,
            "experience": 0.06,
            "worker": "15015351"
        },
        {
            "geometry": "1340750080",
            "preference": 0.48,
            "resilience": 0.4,
            "medical_condition": True,
            "experience": 0.49,
            "worker": "15015514"
        },
        {
            "geometry": "1340750080",
            "preference": 0.91,
            "resilience": 0.07,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15015568"
        },
        {
            "geometry": "1340750080",
            "preference": 0.07,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.55,
            "worker": "15015650"
        },
        {
            "geometry": "1340750080",
            "preference": 0.33,
            "resilience": 0.99,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15015652"
        },
        {
            "geometry": "1340750080",
            "preference": 0.61,
            "resilience": 0.1,
            "medical_condition": True,
            "experience": 0.85,
            "worker": "15015653"
        },
        {
            "geometry": "1340750080",
            "preference": 0.65,
            "resilience": 0.77,
            "medical_condition": True,
            "experience": 0.22,
            "worker": "15004479"
        },
        {
            "geometry": "1340750080",
            "preference": 0.45,
            "resilience": 0.23,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15016112"
        },
        {
            "geometry": "1340750080",
            "preference": 0.42,
            "resilience": 0.1,
            "medical_condition": True,
            "experience": 0.67,
            "worker": "15016591"
        },
        {
            "geometry": "1340750080",
            "preference": 0.37,
            "resilience": 0.15,
            "medical_condition": False,
            "experience": 0.07,
            "worker": "15016633"
        },
        {
            "geometry": "1340750080",
            "preference": 0.83,
            "resilience": 0.09,
            "medical_condition": True,
            "experience": 0.74,
            "worker": "15017049"
        },
        {
            "geometry": "1340750080",
            "preference": 0.81,
            "resilience": 0.56,
            "medical_condition": True,
            "experience": 0.56,
            "worker": "15004696"
        },
        {
            "geometry": "1340750080",
            "preference": 0.33,
            "resilience": 0.12,
            "medical_condition": True,
            "experience": 0.67,
            "worker": "15009882"
        },
        {
            "geometry": "1340750080",
            "preference": 0.75,
            "resilience": 0.87,
            "medical_condition": True,
            "experience": 0.97,
            "worker": "15009935"
        },
        {
            "geometry": "1340750080",
            "preference": 0.6,
            "resilience": 0.35,
            "medical_condition": True,
            "experience": 0.21,
            "worker": "15040627"
        },
        {
            "geometry": "1340750080",
            "preference": 0.66,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.85,
            "worker": "15028961"
        },
        {
            "geometry": "1340750080",
            "preference": 0.37,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.81,
            "worker": "15028786"
        },
        {
            "geometry": "1340750080",
            "preference": 0.85,
            "resilience": 0.97,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15028790"
        },
        {
            "geometry": "1340750080",
            "preference": 0.64,
            "resilience": 0.03,
            "medical_condition": False,
            "experience": 0.83,
            "worker": "15028837"
        },
        {
            "geometry": "1340750080",
            "preference": 0.27,
            "resilience": 0.18,
            "medical_condition": True,
            "experience": 0.31,
            "worker": "15028914"
        },
        {
            "geometry": "1340750080",
            "preference": 0.34,
            "resilience": 0.01,
            "medical_condition": False,
            "experience": 0.57,
            "worker": "15097932"
        },
        {
            "geometry": "1340750080",
            "preference": 0.4,
            "resilience": 0.14,
            "medical_condition": True,
            "experience": 0.03,
            "worker": "15013130"
        },
        {
            "geometry": "1340750080",
            "preference": 0.75,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.34,
            "worker": "15013367"
        },
        {
            "geometry": "1340750080",
            "preference": 0.37,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.57,
            "worker": "15013533"
        },
        {
            "geometry": "1340750080",
            "preference": 0.08,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.62,
            "worker": "15013870"
        },
        {
            "geometry": "1340750080",
            "preference": 0.67,
            "resilience": 0.27,
            "medical_condition": True,
            "experience": 0.49,
            "worker": "15015510"
        },
        {
            "geometry": "1340750080",
            "preference": 0.44,
            "resilience": 0.27,
            "medical_condition": True,
            "experience": 0.11,
            "worker": "15015554"
        },
        {
            "geometry": "1340750080",
            "preference": 0.43,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.49,
            "worker": "15015610"
        },
        {
            "geometry": "1340750080",
            "preference": 0.67,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.6,
            "worker": "15017042"
        },
        {
            "geometry": "1340750080",
            "preference": 0.01,
            "resilience": 0.3,
            "medical_condition": True,
            "experience": 0.14,
            "worker": "15004666"
        },
        {
            "geometry": "1340750080",
            "preference": 0.26,
            "resilience": 0.33,
            "medical_condition": True,
            "experience": 0.75,
            "worker": "15020309"
        },
        {
            "geometry": "1342266080",
            "preference": 0.18,
            "resilience": 0.38,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15014209"
        },
        {
            "geometry": "1342266080",
            "preference": 0.83,
            "resilience": 0.81,
            "medical_condition": True,
            "experience": 0.86,
            "worker": "15014212"
        },
        {
            "geometry": "1342266080",
            "preference": 0.04,
            "resilience": 0.02,
            "medical_condition": False,
            "experience": 0.86,
            "worker": "15014727"
        },
        {
            "geometry": "1342266080",
            "preference": 0.58,
            "resilience": 0.57,
            "medical_condition": True,
            "experience": 0.42,
            "worker": "15014729"
        },
        {
            "geometry": "1342266080",
            "preference": 0.12,
            "resilience": 0.02,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15014964"
        },
        {
            "geometry": "1342266080",
            "preference": 0.62,
            "resilience": 0.83,
            "medical_condition": False,
            "experience": 0.09,
            "worker": "15015125"
        },
        {
            "geometry": "1342266080",
            "preference": 0.84,
            "resilience": 0.24,
            "medical_condition": True,
            "experience": 0.52,
            "worker": "15015261"
        },
        {
            "geometry": "1342266080",
            "preference": 0.4,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.33,
            "worker": "15015261"
        },
        {
            "geometry": "1342266080",
            "preference": 0.17,
            "resilience": 0.51,
            "medical_condition": True,
            "experience": 0.51,
            "worker": "15015264"
        },
        {
            "geometry": "1342266080",
            "preference": 0.91,
            "resilience": 0.35,
            "medical_condition": True,
            "experience": 0.82,
            "worker": "15015349"
        },
        {
            "geometry": "1342266080",
            "preference": 0.82,
            "resilience": 0.24,
            "medical_condition": True,
            "experience": 0.2,
            "worker": "15015351"
        },
        {
            "geometry": "1342266080",
            "preference": 0.6,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.18,
            "worker": "15015351"
        },
        {
            "geometry": "1342266080",
            "preference": 0.77,
            "resilience": 0.49,
            "medical_condition": True,
            "experience": 0.76,
            "worker": "15015514"
        },
        {
            "geometry": "1342266080",
            "preference": 0.45,
            "resilience": 0.92,
            "medical_condition": True,
            "experience": 0.64,
            "worker": "15015568"
        },
        {
            "geometry": "1342266080",
            "preference": 0.62,
            "resilience": 0.86,
            "medical_condition": True,
            "experience": 0.15,
            "worker": "15015650"
        },
        {
            "geometry": "1342266080",
            "preference": 0.07,
            "resilience": 0.44,
            "medical_condition": True,
            "experience": 0.27,
            "worker": "15015652"
        },
        {
            "geometry": "1342266080",
            "preference": 0.06,
            "resilience": 0.51,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15015653"
        },
        {
            "geometry": "1342266080",
            "preference": 0.06,
            "resilience": 0.83,
            "medical_condition": True,
            "experience": 0.86,
            "worker": "15004479"
        },
        {
            "geometry": "1342266080",
            "preference": 0.86,
            "resilience": 0.62,
            "medical_condition": True,
            "experience": 0.46,
            "worker": "15016112"
        },
        {
            "geometry": "1342266080",
            "preference": 0.55,
            "resilience": 0.79,
            "medical_condition": False,
            "experience": 0.45,
            "worker": "15016591"
        },
        {
            "geometry": "1342266080",
            "preference": 0.81,
            "resilience": 0.65,
            "medical_condition": True,
            "experience": 0.48,
            "worker": "15016633"
        },
        {
            "geometry": "1342266080",
            "preference": 0.15,
            "resilience": 0.06,
            "medical_condition": True,
            "experience": 0.9,
            "worker": "15017049"
        },
        {
            "geometry": "1342266080",
            "preference": 0.34,
            "resilience": 0.71,
            "medical_condition": True,
            "experience": 0.17,
            "worker": "15004696"
        },
        {
            "geometry": "1342266080",
            "preference": 0.25,
            "resilience": 0.44,
            "medical_condition": True,
            "experience": 0.52,
            "worker": "15009882"
        },
        {
            "geometry": "1342266080",
            "preference": 0.16,
            "resilience": 0.37,
            "medical_condition": True,
            "experience": 0.41,
            "worker": "15009935"
        },
        {
            "geometry": "1342266080",
            "preference": 0.34,
            "resilience": 0.6,
            "medical_condition": True,
            "experience": 0.65,
            "worker": "15040627"
        },
        {
            "geometry": "1342266080",
            "preference": 0.07,
            "resilience": 0.09,
            "medical_condition": True,
            "experience": 0.28,
            "worker": "15028961"
        },
        {
            "geometry": "1342266080",
            "preference": 0.72,
            "resilience": 0.66,
            "medical_condition": False,
            "experience": 0.87,
            "worker": "15028786"
        },
        {
            "geometry": "1342266080",
            "preference": 0.33,
            "resilience": 0.58,
            "medical_condition": True,
            "experience": 0.35,
            "worker": "15028790"
        },
        {
            "geometry": "1342266080",
            "preference": 0.97,
            "resilience": 0.7,
            "medical_condition": True,
            "experience": 0.6,
            "worker": "15028837"
        },
        {
            "geometry": "1342266080",
            "preference": 0.94,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15028914"
        },
        {
            "geometry": "1342266080",
            "preference": 0.81,
            "resilience": 0.67,
            "medical_condition": True,
            "experience": 0.74,
            "worker": "15097932"
        },
        {
            "geometry": "1342266080",
            "preference": 0.69,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.42,
            "worker": "15013130"
        },
        {
            "geometry": "1342266080",
            "preference": 0.36,
            "resilience": 0.36,
            "medical_condition": True,
            "experience": 0.21,
            "worker": "15013367"
        },
        {
            "geometry": "1342266080",
            "preference": 0.95,
            "resilience": 0.49,
            "medical_condition": True,
            "experience": 0.14,
            "worker": "15013533"
        },
        {
            "geometry": "1342266080",
            "preference": 0.08,
            "resilience": 0.84,
            "medical_condition": True,
            "experience": 0.77,
            "worker": "15013870"
        },
        {
            "geometry": "1342266080",
            "preference": 0.84,
            "resilience": 0.88,
            "medical_condition": True,
            "experience": 0.34,
            "worker": "15015510"
        },
        {
            "geometry": "1342266080",
            "preference": 0.77,
            "resilience": 0.13,
            "medical_condition": True,
            "experience": 0.16,
            "worker": "15015554"
        },
        {
            "geometry": "1342266080",
            "preference": 0.83,
            "resilience": 0.77,
            "medical_condition": True,
            "experience": 0.17,
            "worker": "15015610"
        },
        {
            "geometry": "1342266080",
            "preference": 0.44,
            "resilience": 0.41,
            "medical_condition": True,
            "experience": 0.24,
            "worker": "15017042"
        },
        {
            "geometry": "1342266080",
            "preference": 0.44,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15004666"
        },
        {
            "geometry": "1342266080",
            "preference": 0.53,
            "resilience": 0.31,
            "medical_condition": True,
            "experience": 0.47,
            "worker": "15020309"
        },
        {
            "geometry": "501527470",
            "preference": 0.84,
            "resilience": 0.37,
            "medical_condition": False,
            "experience": 0.98,
            "worker": "15014209"
        },
        {
            "geometry": "501527470",
            "preference": 0.46,
            "resilience": 0.28,
            "medical_condition": True,
            "experience": 0.53,
            "worker": "15014212"
        },
        {
            "geometry": "501527470",
            "preference": 0.97,
            "resilience": 0.82,
            "medical_condition": True,
            "experience": 0.14,
            "worker": "15014727"
        },
        {
            "geometry": "501527470",
            "preference": 0.25,
            "resilience": 0.64,
            "medical_condition": False,
            "experience": 0.55,
            "worker": "15014729"
        },
        {
            "geometry": "501527470",
            "preference": 0.1,
            "resilience": 0.85,
            "medical_condition": False,
            "experience": 0.29,
            "worker": "15014964"
        },
        {
            "geometry": "501527470",
            "preference": 0.76,
            "resilience": 0.27,
            "medical_condition": False,
            "experience": 0.15,
            "worker": "15015125"
        },
        {
            "geometry": "501527470",
            "preference": 0.44,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.45,
            "worker": "15015261"
        },
        {
            "geometry": "501527470",
            "preference": 0.35,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15015261"
        },
        {
            "geometry": "501527470",
            "preference": 0.24,
            "resilience": 0.99,
            "medical_condition": True,
            "experience": 0.03,
            "worker": "15015264"
        },
        {
            "geometry": "501527470",
            "preference": 0.93,
            "resilience": 0.84,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15015349"
        },
        {
            "geometry": "501527470",
            "preference": 0.14,
            "resilience": 0.29,
            "medical_condition": True,
            "experience": 0.7,
            "worker": "15015351"
        },
        {
            "geometry": "501527470",
            "preference": 0.14,
            "resilience": 0.71,
            "medical_condition": True,
            "experience": 0.01,
            "worker": "15015351"
        },
        {
            "geometry": "501527470",
            "preference": 0.08,
            "resilience": 0.26,
            "medical_condition": True,
            "experience": 0.55,
            "worker": "15015514"
        },
        {
            "geometry": "501527470",
            "preference": 0.73,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.29,
            "worker": "15015568"
        },
        {
            "geometry": "501527470",
            "preference": 0.3,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15015650"
        },
        {
            "geometry": "501527470",
            "preference": 0.46,
            "resilience": 0.11,
            "medical_condition": False,
            "experience": 0.6,
            "worker": "15015652"
        },
        {
            "geometry": "501527470",
            "preference": 0.02,
            "resilience": 0.52,
            "medical_condition": True,
            "experience": 0.14,
            "worker": "15015653"
        },
        {
            "geometry": "501527470",
            "preference": 0.43,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.42,
            "worker": "15004479"
        },
        {
            "geometry": "501527470",
            "preference": 0.66,
            "resilience": 0.09,
            "medical_condition": False,
            "experience": 0.07,
            "worker": "15016112"
        },
        {
            "geometry": "501527470",
            "preference": 0.53,
            "resilience": 0.51,
            "medical_condition": False,
            "experience": 0.55,
            "worker": "15016591"
        },
        {
            "geometry": "501527470",
            "preference": 0.39,
            "resilience": 0.47,
            "medical_condition": True,
            "experience": 0.98,
            "worker": "15016633"
        },
        {
            "geometry": "501527470",
            "preference": 0.25,
            "resilience": 0.02,
            "medical_condition": True,
            "experience": 0.34,
            "worker": "15017049"
        },
        {
            "geometry": "501527470",
            "preference": 0.73,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.74,
            "worker": "15004696"
        },
        {
            "geometry": "501527470",
            "preference": 0.33,
            "resilience": 0.04,
            "medical_condition": True,
            "experience": 0.81,
            "worker": "15009882"
        },
        {
            "geometry": "501527470",
            "preference": 0.18,
            "resilience": 0.78,
            "medical_condition": True,
            "experience": 0.7,
            "worker": "15009935"
        },
        {
            "geometry": "501527470",
            "preference": 0.63,
            "resilience": 0.81,
            "medical_condition": True,
            "experience": 0.78,
            "worker": "15040627"
        },
        {
            "geometry": "501527470",
            "preference": 0.46,
            "resilience": 0.29,
            "medical_condition": True,
            "experience": 0.2,
            "worker": "15028961"
        },
        {
            "geometry": "501527470",
            "preference": 0.04,
            "resilience": 0.93,
            "medical_condition": True,
            "experience": 0.99,
            "worker": "15028786"
        },
        {
            "geometry": "501527470",
            "preference": 0.54,
            "resilience": 0.25,
            "medical_condition": True,
            "experience": 0.19,
            "worker": "15028790"
        },
        {
            "geometry": "501527470",
            "preference": 0.36,
            "resilience": 0.78,
            "medical_condition": False,
            "experience": 0.33,
            "worker": "15028837"
        },
        {
            "geometry": "501527470",
            "preference": 0.12,
            "resilience": 0.37,
            "medical_condition": False,
            "experience": 0.74,
            "worker": "15028914"
        },
        {
            "geometry": "501527470",
            "preference": 0.89,
            "resilience": 0.39,
            "medical_condition": False,
            "experience": 0.5,
            "worker": "15097932"
        },
        {
            "geometry": "501527470",
            "preference": 0.5,
            "resilience": 0.92,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15013130"
        },
        {
            "geometry": "501527470",
            "preference": 0.73,
            "resilience": 0.08,
            "medical_condition": True,
            "experience": 0.82,
            "worker": "15013367"
        },
        {
            "geometry": "501527470",
            "preference": 0.55,
            "resilience": 0.32,
            "medical_condition": True,
            "experience": 0.66,
            "worker": "15013533"
        },
        {
            "geometry": "501527470",
            "preference": 0.31,
            "resilience": 0.6,
            "medical_condition": True,
            "experience": 0.69,
            "worker": "15013870"
        },
        {
            "geometry": "501527470",
            "preference": 0.35,
            "resilience": 0.04,
            "medical_condition": False,
            "experience": 0.35,
            "worker": "15015510"
        },
        {
            "geometry": "501527470",
            "preference": 1.0,
            "resilience": 0.27,
            "medical_condition": False,
            "experience": 0.95,
            "worker": "15015554"
        },
        {
            "geometry": "501527470",
            "preference": 0.08,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15015610"
        },
        {
            "geometry": "501527470",
            "preference": 0.68,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15017042"
        },
        {
            "geometry": "501527470",
            "preference": 0.78,
            "resilience": 0.03,
            "medical_condition": True,
            "experience": 0.78,
            "worker": "15004666"
        },
        {
            "geometry": "501527470",
            "preference": 0.37,
            "resilience": 0.38,
            "medical_condition": True,
            "experience": 0.61,
            "worker": "15020309"
        },
        {
            "geometry": "1343314080",
            "preference": 0.68,
            "resilience": 0.95,
            "medical_condition": True,
            "experience": 0.76,
            "worker": "15014209"
        },
        {
            "geometry": "1343314080",
            "preference": 0.57,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.65,
            "worker": "15014212"
        },
        {
            "geometry": "1343314080",
            "preference": 0.25,
            "resilience": 0.11,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15014727"
        },
        {
            "geometry": "1343314080",
            "preference": 0.39,
            "resilience": 0.56,
            "medical_condition": True,
            "experience": 0.26,
            "worker": "15014729"
        },
        {
            "geometry": "1343314080",
            "preference": 0.45,
            "resilience": 1.0,
            "medical_condition": True,
            "experience": 0.92,
            "worker": "15014964"
        },
        {
            "geometry": "1343314080",
            "preference": 0.49,
            "resilience": 0.12,
            "medical_condition": False,
            "experience": 0.45,
            "worker": "15015125"
        },
        {
            "geometry": "1343314080",
            "preference": 0.9,
            "resilience": 0.45,
            "medical_condition": True,
            "experience": 0.68,
            "worker": "15015261"
        },
        {
            "geometry": "1343314080",
            "preference": 0.85,
            "resilience": 0.32,
            "medical_condition": True,
            "experience": 0.06,
            "worker": "15015261"
        },
        {
            "geometry": "1343314080",
            "preference": 0.54,
            "resilience": 0.89,
            "medical_condition": False,
            "experience": 0.71,
            "worker": "15015264"
        },
        {
            "geometry": "1343314080",
            "preference": 0.93,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.51,
            "worker": "15015349"
        },
        {
            "geometry": "1343314080",
            "preference": 0.12,
            "resilience": 0.2,
            "medical_condition": True,
            "experience": 0.79,
            "worker": "15015351"
        },
        {
            "geometry": "1343314080",
            "preference": 0.03,
            "resilience": 0.55,
            "medical_condition": True,
            "experience": 0.8,
            "worker": "15015351"
        },
        {
            "geometry": "1343314080",
            "preference": 0.55,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.31,
            "worker": "15015514"
        },
        {
            "geometry": "1343314080",
            "preference": 1.0,
            "resilience": 0.72,
            "medical_condition": True,
            "experience": 0.77,
            "worker": "15015568"
        },
        {
            "geometry": "1343314080",
            "preference": 0.82,
            "resilience": 0.07,
            "medical_condition": False,
            "experience": 0.64,
            "worker": "15015650"
        },
        {
            "geometry": "1343314080",
            "preference": 0.45,
            "resilience": 0.68,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15015652"
        },
        {
            "geometry": "1343314080",
            "preference": 0.78,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.97,
            "worker": "15015653"
        },
        {
            "geometry": "1343314080",
            "preference": 0.43,
            "resilience": 0.91,
            "medical_condition": True,
            "experience": 0.12,
            "worker": "15004479"
        },
        {
            "geometry": "1343314080",
            "preference": 0.15,
            "resilience": 0.16,
            "medical_condition": True,
            "experience": 0.71,
            "worker": "15016112"
        },
        {
            "geometry": "1343314080",
            "preference": 0.35,
            "resilience": 0.94,
            "medical_condition": False,
            "experience": 0.85,
            "worker": "15016591"
        },
        {
            "geometry": "1343314080",
            "preference": 0.25,
            "resilience": 0.64,
            "medical_condition": True,
            "experience": 0.13,
            "worker": "15016633"
        },
        {
            "geometry": "1343314080",
            "preference": 0.3,
            "resilience": 0.53,
            "medical_condition": True,
            "experience": 0.17,
            "worker": "15017049"
        },
        {
            "geometry": "1343314080",
            "preference": 0.94,
            "resilience": 0.15,
            "medical_condition": True,
            "experience": 0.72,
            "worker": "15004696"
        },
        {
            "geometry": "1343314080",
            "preference": 0.61,
            "resilience": 0.84,
            "medical_condition": True,
            "experience": 0.83,
            "worker": "15009882"
        },
        {
            "geometry": "1343314080",
            "preference": 0.03,
            "resilience": 0.05,
            "medical_condition": True,
            "experience": 0.58,
            "worker": "15009935"
        },
        {
            "geometry": "1343314080",
            "preference": 0.65,
            "resilience": 0.77,
            "medical_condition": True,
            "experience": 0.64,
            "worker": "15040627"
        },
        {
            "geometry": "1343314080",
            "preference": 0.5,
            "resilience": 0.63,
            "medical_condition": True,
            "experience": 0.96,
            "worker": "15028961"
        },
        {
            "geometry": "1343314080",
            "preference": 0.48,
            "resilience": 0.8,
            "medical_condition": True,
            "experience": 0.3,
            "worker": "15028786"
        },
        {
            "geometry": "1343314080",
            "preference": 0.07,
            "resilience": 0.06,
            "medical_condition": True,
            "experience": 0.48,
            "worker": "15028790"
        },
        {
            "geometry": "1343314080",
            "preference": 0.2,
            "resilience": 0.61,
            "medical_condition": True,
            "experience": 0.72,
            "worker": "15028837"
        },
        {
            "geometry": "1343314080",
            "preference": 0.73,
            "resilience": 0.86,
            "medical_condition": False,
            "experience": 0.13,
            "worker": "15028914"
        },
        {
            "geometry": "1343314080",
            "preference": 0.37,
            "resilience": 0.56,
            "medical_condition": True,
            "experience": 0.47,
            "worker": "15097932"
        },
        {
            "geometry": "1343314080",
            "preference": 0.27,
            "resilience": 0.25,
            "medical_condition": True,
            "experience": 0.29,
            "worker": "15013130"
        },
        {
            "geometry": "1343314080",
            "preference": 0.38,
            "resilience": 0.62,
            "medical_condition": True,
            "experience": 0.87,
            "worker": "15013367"
        },
        {
            "geometry": "1343314080",
            "preference": 0.16,
            "resilience": 0.33,
            "medical_condition": True,
            "experience": 0.31,
            "worker": "15013533"
        },
        {
            "geometry": "1343314080",
            "preference": 0.76,
            "resilience": 0.5,
            "medical_condition": True,
            "experience": 0.5,
            "worker": "15013870"
        },
        {
            "geometry": "1343314080",
            "preference": 0.31,
            "resilience": 0.02,
            "medical_condition": False,
            "experience": 0.51,
            "worker": "15015510"
        },
        {
            "geometry": "1343314080",
            "preference": 0.97,
            "resilience": 0.22,
            "medical_condition": True,
            "experience": 0.05,
            "worker": "15015554"
        },
        {
            "geometry": "1343314080",
            "preference": 0.49,
            "resilience": 0.88,
            "medical_condition": True,
            "experience": 0.47,
            "worker": "15015610"
        },
        {
            "geometry": "1343314080",
            "preference": 0.54,
            "resilience": 0.85,
            "medical_condition": True,
            "experience": 0.88,
            "worker": "15017042"
        },
        {
            "geometry": "1343314080",
            "preference": 0.73,
            "resilience": 0.76,
            "medical_condition": True,
            "experience": 0.4,
            "worker": "15004666"
        },
        {
            "geometry": "1343314080",
            "preference": 0.57,
            "resilience": 0.19,
            "medical_condition": True,
            "experience": 0.07,
            "worker": "15020309"
        }
    ]),
    'availabilities': fields.List(fields.Nested(availabilities_model), required=True,
                                  description="Availability details for workers.",
                                  example=[
        {
            "date": "2024-09-04",
            "worker": "15014209",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15014212",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015652",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015653",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15004479",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15016112",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15016633",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15009935",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15028786",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15028837",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15097932",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15013130",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15013533",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15013870",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015610",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15017042",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15020309",
            "from_timestamp": 1693800000.0,
            "end_timestamp": 1693828800.0
        },
        {
            "date": "2024-09-05",
            "worker": "15014209",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15014212",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015652",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015653",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15004479",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15016112",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15016633",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15009935",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15028786",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15028837",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15097932",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15013130",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15013533",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15013870",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015610",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15017042",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-05",
            "worker": "15020309",
            "from_timestamp": 1693886400.0,
            "end_timestamp": 1693915200.0
        },
        {
            "date": "2024-09-06",
            "worker": "15014209",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15014212",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015652",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015653",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15004479",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15016112",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15016633",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15009935",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15028786",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15028837",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15097932",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15013130",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15013533",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15013870",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015610",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15017042",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-06",
            "worker": "15020309",
            "from_timestamp": 1693972800.0,
            "end_timestamp": 1694001600.0
        },
        {
            "date": "2024-09-07",
            "worker": "15014209",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15014212",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015652",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015653",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15004479",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15016112",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15016633",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15009935",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15028786",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15028837",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15097932",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15013130",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15013533",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15013870",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015610",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15017042",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-07",
            "worker": "15020309",
            "from_timestamp": 1694059200.0,
            "end_timestamp": 1694088000.0
        },
        {
            "date": "2024-09-08",
            "worker": "15014209",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15014212",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015652",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015653",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15004479",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15016112",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15016633",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15009935",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15028786",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15028837",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15097932",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15013130",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15013533",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15013870",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015610",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15017042",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-08",
            "worker": "15020309",
            "from_timestamp": 1694145600.0,
            "end_timestamp": 1694174400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15014209",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15014212",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015652",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015653",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15004479",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15016112",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15016633",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15009935",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15028786",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15028837",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15097932",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15013130",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15013533",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15013870",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015610",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15017042",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-18",
            "worker": "15020309",
            "from_timestamp": 1695009600.0,
            "end_timestamp": 1695038400.0
        },
        {
            "date": "2024-09-19",
            "worker": "15014209",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15014212",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015652",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015653",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15004479",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15016112",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15016633",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15009935",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15028786",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15028837",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15097932",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15013130",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15013533",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15013870",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015610",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15017042",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-19",
            "worker": "15020309",
            "from_timestamp": 1695096000.0,
            "end_timestamp": 1695124800.0
        },
        {
            "date": "2024-09-20",
            "worker": "15014209",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15014212",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015652",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015653",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15004479",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15016112",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15016633",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15009935",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15028786",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15028837",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15097932",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15013130",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15013533",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15013870",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015610",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15017042",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-20",
            "worker": "15020309",
            "from_timestamp": 1695182400.0,
            "end_timestamp": 1695211200.0
        },
        {
            "date": "2024-09-21",
            "worker": "15014209",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15014212",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015652",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015653",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15004479",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15016112",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15016633",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15009935",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15028786",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15028837",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15097932",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15013130",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15013533",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15013870",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015610",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15017042",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-21",
            "worker": "15020309",
            "from_timestamp": 1695268800.0,
            "end_timestamp": 1695297600.0
        },
        {
            "date": "2024-09-22",
            "worker": "15014209",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15014212",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015652",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015653",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15004479",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15016112",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15016633",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15009935",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15028786",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15028837",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15097932",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15013130",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15013533",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15013870",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015610",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15017042",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-22",
            "worker": "15020309",
            "from_timestamp": 1695355200.0,
            "end_timestamp": 1695384000.0
        },
        {
            "date": "2024-09-04",
            "worker": "15014727",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15014729",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15014964",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015125",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015261",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015264",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015351",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015514",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015568",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15016591",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15017049",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15004696",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15009882",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15040627",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15028961",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15028790",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15028914",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-04",
            "worker": "15013367",
            "from_timestamp": 1693828800.0,
            "end_timestamp": 1693857600.0
        },
        {
            "date": "2024-09-05",
            "worker": "15014727",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15014729",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15014964",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015125",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015261",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015264",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015351",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015514",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015568",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15016591",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15017049",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15004696",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15009882",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15040627",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15028961",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15028790",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15028914",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-05",
            "worker": "15013367",
            "from_timestamp": 1693915200.0,
            "end_timestamp": 1693944000.0
        },
        {
            "date": "2024-09-06",
            "worker": "15014727",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15014729",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15014964",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015125",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015261",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015264",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015351",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015514",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015568",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15016591",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15017049",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15004696",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15009882",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15040627",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15028961",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15028790",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15028914",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-06",
            "worker": "15013367",
            "from_timestamp": 1694001600.0,
            "end_timestamp": 1694030400.0
        },
        {
            "date": "2024-09-07",
            "worker": "15014727",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15014729",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15014964",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015125",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015261",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015264",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015351",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015514",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015568",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15016591",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15017049",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15004696",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15009882",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15040627",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15028961",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15028790",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15028914",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-07",
            "worker": "15013367",
            "from_timestamp": 1694088000.0,
            "end_timestamp": 1694116800.0
        },
        {
            "date": "2024-09-08",
            "worker": "15014727",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15014729",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15014964",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015125",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015261",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015264",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015351",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015514",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015568",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15016591",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15017049",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15004696",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15009882",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15040627",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15028961",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15028790",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15028914",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-08",
            "worker": "15013367",
            "from_timestamp": 1694174400.0,
            "end_timestamp": 1694203200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15014727",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15014729",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15014964",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015125",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015261",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015264",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015351",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015514",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015568",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15016591",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15017049",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15004696",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15009882",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15040627",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15028961",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15028790",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15028914",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-18",
            "worker": "15013367",
            "from_timestamp": 1695038400.0,
            "end_timestamp": 1695067200.0
        },
        {
            "date": "2024-09-19",
            "worker": "15014727",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15014729",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15014964",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015125",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015261",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015264",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015351",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015514",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015568",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15016591",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15017049",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15004696",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15009882",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15040627",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15028961",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15028790",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15028914",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-19",
            "worker": "15013367",
            "from_timestamp": 1695124800.0,
            "end_timestamp": 1695153600.0
        },
        {
            "date": "2024-09-20",
            "worker": "15014727",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15014729",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15014964",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015125",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015261",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015264",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015351",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015514",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015568",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15016591",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15017049",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15004696",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15009882",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15040627",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15028961",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15028790",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15028914",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-20",
            "worker": "15013367",
            "from_timestamp": 1695211200.0,
            "end_timestamp": 1695240000.0
        },
        {
            "date": "2024-09-21",
            "worker": "15014727",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15014729",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15014964",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015125",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015261",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015264",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015351",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015514",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015568",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15016591",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15017049",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15004696",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15009882",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15040627",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15028961",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15028790",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15028914",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-21",
            "worker": "15013367",
            "from_timestamp": 1695297600.0,
            "end_timestamp": 1695326400.0
        },
        {
            "date": "2024-09-22",
            "worker": "15014727",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15014729",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15014964",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015125",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015261",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015264",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015351",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015514",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015568",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15016591",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15017049",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15004696",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15009882",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15040627",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15028961",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15028790",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15028914",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-22",
            "worker": "15013367",
            "from_timestamp": 1695384000.0,
            "end_timestamp": 1695412800.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015264",
            "from_timestamp": 1693857600.0,
            "end_timestamp": 1693886400.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015650",
            "from_timestamp": 1693857600.0,
            "end_timestamp": 1693886400.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015510",
            "from_timestamp": 1693857600.0,
            "end_timestamp": 1693886400.0
        },
        {
            "date": "2024-09-04",
            "worker": "15015554",
            "from_timestamp": 1693857600.0,
            "end_timestamp": 1693886400.0
        },
        {
            "date": "2024-09-04",
            "worker": "15004666",
            "from_timestamp": 1693857600.0,
            "end_timestamp": 1693886400.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015264",
            "from_timestamp": 1693944000.0,
            "end_timestamp": 1693972800.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015650",
            "from_timestamp": 1693944000.0,
            "end_timestamp": 1693972800.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015510",
            "from_timestamp": 1693944000.0,
            "end_timestamp": 1693972800.0
        },
        {
            "date": "2024-09-05",
            "worker": "15015554",
            "from_timestamp": 1693944000.0,
            "end_timestamp": 1693972800.0
        },
        {
            "date": "2024-09-05",
            "worker": "15004666",
            "from_timestamp": 1693944000.0,
            "end_timestamp": 1693972800.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015264",
            "from_timestamp": 1694030400.0,
            "end_timestamp": 1694059200.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015650",
            "from_timestamp": 1694030400.0,
            "end_timestamp": 1694059200.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015510",
            "from_timestamp": 1694030400.0,
            "end_timestamp": 1694059200.0
        },
        {
            "date": "2024-09-06",
            "worker": "15015554",
            "from_timestamp": 1694030400.0,
            "end_timestamp": 1694059200.0
        },
        {
            "date": "2024-09-06",
            "worker": "15004666",
            "from_timestamp": 1694030400.0,
            "end_timestamp": 1694059200.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015264",
            "from_timestamp": 1694116800.0,
            "end_timestamp": 1694145600.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015650",
            "from_timestamp": 1694116800.0,
            "end_timestamp": 1694145600.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015510",
            "from_timestamp": 1694116800.0,
            "end_timestamp": 1694145600.0
        },
        {
            "date": "2024-09-07",
            "worker": "15015554",
            "from_timestamp": 1694116800.0,
            "end_timestamp": 1694145600.0
        },
        {
            "date": "2024-09-07",
            "worker": "15004666",
            "from_timestamp": 1694116800.0,
            "end_timestamp": 1694145600.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015264",
            "from_timestamp": 1694203200.0,
            "end_timestamp": 1694232000.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015650",
            "from_timestamp": 1694203200.0,
            "end_timestamp": 1694232000.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015510",
            "from_timestamp": 1694203200.0,
            "end_timestamp": 1694232000.0
        },
        {
            "date": "2024-09-08",
            "worker": "15015554",
            "from_timestamp": 1694203200.0,
            "end_timestamp": 1694232000.0
        },
        {
            "date": "2024-09-08",
            "worker": "15004666",
            "from_timestamp": 1694203200.0,
            "end_timestamp": 1694232000.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015264",
            "from_timestamp": 1694462400.0,
            "end_timestamp": 1694491200.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015650",
            "from_timestamp": 1694462400.0,
            "end_timestamp": 1694491200.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015510",
            "from_timestamp": 1694462400.0,
            "end_timestamp": 1694491200.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015554",
            "from_timestamp": 1694462400.0,
            "end_timestamp": 1694491200.0
        },
        {
            "date": "2024-09-11",
            "worker": "15004666",
            "from_timestamp": 1694462400.0,
            "end_timestamp": 1694491200.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015264",
            "from_timestamp": 1694548800.0,
            "end_timestamp": 1694577600.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015650",
            "from_timestamp": 1694548800.0,
            "end_timestamp": 1694577600.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015510",
            "from_timestamp": 1694548800.0,
            "end_timestamp": 1694577600.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015554",
            "from_timestamp": 1694548800.0,
            "end_timestamp": 1694577600.0
        },
        {
            "date": "2024-09-12",
            "worker": "15004666",
            "from_timestamp": 1694548800.0,
            "end_timestamp": 1694577600.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015264",
            "from_timestamp": 1694635200.0,
            "end_timestamp": 1694664000.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015650",
            "from_timestamp": 1694635200.0,
            "end_timestamp": 1694664000.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015510",
            "from_timestamp": 1694635200.0,
            "end_timestamp": 1694664000.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015554",
            "from_timestamp": 1694635200.0,
            "end_timestamp": 1694664000.0
        },
        {
            "date": "2024-09-13",
            "worker": "15004666",
            "from_timestamp": 1694635200.0,
            "end_timestamp": 1694664000.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015264",
            "from_timestamp": 1694721600.0,
            "end_timestamp": 1694750400.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015650",
            "from_timestamp": 1694721600.0,
            "end_timestamp": 1694750400.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015510",
            "from_timestamp": 1694721600.0,
            "end_timestamp": 1694750400.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015554",
            "from_timestamp": 1694721600.0,
            "end_timestamp": 1694750400.0
        },
        {
            "date": "2024-09-14",
            "worker": "15004666",
            "from_timestamp": 1694721600.0,
            "end_timestamp": 1694750400.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015264",
            "from_timestamp": 1694808000.0,
            "end_timestamp": 1694836800.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015650",
            "from_timestamp": 1694808000.0,
            "end_timestamp": 1694836800.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015510",
            "from_timestamp": 1694808000.0,
            "end_timestamp": 1694836800.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015554",
            "from_timestamp": 1694808000.0,
            "end_timestamp": 1694836800.0
        },
        {
            "date": "2024-09-15",
            "worker": "15004666",
            "from_timestamp": 1694808000.0,
            "end_timestamp": 1694836800.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015264",
            "from_timestamp": 1695067200.0,
            "end_timestamp": 1695096000.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015650",
            "from_timestamp": 1695067200.0,
            "end_timestamp": 1695096000.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015510",
            "from_timestamp": 1695067200.0,
            "end_timestamp": 1695096000.0
        },
        {
            "date": "2024-09-18",
            "worker": "15015554",
            "from_timestamp": 1695067200.0,
            "end_timestamp": 1695096000.0
        },
        {
            "date": "2024-09-18",
            "worker": "15004666",
            "from_timestamp": 1695067200.0,
            "end_timestamp": 1695096000.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015264",
            "from_timestamp": 1695153600.0,
            "end_timestamp": 1695182400.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015650",
            "from_timestamp": 1695153600.0,
            "end_timestamp": 1695182400.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015510",
            "from_timestamp": 1695153600.0,
            "end_timestamp": 1695182400.0
        },
        {
            "date": "2024-09-19",
            "worker": "15015554",
            "from_timestamp": 1695153600.0,
            "end_timestamp": 1695182400.0
        },
        {
            "date": "2024-09-19",
            "worker": "15004666",
            "from_timestamp": 1695153600.0,
            "end_timestamp": 1695182400.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015264",
            "from_timestamp": 1695240000.0,
            "end_timestamp": 1695268800.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015650",
            "from_timestamp": 1695240000.0,
            "end_timestamp": 1695268800.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015510",
            "from_timestamp": 1695240000.0,
            "end_timestamp": 1695268800.0
        },
        {
            "date": "2024-09-20",
            "worker": "15015554",
            "from_timestamp": 1695240000.0,
            "end_timestamp": 1695268800.0
        },
        {
            "date": "2024-09-20",
            "worker": "15004666",
            "from_timestamp": 1695240000.0,
            "end_timestamp": 1695268800.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015264",
            "from_timestamp": 1695326400.0,
            "end_timestamp": 1695355200.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015650",
            "from_timestamp": 1695326400.0,
            "end_timestamp": 1695355200.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015510",
            "from_timestamp": 1695326400.0,
            "end_timestamp": 1695355200.0
        },
        {
            "date": "2024-09-21",
            "worker": "15015554",
            "from_timestamp": 1695326400.0,
            "end_timestamp": 1695355200.0
        },
        {
            "date": "2024-09-21",
            "worker": "15004666",
            "from_timestamp": 1695326400.0,
            "end_timestamp": 1695355200.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015264",
            "from_timestamp": 1695412800.0,
            "end_timestamp": 1695441600.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015650",
            "from_timestamp": 1695412800.0,
            "end_timestamp": 1695441600.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015510",
            "from_timestamp": 1695412800.0,
            "end_timestamp": 1695441600.0
        },
        {
            "date": "2024-09-22",
            "worker": "15015554",
            "from_timestamp": 1695412800.0,
            "end_timestamp": 1695441600.0
        },
        {
            "date": "2024-09-22",
            "worker": "15004666",
            "from_timestamp": 1695412800.0,
            "end_timestamp": 1695441600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15014727",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15014729",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15014964",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015125",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015261",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015264",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015351",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015514",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015568",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15016591",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15017049",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15004696",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15009882",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15040627",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15028961",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15028790",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15028914",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-11",
            "worker": "15013367",
            "from_timestamp": 1694404800.0,
            "end_timestamp": 1694433600.0
        },
        {
            "date": "2024-09-12",
            "worker": "15014727",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15014729",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15014964",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015125",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015261",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015264",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015351",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015514",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015568",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15016591",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15017049",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15004696",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15009882",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15040627",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15028961",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15028790",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15028914",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-12",
            "worker": "15013367",
            "from_timestamp": 1694491200.0,
            "end_timestamp": 1694520000.0
        },
        {
            "date": "2024-09-13",
            "worker": "15014727",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15014729",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15014964",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015125",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015261",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015264",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015351",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015514",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015568",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15016591",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15017049",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15004696",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15009882",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15040627",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15028961",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15028790",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15028914",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-13",
            "worker": "15013367",
            "from_timestamp": 1694577600.0,
            "end_timestamp": 1694606400.0
        },
        {
            "date": "2024-09-14",
            "worker": "15014727",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15014729",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15014964",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015125",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015261",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015264",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015351",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015514",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015568",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15016591",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15017049",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15004696",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15009882",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15040627",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15028961",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15028790",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15028914",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-14",
            "worker": "15013367",
            "from_timestamp": 1694664000.0,
            "end_timestamp": 1694692800.0
        },
        {
            "date": "2024-09-15",
            "worker": "15014727",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15014729",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15014964",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015125",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015261",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015264",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015351",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015514",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015568",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15016591",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15017049",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15004696",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15009882",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15040627",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15028961",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15028790",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15028914",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-15",
            "worker": "15013367",
            "from_timestamp": 1694750400.0,
            "end_timestamp": 1694779200.0
        },
        {
            "date": "2024-09-11",
            "worker": "15014209",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15014212",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015652",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015653",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15004479",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15016112",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15016633",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15009935",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15028786",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15028837",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15097932",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15013130",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15013533",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15013870",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15015610",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15017042",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-11",
            "worker": "15020309",
            "from_timestamp": 1694433600.0,
            "end_timestamp": 1694462400.0
        },
        {
            "date": "2024-09-12",
            "worker": "15014209",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15014212",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015652",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015653",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15004479",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15016112",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15016633",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15009935",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15028786",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15028837",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15097932",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15013130",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15013533",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15013870",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15015610",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15017042",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-12",
            "worker": "15020309",
            "from_timestamp": 1694520000.0,
            "end_timestamp": 1694548800.0
        },
        {
            "date": "2024-09-13",
            "worker": "15014209",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15014212",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015652",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015653",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15004479",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15016112",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15016633",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15009935",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15028786",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15028837",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15097932",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15013130",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15013533",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15013870",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15015610",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15017042",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-13",
            "worker": "15020309",
            "from_timestamp": 1694606400.0,
            "end_timestamp": 1694635200.0
        },
        {
            "date": "2024-09-14",
            "worker": "15014209",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15014212",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015652",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015653",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15004479",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15016112",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15016633",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15009935",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15028786",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15028837",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15097932",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15013130",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15013533",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15013870",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15015610",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15017042",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-14",
            "worker": "15020309",
            "from_timestamp": 1694692800.0,
            "end_timestamp": 1694721600.0
        },
        {
            "date": "2024-09-15",
            "worker": "15014209",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15014212",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015652",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015653",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15004479",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15016112",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15016633",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15009935",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15028786",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15028837",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15097932",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15013130",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15013533",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15013870",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15015610",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15017042",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        },
        {
            "date": "2024-09-15",
            "worker": "15020309",
            "from_timestamp": 1694779200.0,
            "end_timestamp": 1694808000.0
        }
    ])
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
        # Here you would process the planning data
        data = request.json
        print(data)  # This will print the received JSON data to the console

        # Accessing specific fields from the JSON
        start_time_timestamp = data.get('start_time_stamp')
        print(start_time_timestamp)
        # Accessing order_data
        order_data = data.get('order-data')
        print(order_data)
        # Store the values for each order in order_list like: (duration [h], line_id, priority, due_date [h])
        order_list = []
        # order_dict to uniquely identify the order based on id
        order_dict = {}
        order_map = {}
        temp_order_map = {}
        temp = 0

        init_line_list = {}
        temp_line_list = {}
        tp_mapping = data.get('throughput_mapping')
        for tp in tp_mapping:
            if tp['line'] not in init_line_list:
                init_line_list[tp['line']] = temp
                temp_line_list['Line ' + str(temp)] = tp['line']
                temp = temp + 1

        temp = 0
        for to in order_data:
            if to['order'] not in temp_order_map:
                temp_order_map[to['order']] = temp
                order_map['Order ' + str(temp)] = to['order']
                temp = temp + 1

        temp = 0
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []  # if order is not in the dictionary we create an enry for it
            priority = 0
            if not order['priority']:
                priority = 1
            # Convert the time into seconds format
            deadline_timestamp = order["deadline"]
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to mins
            duration_mins = duration_seconds / 60

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
                    if throughput_mapping['line'] == "Line " + str(line) and throughput_mapping['geometry'] == order['geometry']:
                        if throughput_mapping['throughput'] == 0:
                            warnings.warn("Throughput adjusted to 300")
                            throughput_mapping['throughput'] = 300
                        duration = ((5 * order['mold']) + (
                                15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        # add the entry (duration [h], line_id, priority, due_date [h])
                        # to the order_dict for the given order
                        if init_line_list[throughput_mapping['line']]:
                            temp = init_line_list[throughput_mapping['line']]
                        order_dict[order['order']].append(
                            (math.ceil(duration), temp, priority, math.ceil(duration_mins)))
                    temp = 0
        for key, value in order_dict.items():
            if value:
                order_list.append(value)

        # Replace the hard coded EXAMPLE_ORDER_INSTANCE with the order list generated in the previous step
        # and call the function main() from cp_order_to_line
        solution_df = main(order_list=order_list)
        print(solution_df.head(n=30))
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
        worker_map = {}
        for worker in worker_list:
            if int(worker) not in worker_map:
                worker_map[int(worker)] = index
                worker_specific_data[index] = {}
                index = index + 1
            for factor in human_factor:
                if worker == factor['worker']:
                    worker_specific_data[worker_map[int(worker)]][factor['geometry']] = {}
                    medical_condition = True
                    if factor['medical_condition'] == False:
                        medical_condition = False
                    new_data = {
                        "experience": factor['experience'],
                        "preference": factor['preference'],
                        "resilience": factor['resilience'],
                        "medical-condition": medical_condition
                    }
                    worker_specific_data[worker_map[int(worker)]][factor['geometry']] = new_data

        print(order_list)

        # Retrieve all orders and map them in the format "Order i" where i is the index for a unique order
        order_details = {}
        order_list = data.get('order-data')
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

            temps = 0
            for worker in worker_availabilities:
                if worker['Worker_id'] == worker_map[int(worker_id)]:
                    temps = 1
                    worker["availability"].append((from_relative, end_relative))
                    break

            # Append worker availability as tuple
            if temps == 0:
                worker_availabilities.append({
                    "Worker_id": worker_map[int(worker_id)],
                    "availability": [(from_relative, end_relative)]
                })

        # Hard coded worker_availabilities example not to be used
        #worker_availabilities = [
            #    # first shift
        #    {'Worker_id': 1, "availability": [(0, 7), (16, 23), (32, 39), (48, 55), (64, 71)]},
        #]

        # For each task (Order) in the result obtained from order_to_line, we add the list of possible geometries
        # see hardcoded order_details in cp_worker_allocation.py for more information
        line_allocation = []
        for order in order_to_line:
            geo_list = order_details[order['Task']]
            for geo in geo_list:
                temp_order = order
                temp_order['geometry'] = geo
                try:
                    if required_workers_mapping[order['Resource']][temp_order['geometry']]:
                        temp_order['required_workers'] = required_workers_mapping[order['Resource']][
                            temp_order['geometry']]
                        line_allocation.append(temp_order)
                except KeyError:
                    # Handle missing key, e.g., skip or log an error
                    pass

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
                    worker_allocation_data.append(i)
                items['workers'] = worker_allocation_data
            else:
                items['workers'] = []



        final_result = []
        for solution in line_allocation:
            temp_sol = solution.copy()
            if temp_sol['Resource'] in temp_line_list:
                temp_sol['Resource'] = temp_line_list[temp_sol['Resource']]
            if temp_sol['Task'] in order_map:
                temp_sol['Task'] = order_map[temp_sol['Task']]
            final_result.append(temp_sol)

        message = "Successfully performed worker allocation operation."
        if len(line_allocation) == 0:
            message = "No Optimal / Feasible solution found!!"

        return {
            "message": message,
            "solution": final_result  # Final result
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
        start_time_timestamp = data.get('start_time_stamp')
        print(start_time_timestamp)
        # Accessing order_data
        order_data = data.get('order-data')
        print(order_data)
        # Store the values for each order in order_list like: (duration [h], line_id, priority, due_date [h])
        order_list = []
        # order_dict to uniquely identify the order based on id
        order_dict = {}
        order_map = {}
        temp_order_map = {}
        temp = 0

        init_line_list = {}
        temp_line_list = {}
        tp_mapping = data.get('throughput_mapping')
        for tp in tp_mapping:
            if tp['line'] not in init_line_list:
                init_line_list[tp['line']] = temp
                temp_line_list['Line ' + str(temp)] = tp['line']
                temp = temp + 1

        temp = 0
        for to in order_data:
            if to['order'] not in temp_order_map:
                temp_order_map[to['order']] = temp
                order_map['Order ' + str(temp)] = to['order']
                temp = temp + 1

        temp = 0
        for order in order_data:
            if order['order'] not in order_dict:
                order_dict[order['order']] = []  # if order is not in the dictionary we create an enry for it
            priority = 0
            if not order['priority']:
                priority = 1
            # Convert the time into seconds format
            deadline_timestamp = order["deadline"]
            duration_seconds = deadline_timestamp - start_time_timestamp

            # Convert seconds to mins
            duration_mins = duration_seconds / 60

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
                    if throughput_mapping['line'] == "Line " + str(line) and throughput_mapping['geometry'] == order['geometry']:
                        if throughput_mapping['throughput'] == 0:
                            warnings.warn("Throughput adjusted to 300")
                            throughput_mapping['throughput'] = 300
                        duration = ((5 * order['mold']) + (
                                15 + (order['amount'] / throughput_mapping['throughput'])) / 60)
                        # add the entry (duration [h], line_id, priority, due_date [h])
                        # to the order_dict for the given order
                        if init_line_list[throughput_mapping['line']]:
                            temp = init_line_list[throughput_mapping['line']]
                        order_dict[order['order']].append(
                            (math.ceil(duration), temp, priority, math.ceil(duration_mins)))
                    temp = 0
        for key, value in order_dict.items():
            if value:
                order_list.append(value)

        # Replace the hard coded EXAMPLE_ORDER_INSTANCE with the order list generated in the previous step
        # and call the function main() from cp_order_to_line
        solution_df = main(order_list=order_list)
        print(solution_df.head(n=30))
        solution_dict = solution_df.to_dict(orient='records')

        final_result = []
        for solution in solution_dict:
            temp_sol = solution.copy()
            if temp_sol['Resource'] in temp_line_list:
                temp_sol['Resource'] = temp_line_list[temp_sol['Resource']]
            if temp_sol['Task'] in order_map:
                temp_sol['Task'] = order_map[temp_sol['Task']]
            final_result.append(temp_sol)
        print(order_list)
        return {
            "message": "Successfully performed order-to-line operation.",
            "solution": final_result  # Include solution_dict in the response
        }, 200


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
