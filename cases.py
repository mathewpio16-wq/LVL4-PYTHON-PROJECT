def add_case(cases):
    print("\n--- Add New Case ---")

# Validating case ids
    while True:
        try:
            case_id = int(input("Enter Case ID: "))

            if case_id <= 0:
                print("Case ID must be a positive number.")
                continue

# Ensuring there are no duplicate Case IDs
            duplicate = False
            for case in cases:
                if case["case_id"] == case_id:
                    duplicate = True
                    break

            if duplicate: 
                print("A case with this ID already exists")
                continue
            break

        except ValueError:
            print("Please enter a valid numeric Case ID. ")

    # Validating the case titles.
    while True:
        case_title = input("Enter Case Title: ").strip()

        if case_title:
            break

    # Validating the clients name
    while True:
        client_name = input("Enter Client Name: ").strip()
        
        if client_name:
            break

        print("Client name cannot be empty")

    # Validating the case description
    while True:
        description = input("Enter Description: ").strip()

        if description:
            break

        print("Description cannot be empty")

    # validating the case priority
    while True:
        try:
            priority = int(input("Enter priority (1-3):  "))

            if priority in [1, 2, 3]:
                break

            print("Priority must be between 1 and 3.")

        except ValueError:
            print("Please enter a valid number.")

    # Creating the case dictionary
    new_case = {
        "case_id": case_id,
        "case_title": case_title,
        "client_name": client_name,
        "description": description,
        "priority": priority, 
        "status": "Open",
    }

    # Storing a new case

    cases.append(new_case)

    print(f"\nCase {case_id} added successfully!")

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
    cases = []

    add_case(cases)
    add_case(cases)

    view_cases(cases)
    view_case_by_id(cases, 2)
