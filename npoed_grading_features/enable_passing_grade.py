from functools import wraps
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .models import NpoedGradingFeatures, CoursePassingGradeUserStatus

NOT_PASSED_MESSAGE_TEMPLATE = _("You must earn {threshold_percent}% (got {student_percent}%) for {category}.")


def build_course_grading_model(class_):
    def parse_grader(json_grader):
        # manual to clear out kruft
        result = {"type": json_grader["type"],
                  "min_count": int(json_grader.get('min_count', 0)),
                  "drop_count": int(json_grader.get('drop_count', 0)),
                  "short_label": json_grader.get('short_label', None),
                  "weight": float(json_grader.get('weight', 0)) / 100.0,

                  "passing_grade": float(json_grader.get('passing_grade', 0)) / 100.0
                  }

        return result

    def jsonize_grader(i, grader):
        # Warning: converting weight to integer might give unwanted results due
        # to the reason how floating point arithmetic works
        # e.g, "0.29 * 100 = 28.999999999999996"
        return {
            "id": i,
            "type": grader["type"],
            "min_count": grader.get('min_count', 0),
            "drop_count": grader.get('drop_count', 0),
            "short_label": grader.get('short_label', ""),
            "weight": grader.get('weight', 0) * 100,

            "passing_grade": grader.get('passing_grade', 0) * 100,
        }
    class_.parse_grader = staticmethod(parse_grader)
    class_.jsonize_grader = staticmethod(jsonize_grader)
    return class_


def build_course_grade(class_):
    def _passing_grades(course_grade):
        graders = course_grade.course_data.course.grading_policy['GRADER']
        passing_grades = dict((x['type'], x['passing_grade']) for x in graders)
        return passing_grades

    def compute_categories_not_passed(course_grade):
        passing_grades = _passing_grades(course_grade)

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

    def switch_to_default(course_grade):
        course_id = course_grade.course_data.course.id
        result = not NpoedGradingFeatures.is_passing_grade_enabled(course_id)
        return result

    def _compute_passed(self, grade_cutoffs, percent):
        if switch_to_default(self):
            return self._default_compute_passed(grade_cutoffs, percent)
        nonzero_cutoffs = [cutoff for cutoff in grade_cutoffs.values() if cutoff > 0]
        success_cutoff = min(nonzero_cutoffs) if nonzero_cutoffs else None
        percent_passed = success_cutoff and percent >= success_cutoff
        category_not_passed_messages = compute_categories_not_passed(self)
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
        if switch_to_default(self):
            return summary

        passing_grades = _passing_grades(self)

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
        if switch_to_default(self):
            return self._default__compute_letter_rade(grade_cutoffs, percent)
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

    class_._default__compute_passed = class_._compute_passed
    class_._compute_passed = _compute_passed

    class_._default__compute_letter_grade = class_._compute_letter_grade
    class_._compute_letter_grade = _compute_letter_grade

    class_._default_summary = class_.summary
    class_.summary = property(summary)

    return class_


def build_is_course_passed(func):
    @wraps(func)
    def is_course_passed(course, grade_summary=None, student=None, request=None):
        breakdown = grade_summary['section_breakdown']
        failed_pass_grading = []
        for section in breakdown:
            is_averaged_result = section.get('prominent', False)
            if is_averaged_result and 'mark' in section:
                if section['mark'].get('detail',None):
                    failed_pass_grading.append(section['mark']['detail'])

        return bool(failed_pass_grading) and func(course, grade_summary, student, request)

    return is_course_passed


def build__credit_course_requirements(func):

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
    if not settings.FEATURES.get("ENABLE_PASSING_GRADE", False):
        return class_
    name = class_.__name__
    if name in replaced:
        constructor = replaced.get(name)
        return constructor(class_)
    return class_
