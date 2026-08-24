WEIGHTS = {
    "threads": 20, "database_pool": 20, "http_pool": 15, "pods": 10,
    "hpa": 15, "resources": 10, "external_timeout": 5, "blocking_calls": 5,
}

STATUS_POINTS = {
    "HEALTHY": 1.0, "ADEQUATE": .8, "ATTENTION": .5,
    "POTENTIAL_BOTTLENECK": .35, "INSUFFICIENT": 0.0,
}

