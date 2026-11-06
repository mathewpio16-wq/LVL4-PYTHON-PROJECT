def bubble_sort_cases(cases):
    sorted_cases = cases.copy()

    n = len(sorted_cases)

    for i in range(n-1):
        swapped = False

        for j in range(n - 1 - i):
            if sorted_cases[j]["priority"] < sorted_cases[j + 1]["priority"]:
                sorted_cases[j], sorted_cases[j+1] = (
                    sorted_cases[j+1],
                    sorted_cases[j]
                )

                swapped = True

        if not swapped:
            break

    return sorted_cases
    

if __name__  == "__main__":
    cases = [
        {"case_id": 101, "priority": 2},
        {"case_id": 102, "priority": 1},
        {"case_id": 103, "priority": 3},
        {"case_id": 104, "priority": 2},
        {"case_id": 105, "priority": 3},
    ]

    print("Before Sorting:")

    for case in cases:
        print(case)

    sorted_cases = bubble_sort_cases(cases)

    print("\nAfter Sorting:")
    for case in sorted_cases:
        print(case)


    test_cases = [
        ("Already Sorted", [3,2,1]),
        ("Reverse Sorted", [1,2,3]),
        ("Equal Priorities", [2,2,2]),
        ("Empty List", []),
        ("Single Case", [3]),
    ]

    for test_name, priorities in test_cases:
        cases_to_test = [
            {"case_id": i + 1, "priority": priority}
            for i, priority in enumerate(priorities)
        ]

        result = bubble_sort_cases(cases_to_test)

        sorted_priorities = [
            case["priority"] for case in result
        ]

        expected = sorted(priorities, reverse=True)

        print(f"\nTest: {test_name}")
        print(f"Result: {sorted_priorities}")
        print(f"Expected: {expected}")

        if sorted_priorities == expected:
            print("PASS")
        else: 
            print("FAIL")