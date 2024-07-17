import random

details = {
    worker_id: {
        f"geo{geo}": {
            "experience": round(random.uniform(0.0, 1.0), 2),
            "preference": round(random.uniform(0.0, 1.0), 2),
            "resilience": round(random.uniform(0.0, 1.0), 2),
            "medical-condition": random.choice([True, True, True, False])  # More True values than False
        } for geo in range(1, 6)
    } for worker_id in range(1, 21)
}

print(details)

if __name__ == '__main__':
    pass