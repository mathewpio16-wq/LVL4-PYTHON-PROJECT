"""Case service: validate user input and persist a new case in SQLite."""
import sqlite3
from database import save_case
from validation import (validate_case_title, validate_client_name,
                        validate_description, validate_priority)


def create_case(case_data):
    """Return (success, message). The database generates the Case ID."""
    if not isinstance(case_data, dict):
        return False, "Please provide the case details."
    checks = (
        (validate_case_title, "case_title"),
        (validate_client_name, "client_name"),
        (validate_description, "description"),
        (validate_priority, "priority"),
    )
    for validator, field in checks:
        valid, message = validator(case_data.get(field, ""))
        if not valid:
            return False, message
    new_case = {field: case_data[field].strip()
                for field in ("case_title", "client_name", "description")}
    new_case["priority"] = int(case_data["priority"])
    new_case["status"] = "Open"
    try:
        case_id = save_case(new_case)
    except sqlite3.Error:
        return False, "Unable to save case. Please try again."
    return True, f"Case #{case_id} added successfully."
