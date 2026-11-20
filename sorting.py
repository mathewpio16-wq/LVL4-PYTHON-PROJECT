"""Bubble sort cases by descending priority."""
from database import get_all_cases


def bubble_sort_cases(cases):
    result = cases.copy()
    for i in range(len(result) - 1):
        swapped = False
        for j in range(len(result) - 1 - i):
            if result[j]["priority"] < result[j + 1]["priority"]:
                result[j], result[j + 1] = result[j + 1], result[j]
                swapped = True
        if not swapped:
            break
    return result


def sort_cases_from_db():
    return bubble_sort_cases(get_all_cases())
