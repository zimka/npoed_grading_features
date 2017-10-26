from django.conf import settings
from .models import NpoedGradingFeatures

_ = lambda text: text


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

    def _compute_passed_by_category(course_grade):
        passing_grades = _passing_grades(course_grade)

        breakdown = course_grade.grader_result['section_breakdown']
        results = dict((x['category'], x['percent']) for x in breakdown)
        keys_match = len(results.keys()) == len(passing_grades.keys()) and \
            all(x in passing_grades for x in results)
        if not keys_match:
            # Error handling
            return True
        is_passed = all([results[category] > passing_grades[category] for category in results.keys()])
        return is_passed

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
        category_passed = _compute_passed_by_category(self)
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
                message = u'Not passed. You must earn {percent} percent for this category to pass.'.format(
                    percent=100*passing_grades[category]
                )
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


replaced = {
    "CourseGradingModel": build_course_grading_model,
    "CourseGrade": build_course_grade,
}


def enable_passing_grade(class_):
    if not settings.FEATURES.get("ENABLE_PASSING_GRADE", False):
        return class_
    name = class_.__name__
    if name in replaced:
        constructor = replaced.get(name)
        return constructor(class_)
    return class_
