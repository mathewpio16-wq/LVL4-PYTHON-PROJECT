def validate_case_id(case_id, cases):
    try:
        case_id = int(case_id)

        if case_id <= 0:
            return False, "Case ID must be a positive number."
        
        for case in cases:
            if case["case_id"] == case_id:
                return False, "A case with this ID already exists."
        return True, "Valid Case ID"
    except (ValueError, TypeError):
        return False, "Please enter a valid number"
    

def validate_case_title(case_title):
    # Remove spaces before and after the title
    case_title = case_title.strip()

    # Check whether the title is empty
    if not case_title:
        return False, "Case title cannot be empty."

    # Return success if the title is valid
    return True, "Valid case title."

def validate_client_name(client_name):
    client_name = client_name.strip()

    if not client_name:
        return False, "Client name cannot be empty."

    return True, "Valid client name."


def validate_description(description):
    description = description.strip()

    if not description:
        return False, "Description cannot be empty."

    return True, "Valid description."


def validate_priority(priority):
    try:
        priority = int(priority)

        if priority not in [1, 2, 3]:
            return False, "Priority must be between 1 and 3."

        return True, "Valid priority."

    except (ValueError, TypeError):
        return False, "Please enter a valid number."

if __name__ == "__main__":
    print(validate_client_name("John Smith"))
    print(validate_client_name(""))

    print(validate_description("Investigation into fraud"))
    print(validate_description("   "))

    print(validate_priority("1"))
    print(validate_priority("3"))
    print(validate_priority("5"))
    print(validate_priority("abc"))