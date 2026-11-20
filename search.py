from database import get_all_cases

def search_case(cases, case_id):
    for case in cases:
        if case["case_id"] == case_id:
            return case

    return None


def search_case_from_db(case_id):
    cases = get_all_cases()

    try:
        case_id = int(case_id)
    except (ValueError, TypeError):
        return None

    return search_case(cases, case_id)
    
if __name__ == "__main__":

    cases = [
        {"case_id": 101, "priority": 2},
        {"case_id": 102, "priority": 1},
        {"case_id": 103, "priority": 3},
        {"case_id": 104, "priority": 2},
        {"case_id": 105, "priority": 3},
    ]

    case_id = int(input("Enter Case ID to search: "))

    result = search_case(cases, case_id)

    if result is not None:
        print("\nCase Found:")
        print(result)

    else:
        print("\nCase not found.")