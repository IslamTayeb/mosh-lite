import csv


def parse_csv(filename: str) -> list[dict]:
    with open(filename, "r") as f:
        reader = csv.reader(f)
        data = [(int(row[1]), float(row[0])) for row in reader]
        return dict(data)


def backfill(
    latency: dict[int, float],
    client_log: dict[int, float],
    server_log: dict[int, float],
) -> None:
    latest_time = None
    for key in sorted(latency.keys(), reverse=True):
        if key in server_log and server_log[key] is not None:
            latest_time = server_log[key]
        if latency[key] is None and latest_time is not None:
            latency[key] = latest_time - client_log[key]


def calculate_latency(client_log: dict, server_log: dict) -> dict[int, float]:
    latency = dict()
    for key, value in client_log.items():
        if key in server_log:
            latency[key] = server_log[key] - value
        else:
            latency[key] = None

    backfill(latency, client_log, server_log)

    return latency


def calculate_statistics(latency: dict[int, float]) -> dict[str, float]:
    values = [v for v in latency.values() if v is not None]
    if not values:
        return {"min": 0, "max": 0, "average": 0}

    average = sum(values) / len(values)
    median = sorted(values)[len(values) // 2]

    return {"average": average, "median": median}


def main():
    client_log = parse_csv("client_out.log")
    server_log = parse_csv("output.log")

    latency = calculate_latency(client_log, server_log)
    stats = calculate_statistics(latency)

    with open("latency.csv", "w+") as f:
        for stat, value in stats.items():
            f.write(f"{stat},{value}\n")


if __name__ == "__main__":
    main()
