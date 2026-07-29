"""
Sample Test File designed to fail against sample_app.py intentional bug.
"""

from sample_app import add_numbers, get_application_status


def test_add_numbers():
    # Expect 2 + 3 = 5, but sample_app returns 2 * 3 = 6 (intentional failure)
    assert add_numbers(2, 3) == 5, "Expected 2 + 3 = 5"


def test_application_status():
    assert get_application_status() == "OK"
