from validation import (
    validate_case_id,
    validate_case_title,
    validate_client_name,
    validate_description,
    validate_priority
)

from database import save_case, get_all_cases
import sqlite3


def create_case(case_data):
    # Retrieve existing cases from SQLite
    cases = get_all_cases()

    # Validate the Case ID
    is_valid, message = validate_case_id(
        case_data.get("case_id", ""),
        cases
    )

    if not is_valid:
        return False, message

    # Validate the Case Title
    is_valid, message = validate_case_title(
        case_data.get("case_title", "")
    )

    if not is_valid:
        return False, message

    # Validate the Client Name
    is_valid, message = validate_client_name(
        case_data.get("client_name", "")
    )

    if not is_valid:
        return False, message

    # Validate the Description
    is_valid, message = validate_description(
        case_data.get("description", "")
    )

    if not is_valid:
        return False, message

    # Validate the Priority
    is_valid, message = validate_priority(
        case_data.get("priority", "")
    )

    if not is_valid:
        return False, message

    # Prepare validated case information
    new_case = {
        "case_id": int(case_data["case_id"]),
        "case_title": case_data["case_title"].strip(),
        "client_name": case_data["client_name"].strip(),
        "description": case_data["description"].strip(),
        "priority": int(case_data["priority"]),
        "status": "Open"
    }

    # Save the case to SQLite
    try:
        save_case(new_case)

    except sqlite3.IntegrityError:
        return False, "A case with this ID already exists."

    except sqlite3.Error:
        return False, "Unable to save the case. Please try again."

    return True, "Case added successfully."

def add_case(cases):
    print("\n--- Add New Case ---")

    while True:
        case_id_input = input("Enter Case ID: ")

        is_valid, message = validate_case_id(case_id_input, cases)

        if is_valid:
            case_id = int(case_id_input)
            break

        print(message)

    # Validating the case title
    while True:
        case_title = input("Enter Case Title: ").strip()

        is_valid, message = validate_case_title(case_title)

        if is_valid:
            break

        print(message)

        # Validate client name
    while True:
        client_name = input("Enter Client Name: ").strip()

        is_valid, message = validate_client_name(client_name)

        if is_valid:
            break

        print(message)

    # Validate description
    while True:
        description = input("Enter Description: ").strip()

        is_valid, message = validate_description(description)

        if is_valid:
            break

        print(message)

    # Validate priority
    while True:
        priority_input = input("Enter Priority (1-3): ")

        is_valid, message = validate_priority(priority_input)

        if is_valid:
            priority = int(priority_input)
            break

        print(message)

    # Creating the case dictionary
    new_case = {
        "case_id": case_id,
        "case_title": case_title,
        "client_name": client_name,
        "description": description,
        "priority": priority, 
        "status": "Open",
    }

    # Save the new case to SQLite
    save_case(new_case)

    # Update the current list
    cases.append(new_case)

    print(f"\nCase {case_id} added and saved successfully!")

def view_cases(cases):
    print("\n--- All Registered Cases")

    if not cases: 
        print("No cases have been registered.")
        return
    
    for case in cases: 
        print("------------------------------")
        print(f"Case ID: {case['case_id']}")
        print(f"Title: {case['case_title']}")
        print(f"Client: {case['client_name']}")
        print(f"Description: {case['description']}")
        print(f"Priority: {case['priority']}")
        print(f"Status: {case['status']}")
        print("------------------------------")

def view_case_by_id(cases, case_id):
    for case in cases: 
        if case["case_id"] == case_id:
            print("\n--- Case Details ---")
            print(f"Case ID: {case['case_id']}")
            print(f"Title: {case['case_title']}")
            print(f"Client: {case['client_name']}")
            print(f"Description: {case['description']}")
            print(f"Priority: {case['priority']}")
            print(f"Status: {case['status']}")
            return case
    
    
    print("Case not found")
    return None

if __name__ == "__main__":
    cases = get_all_cases()

    add_case(cases)
    add_case(cases)

    view_cases(cases)
    view_case_by_id(cases, 2)
