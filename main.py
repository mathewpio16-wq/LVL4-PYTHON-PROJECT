from cases import add_case, view_cases, view_case_by_id
from search import search_case
from sorting import bubble_sort_cases

def main():
    cases = []

    while True:
        print("\n--- DFIP Case Management System ---")
        print("1. Add Case")
        print("2. View All Cases")
        print("3. Search Case")
        print("4. Sort Cases by Priority")
        print("5. Exit")

        choice = input("Enter your choice (1-5): ")

        if choice == "1":
            add_case(cases)
        elif choice == "2":
            view_cases(cases)
        elif choice == "3":
            case_id = int(input("Enter Case ID to search: "))

            result = search_case(cases, case_id)

            if result is not None:
                print("\nCase Found: ")
                print(result)
            else:
                print("Case not found.")
        elif choice == "4":
            sorted_cases = bubble_sort_cases(cases)
            view_cases(sorted_cases)
        elif choice == "5":
            print("Exiting the system")
            break 
        else: 
            print("Invalid option or feature not yet implemented.")

if __name__ == "__main__":
    main()