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