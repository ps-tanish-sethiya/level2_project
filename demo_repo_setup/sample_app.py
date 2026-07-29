"""
Sample Application with an intentional bug for demo target repository.
"""

def add_numbers(a: int, b: int) -> int:
    # Intentional bug: returns product instead of sum for demo build failure
    return a * b


def get_application_status() -> str:
    return "OK"
