"""Linear search by case ID."""
from database import get_all_cases


def search_case(cases, case_id):
    for case in cases:
        if case["case_id"] == case_id:
            return case
    return None


def search_case_from_db(case_id):
    try:
        case_id = int(case_id)
    except (ValueError, TypeError):
        return None
    return search_case(get_all_cases(), case_id)
