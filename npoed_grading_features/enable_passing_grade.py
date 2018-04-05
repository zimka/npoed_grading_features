from functools import wraps
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .models import NpoedGradingFeatures, CoursePassingGradeUserStatus

NOT_PASSED_MESSAGE_TEMPLATE = _("You must earn {threshold_percent}% (got {student_percent}%) for {category}.")


def build_course_grading_model(class_):
    """
    Adding "passing_grade" to graders at reading to and writing from CourseGradingModel.
    """
    class UpdatedGradingModel(class_):
        def __init__(self, course_descriptor):
            super(UpdatedGradingModel, self).__init__(course_descriptor)
            self._update_graders(course_descriptor)

        def _update_graders(self, course_descriptor):
            key = "passing_grade"
            should_have = NpoedGradingFeatures.is_passing_grade_enabled(
                course_descriptor.location.course_key
            )
            for g in self.graders:
                has_key = key in g
                if has_key and not should_have:
                    g.pop(key)
                if should_have and not has_key:
                    g[key] = 0.

        @staticmethod
        def parse_grader(json_grader):
            # manual to clear out kruft
            result = class_.parse_grader(json_grader)
            passing_grade = json_grader.get('passing_grade', None)
            if passing_grade is not None:
                passing_grade = float(passing_grade) / 100.0
                result["passing_grade"] = passing_grade
            return result

        @staticmethod
        def jsonize_grader(i, grader):
            result = class_.jsonize_grader(i, grader)
            passing_grade = grader.get('passing_grade', None)
            if passing_grade is not None:
                passing_grade = float(passing_grade) * 100.0
                result["passing_grade"] = passing_grade
            return result

    return UpdatedGradingModel


def build_course_grade(class_):
    """
    Modifies CourseGrade. Changes .summary, _compute_passed and
    _compute_letter_grade to check category passing grades.
    Edx versions of method M are saved as _default_M.
    Also adds marks ('x' with message) at progress graph.
    """
    def inner_passing_grades(course_grade):
        graders = course_grade.course_data.course.grading_policy['GRADER']
        passing_grades = dict((x['type'], x.get('passing_grade',0)) for x in graders)
        return passing_grades

    def inner_categories_not_passed_messages(course_grade):
        passing_grades = inner_passing_grades(course_grade)

        breakdown = course_grade.grader_result['section_breakdown']
        results = dict((x['category'], x['percent']) for x in breakdown)
        keys_match = len(results.keys()) == len(passing_grades.keys()) and \
            all(x in passing_grades for x in results)
        if not keys_match:
            # Error handling
            return True

        messages = []
        for category in results.keys():
            if results[category] < passing_grades[category]:
                student_percent = int(round(results[category]*100))
                threshold_percent = int(round(passing_grades[category]*100))
                messages.append(NOT_PASSED_MESSAGE_TEMPLATE.format(
                    category=category,
                    student_percent=student_percent,
                    threshold_percent=threshold_percent
                ))
        return messages

    def inner_switch_to_default(course_grade):
        course_id = course_grade.course_data.course.id
        result = not NpoedGradingFeatures.is_passing_grade_enabled(course_id)
        return result

    def _compute_passed(self, grade_cutoffs, percent):
        if inner_switch_to_default(self):
            return default__compute_passed(grade_cutoffs, percent)
        nonzero_cutoffs = [cutoff for cutoff in grade_cutoffs.values() if cutoff > 0]
        success_cutoff = min(nonzero_cutoffs) if nonzero_cutoffs else None
        percent_passed = success_cutoff and percent >= success_cutoff
        category_not_passed_messages = inner_categories_not_passed_messages(self)
        CoursePassingGradeUserStatus.set_passing_grade_status(
            user=self.user,
            course_key=self.course_data.course.id,
            fail_status_messages=category_not_passed_messages
        )
        category_passed = len(category_not_passed_messages) == 0
        return percent_passed and category_passed

    def summary(self):
        summary = self._default_summary
        if self.passed:
            return summary
        if inner_switch_to_default(self):
            return summary

        passing_grades = inner_passing_grades(self)

        breakdown = self.grader_result['section_breakdown']
        results = dict((x['category'], x['percent']) for x in breakdown)
        for section in breakdown:
            category = section['category']
            is_averaged_result = section.get('prominent', False)
            is_not_passed = results[category] < passing_grades[category]
            if is_averaged_result and is_not_passed:
                student_percent = int(round(results[category]*100))
                threshold_percent = int(round(passing_grades[category]*100))
                message = NOT_PASSED_MESSAGE_TEMPLATE.format(
                    category=category,
                    student_percent=student_percent,
                    threshold_percent=threshold_percent
                )
                #message = u'Not passed. You must earn {percent} percent for this category to pass.'.format(
                #    percent=100*passing_grades[category]
                #)
                section['mark'] = {'detail': message}
        return summary

    def _compute_letter_grade(self, grade_cutoffs, percent):
        if inner_switch_to_default(self):
            return default__compute_letter_grade(grade_cutoffs, percent)
        letter_grade = None
        if not self.passed:
            percent = 0
        # Possible grades, sorted in descending order of score
        descending_grades = sorted(grade_cutoffs, key=lambda x: grade_cutoffs[x], reverse=True)
        for possible_grade in descending_grades:
            if percent >= grade_cutoffs[possible_grade]:
                letter_grade = possible_grade
                break

        return letter_grade

    default__compute_passed = class_._compute_passed
    class_._compute_passed = _compute_passed

    default__compute_letter_grade = class_._compute_letter_grade
    class_._compute_letter_grade = _compute_letter_grade

    class_._default_summary = class_.summary
    class_.summary = property(summary)

    return class_


def build_is_course_passed(func):
    """
    Checks if course passed.
    If grade_summary is given, next hack is used:
    grade_summary is modified by build_course_grade in such a way that
    failed_pass_messages are shown at the graph. So we try to get already
    calculated error messages from there.
    If student is given we try to get info from db.
    Otherwise consider that passing_grades are met, but actually there is no
    such calls of is_course_passed in edx currently.
    """
    @wraps(func)
    def is_course_passed(course, grade_summary=None, student=None, request=None):
        course_key = course.id
        if not NpoedGradingFeatures.is_passing_grade_enabled(course_key):
            return func(course, grade_summary, student, request)
        failed_pass_grading = []
        if grade_summary:
            breakdown = grade_summary['section_breakdown']
            failed_pass_grading = []
            for section in breakdown:
                is_averaged_result = section.get('prominent', False)
                if is_averaged_result and 'mark' in section:
                    if section['mark'].get('detail', None):
                        failed_pass_grading.append(section['mark']['detail'])
        elif student:
            failed_pass_grading = CoursePassingGradeUserStatus.get_passing_grade_status(course_key, student)

        is_category_grade_passed = not failed_pass_grading
        return is_category_grade_passed and func(course, grade_summary, student, request)

    return is_course_passed


def build__credit_course_requirements(func):
    """
    Adds unmet passing grade to the progress page.
    Messages are shown at the page as unmet credit requirements.
    """
    @wraps(func)
    def _credit_course_requirements(course_key, student):
        credit_requirements = func(course_key, student)
        if not NpoedGradingFeatures.is_passing_grade_enabled(course_key):
            return credit_requirements
        failed_categories = CoursePassingGradeUserStatus.get_passing_grade_status(course_key, student)
        if not failed_categories:
            return credit_requirements

        passing_grade_requirements = [{
            "namespace": "passing_grade",
            "name": "",
            "display_name": x,
            "criteria": "",
            "reason": "",
            "status": "",
            "status_date": None,
            "order": None,
        } for x in failed_categories]

        if credit_requirements is None:
            credit_requirements = {
                'eligibility_status': 'failed',
                'requirements': passing_grade_requirements,
            }
        else:
            credit_requirements['requirements'].extend(passing_grade_requirements)
            credit_requirements['eligibility_status'] = 'failed'
        return credit_requirements
    return _credit_course_requirements

replaced = {
    "CourseGradingModel": build_course_grading_model,
    "CourseGrade": build_course_grade,
    "is_course_passed": build_is_course_passed,
    "_credit_course_requirements": build__credit_course_requirements
}


def enable_passing_grade(class_):
    """
    This decorator should be applied to the edx
    classes/functions that are mentioned as keys in 'replaced'.
    """
    if not settings.FEATURES.get("ENABLE_GRADING_FEATURES", False):
        return class_
    name = class_.__name__
    if name in replaced:
        constructor = replaced.get(name)
        return constructor(class_)
    return class_
