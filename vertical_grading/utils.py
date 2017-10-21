from functools import wraps

from django.conf import settings
from xmodule.graders import ProblemScore

from lms.djangoapps.grades.scores import get_score


def feature_enabled():
    return settings.FEATURES.get("ENABLE_VERTICAL_GRADING")


def vertical_grading_assignment_grade(grade):
    """
    This is decorator for common.lib.xmodule.xmodule.py:AssignmentFormatGrader.grade
    It replaces subsection min-value-score drop by vertical min-value-score drop
    """
    if not feature_enabled():
        return grade

    def drop_lowest_problems(category_grade_sheet, drop_count):
        if not drop_count:
            return category_grade_sheet
        locations_to_scores = {}
        for subsection_key in category_grade_sheet:
            current_locations_to_scores = category_grade_sheet[subsection_key].locations_to_scores

    @wraps(grade)
    def wrapped(self, grade_sheet, *args, **kwargs):
        drop_count = self.drop_count
        self.drop_count = 0
        current_sheet = grade_sheet.get(self.category)
        if current_sheet:
            for k, v in current_sheet.items():
                graded_total = v.graded_total
                if graded_total:
                    print(k,type(v), graded_total.earned, "/", graded_total.possible)
                else:
                    print(k,type(v), graded_total)
        else:
            print(self.category, "NO_SHEET")
        print("--------")
        grade_results = grade(self, grade_sheet, *args, **kwargs)
        self.drop_count = drop_count
        return grade_results

    return wrapped


VERTICAL_CATEGORY = 'vertical'


def get_vertical_score(
        cls,
        block_key,
        course_structure,
        submissions_scores,
        csm_scores,
        persisted_block=None
):
    if block_key.category != VERTICAL_CATEGORY:
        return
    vertical_weight = getattr(course_structure[block_key], "weight", None)
    if not vertical_weight:
        return
    children_keys = course_structure.get_children(block_key)
    children_scores = []
    for child_key in children_keys:
        try:
            block = course_structure[child_key]
        except KeyError:
            # It's possible that the user's access to that
            # block has changed since the subsection grade
            # was last persisted.
            pass
        else:
            if getattr(block, 'has_score', False):
                problem_score = get_score(
                    submissions_scores,
                    csm_scores,
                    persisted_block,
                    block,
                )
                if problem_score:
                    children_scores.append(problem_score)
    if not children_scores:
        return
    vertical_possible = sum(score.possible for score in children_scores)
    vertical_earned = sum(score.earned for score in children_scores)
    weighted_earned = vertical_weight * float(vertical_earned) / vertical_possible
    weighted_possible = vertical_weight
    vertical_attempted = any(score.attempted for score in children_scores)
    vertical_graded = any(score.graded for score in children_scores)
    vertical_pseudo_problem = ProblemScore(
        raw_earned=vertical_earned,
        raw_possible=vertical_possible,
        weighted_earned=weighted_earned,
        weighted_possible=weighted_possible,
        weight=vertical_weight,
        graded=vertical_graded,
        attempted=vertical_attempted
    )
    return vertical_pseudo_problem