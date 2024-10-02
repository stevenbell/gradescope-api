from bs4 import BeautifulSoup
from typing import List, Dict
import time
from requests_toolbelt.multipart.encoder import MultipartEncoder

from gradescopeapi.classes._helpers._course_helpers import (
    get_courses_info,
    get_course_members,
)
from gradescopeapi.classes._helpers._assignment_helpers import (
    check_page_auth,
    get_assignments_instructor_view,
    get_assignments_student_view,
    get_submission_files,
)
from gradescopeapi.classes.assignments import Assignment
from gradescopeapi.classes.member import Member

class Account:
    def __init__(self, session):
        self.session = session

    def get_courses(self) -> dict:
        """
        Get all courses for the user, including both instructor and student courses

        Returns:
            dict: A dictionary of dictionaries, where keys are "instructor" and "student" and values are
            dictionaries containing all courses, where keys are course IDs and values are Course objects.

            For example:
                {
                'instructor': {
                    "123456": Course(...),
                    "234567": Course(...)
                },
                'student': {
                    "654321": Course(...),
                    "765432": Course(...)
                }
                }

        Raises:
            RuntimeError: If request to account page fails.
        """

        endpoint = "https://www.gradescope.com/account"

        # get main page
        response = self.session.get(endpoint)

        if response.status_code != 200:
            raise RuntimeError(
                "Failed to access account page on Gradescope. Status code: {response.status_code}"
            )

        soup = BeautifulSoup(response.text, "html.parser")

        # see if user is solely a student or instructor
        user_courses, is_instructor = get_courses_info(soup, "Your Courses")

        # if the user is indeed solely a student or instructor
        # return the appropriate set of courses
        if user_courses:
            if is_instructor:
                return {"instructor": user_courses, "student": {}}
            else:
                return {"instructor": {}, "student": user_courses}

        # if user is both a student and instructor, get both sets of courses
        courses = {"instructor": {}, "student": {}}

        # get instructor courses
        instructor_courses, _ = get_courses_info(soup, "Instructor Courses")
        courses["instructor"] = instructor_courses

        # get student courses
        student_courses, _ = get_courses_info(soup, "Student Courses")
        courses["student"] = student_courses

        return courses

    def get_course_users(self, course_id: str) -> List[Member]:
        """
        Get a list of all users in a course
        Returns:
            list: A list of users in the course (Member objects)
        Raises:
            Exceptions:
            "One or more invalid parameters": if course_id is null or empty value
            "You must be logged in to access this page.": if no user is logged in
        """

        membership_endpoint = (
            f"https://www.gradescope.com/courses/{course_id}/memberships"
        )

        # check that course_id is valid (not empty)
        if not course_id:
            raise Exception("Invalid Course ID")

        session = self.session

        try:
            # scrape page
            membership_resp = check_page_auth(session, membership_endpoint)
            membership_soup = BeautifulSoup(membership_resp.text, "html.parser")

            # get all users in the course
            users = get_course_members(membership_soup, course_id)

            return users
        except Exception as e:
            return None

    def get_assignments(self, course_id: str) -> List[Assignment]:
        """
        Get a list of detailed assignment information for a course
        Returns:
            list: A list of Assignments
        Raises:
            Exceptions:
            "One or more invalid parameters": if course_id or assignment_id is null or empty value
            "You are not authorized to access this page.": if logged in user is unable to access submissions
            "You must be logged in to access this page.": if no user is logged in
        """
        course_endpoint = f"https://www.gradescope.com/courses/{course_id}"
        # check that course_id is valid (not empty)
        if not course_id:
            raise Exception("Invalid Course ID")
        session = self.session
        # scrape page
        coursepage_resp = check_page_auth(session, course_endpoint)
        coursepage_soup = BeautifulSoup(coursepage_resp.text, "html.parser")

        # two different helper functions to parse assignment info
        # webpage html structure differs based on if user if instructor or student
        assignment_info_list = get_assignments_instructor_view(coursepage_soup)
        if not assignment_info_list:
            assignment_info_list = get_assignments_student_view(coursepage_soup)

        return assignment_info_list

    def create_assignment(self, course_id: str,
             name: str):

        GS_NEW_ASSIGNMENT_ENDPOINT = f"https://www.gradescope.com/courses/{course_id}/assignments/new"
        GS_POST_ASSIGNMENT_ENDPOINT = (
            f"https://www.gradescope.com/courses/{course_id}/assignments/"
        )
    
        # Get auth token
        response = self.session.get(GS_NEW_ASSIGNMENT_ENDPOINT)
        soup = BeautifulSoup(response.text, "html.parser")
        #auth_token = soup.select_one('input[name="authenticity_token"]')["value"]
        auth_token = soup.find_all(attrs={"name":"csrf-token"})[0]["content"]
    
        # Setup multipart form data
        multipart = MultipartEncoder(
            fields={
                #"utf8": "✓",
                #"_method": "patch",
                "authenticity_token": auth_token,
                "assignment[title]": ("HOMEWORK 2"),
                "template_pdf": ('filename', open('template.pdf', 'rb'), 'application/pdf'),
                "assignment[submissions_anonymized]": ("0"),
                "assignment[student_submission]": ("true"),
                "assignment[release_date_string]": (
                    "2024-09-08T09:00" #release_date.strftime("%Y-%m-%dT%H:%M") if release_date else ""
                ),
                "assignment[due_date_string]": (
                    "2024-09-15T23:59" #due_date.strftime("%Y-%m-%dT%H:%M") if due_date else ""
                ),
                "assignment[allow_late_submissions]": "0", #"1" if late_due_date else "0",
                "assignment[hard_due_date_string]": (
                    "2024-09-18T23:59" #late_due_date.strftime("%Y-%m-%dT%H:%M") if late_due_date else ""
                ),
                "assignment[enforce_time_limit]": ("0"),
                "assignment[submission_type]": ("image"),
                "assignment[group_submission]": ("0"),
                "assignment[when_to_create_rubric]": ("while_grading"),
                "assignment[template_visible_to_students]": ("0"),
                #"commit": "Save",
            }
        )
        headers = {
            "Content-Type": multipart.content_type,
            "Referer": GS_NEW_ASSIGNMENT_ENDPOINT,
        }
    
        response = self.session.post(
            GS_POST_ASSIGNMENT_ENDPOINT, data=multipart, headers=headers
        )
    
        print(response)
        print(response.text)
        #breakpoint()
        return response.status_code == 200


    def get_assignment_submissions(
        self, course_id: str, assignment_id: str
    ) -> Dict[str, List[str]]:
        """
        Get a list of dicts mapping AWS links for all submissions to each submission id
        Returns:
            dict: A dictionary of submissions, where the keys are the submission ids and the values are
            a list of aws links to the submission pdf
            For example:
                {
                    'submission_id': [
                        'aws_link1.com',
                        'aws_link2.com',
                        ...
                    ],
                    ...
                }
        Raises:
            Exceptions:
                "One or more invalid parameters": if course_id or assignment_id is null or empty value
                "You are not authorized to access this page.": if logged in user is unable to access submissions
                "You must be logged in to access this page.": if no user is logged in
                "Page not Found": When link is invalid: change in url, invalid course_if or assignment id
                "Image only submissions not yet supported": assignment is image submission only, which is not yet supported
        NOTE:
        1. Image submissions not supports, need to find an endpoint to retrieve image pdfs
        2. Not recommended for use, since this makes a GET request for every submission -> very slow!
        3. so far only accessible for teachers, not for students to get submissions to an assignment
        """
        ASSIGNMENT_ENDPOINT = f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}"
        ASSIGNMENT_SUBMISSIONS_ENDPOINT = f"{ASSIGNMENT_ENDPOINT}/review_grades"
        if not course_id or not assignment_id:
            raise Exception("One or more invalid parameters")
        session = self.session
        submissions_resp = check_page_auth(session, ASSIGNMENT_SUBMISSIONS_ENDPOINT)
        submissions_soup = BeautifulSoup(submissions_resp.text, "html.parser")
        # select submissions (class of td.table--primaryLink a tag, submission id stored in href link)
        submissions_a_tags = submissions_soup.select("td.table--primaryLink a")
        submission_ids = [
            a_tag.attrs.get("href").split("/")[-1] for a_tag in submissions_a_tags
        ]
        submission_links = {}
        for submission_id in submission_ids:  # doesn't support image submissions yet
            aws_links = get_submission_files(
                session, course_id, assignment_id, submission_id
            )
            submission_links[submission_id] = aws_links
            # sleep for 0.1 seconds to avoid sending too many requests to gradescope
            time.sleep(0.1)
        return submission_links

    def get_assignment_submission(
        self, student_email: str, course_id: str, assignment_id: str
    ) -> List[str]:
        """
        Get a list of aws links to pdfs of the student's most recent submission to an assignment
        Returns:
            list: A list of aws links as strings
            For example:
                [
                    'aws_link1.com',
                    'aws_link2.com',
                    ...
                ]
        Raises:
             Exceptions:
                "One or more invalid parameters": if course_id or assignment_id is null or empty value
                "You are not authorized to access this page.": if logged in user is unable to access submissions
                "You must be logged in to access this page.": if no user is logged in
                "Page not Found": When link is invalid: change in url, invalid course_if or assignment id
                "Image only submissions not yet supported": assignment is image submission only, which is not yet supported
        NOTE: so far only accessible for teachers, not for students to get their own submission
        """
        # fetch submission id
        ASSIGNMENT_ENDPOINT = f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}"
        ASSIGNMENT_SUBMISSIONS_ENDPOINT = f"{ASSIGNMENT_ENDPOINT}/review_grades"
        if not (student_email and course_id and assignment_id):
            raise Exception("One or more invalid parameters")
        session = self.session
        submissions_resp = check_page_auth(session, ASSIGNMENT_SUBMISSIONS_ENDPOINT)
        submissions_soup = BeautifulSoup(submissions_resp.text, "html.parser")
        td_with_email = submissions_soup.find(
            "td", string=lambda s: student_email in str(s)
        )
        if td_with_email:
            # grab submission from previous td
            submission_td = td_with_email.find_previous_sibling()
            # submission_td will have an anchor element as a child if there is a submission
            a_element = submission_td.find("a")
            if a_element:
                submission_id = a_element.get("href").split("/")[-1]
            else:
                raise Exception("No submission found")
        # call get_submission_files helper function
        aws_links = get_submission_files(
            session, course_id, assignment_id, submission_id
        )
        return aws_links
