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
    def _compute_passed(self, grade_cutoff, percent):
        percent_passed =  self._compute_passed_percent(grade_cutoff, percent)
        cat_passed = self._compute_passed_by_category()
        return percent_passed and cat_passed

    def _compute_passed_by_category(self):
        graders = self.course_data.course.grading_policy['GRADER']
        passing_grades = dict( (x['type'], x['passing_grade']) for x in graders)

        breakdown = self.grader_result['section_breakdown']
        results = dict((x['category'], x['percent']) for x in breakdown)
        keys_match = len(results.keys()) == len(passing_grades.keys()) and \
            all(x in passing_grades for x in results)
        if not keys_match:
            # Error handling
            return True
        is_passed = all([results[category] > passing_grades[category] for category in results.keys()])
        return is_passed

    class_._compute_passed_percent = staticmethod(class_._compute_passed)
    class_._compute_passed_by_category = _compute_passed_by_category
    class_._compute_passed = _compute_passed
    return class_

replaced = {
    "CourseGradingModel": build_course_grading_model,
    "CourseGrade": build_course_grade,
}


def enable_passing_grade(obj):
    name = obj.__name__
    if name in replaced:
        constructor = replaced.get(name)
        return constructor(obj)
    return obj
