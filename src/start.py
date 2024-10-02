from gradescopeapi.classes.connection import GSConnection

# create connection and login
connection = GSConnection()
connection.login("steven.bell@tufts.edu", "gradesudo374")

"""
Fetching all courses for user
"""
# courses = connection.account.get_courses()
# for course in courses["instructor"]:
#     print(course)
# for course in courses["student"]:
#     print(course)

course_id = "833437"

connection.account.create_assignment(course_id, "Homework 2")

"""
Getting all assignments for course
"""
assignments = connection.account.get_assignments(course_id)
for assignment in assignments:
    print(assignment)



