"""Shared case input validation."""
def validate_case_id(value, cases):
    try:
        number = int(value)
    except (ValueError, TypeError):
        return False, "Please enter a valid Case ID number."
    if number <= 0:
        return False, "Case ID must be a positive number."
    if any(case["case_id"] == number for case in cases):
        return False, "A case with this ID already exists."
    return True, "Valid Case ID."


def validate_case_title(value):
    return (True, "Valid case title.") if isinstance(value, str) and value.strip() else (False, "Case title cannot be empty.")


def validate_client_name(value):
    return (True, "Valid client name.") if isinstance(value, str) and value.strip() else (False, "Client name cannot be empty.")


def validate_description(value):
    return (True, "Valid description.") if isinstance(value, str) and value.strip() else (False, "Description cannot be empty.")


def validate_priority(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        return False, "Please enter a valid priority number."
    return (True, "Valid priority.") if number in (1, 2, 3) else (False, "Priority must be between 1 and 3.")
