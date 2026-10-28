from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))



def submit(request, course_id):
    if not request.user.is_authenticated:
        return redirect("onlinecourse:login")

    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(
        Enrollment, user=request.user, course=course
    )

    if request.method == "POST":
        submission = Submission.objects.create(enrollment=enrollment)

        for choice_id in extract_answers(request):
            choice = get_object_or_404(
                Choice, pk=choice_id, question__course=course
            )
            submission.choices.add(choice)

        return redirect(
            "onlinecourse:show_exam_result",
            course_id=course.id,
            submission_id=submission.id,
        )

    return redirect("onlinecourse:course_details", pk=course.id)


def extract_answers(request):
    answers = []
    for key in request.POST:
        if key.startswith("choice"):
            try:
                answers.append(int(request.POST[key]))
            except (ValueError, TypeError):
                continue
    return answers


def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect("onlinecourse:login")

    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course,
    )

    selected_ids = set(submission.choices.values_list("id", flat=True))
    questions = Question.objects.filter(course=course).prefetch_related(
        "choice_set"
    )

    total_score = 0
    max_score = 0
    question_results = []

    for question in questions:
        max_score += question.grade
        correct_ids = set(
            question.choice_set.filter(is_correct=True).values_list(
                "id", flat=True
            )
        )
        question_choice_ids = set(
            question.choice_set.values_list("id", flat=True)
        )
        selected_for_question = selected_ids.intersection(
            question_choice_ids
        )
        is_correct = bool(correct_ids) and selected_for_question == correct_ids

        if is_correct:
            total_score += question.grade

        question_results.append({
            "question": question,
            "selected_choices": question.choice_set.filter(
                id__in=selected_for_question
            ),
            "correct_choices": question.choice_set.filter(is_correct=True),
            "is_correct": is_correct,
        })

    grade = round(total_score * 100 / max_score) if max_score else 0

    context = {
        "course": course,
        "submission": submission,
        "grade": grade,
        "score": total_score,
        "total_score": max_score,
        "question_results": question_results,
    }
    return render(
        request, "onlinecourse/exam_result_bootstrap.html", context
    )


