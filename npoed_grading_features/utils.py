from functools import wraps

from django.conf import settings
from .models import NpoedGradingFeatures


def feature_enabled(course_id):
    return settings.FEATURES.get("ENABLE_VERTICAL_GRADING") and NpoedGradingFeatures.is_vertical_grading_enabled(course_id)

VERTICAL_CATEGORY = 'vertical'


def get_vertical_score(
        block_key,
        course_structure,
        submissions_scores,
        csm_scores,
        persisted_block=None
):
    from lms.djangoapps.grades.scores import get_score, ProblemScore # placed here to avoid circular import

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
    inner_first_attempted = list(score.first_attempted for score in children_scores)
    vertical_attempted = max(inner_first_attempted) if inner_first_attempted else None
    vertical_graded = any(score.graded for score in children_scores)
    vertical_pseudo_problem = ProblemScore(
        raw_earned=vertical_earned,
        raw_possible=vertical_possible,
        weighted_earned=weighted_earned,
        weighted_possible=weighted_possible,
        weight=vertical_weight,
        graded=vertical_graded,
        first_attempted=vertical_attempted
    )
    return vertical_pseudo_problem


def drop_minimal_vertical_from_subsection_grades(subsection_grades):
    max_lost_points = -1
    max_lost_points_index = (-1, "None")

    for num, grade in enumerate(subsection_grades):
        for block_key, problem_score in grade.problem_scores.items():
            lost_points = problem_score.possible - problem_score.earned
            if lost_points > max_lost_points:
                max_lost_points = lost_points
                max_lost_points_index = (num, block_key)
    if max_lost_points == -1:
        return subsection_grades
    modified_grade = subsection_grades[max_lost_points_index[0]]
    subtracted_score = modified_grade.problem_scores.pop(max_lost_points_index[1])
    modified_grade.graded_total.earned -= subtracted_score.earned
    modified_grade.graded_total.possible -= subtracted_score.possible

    #TODO: should show all total?
    modified_grade.all_total.earned -= subtracted_score.earned
    modified_grade.all_total.possible -= subtracted_score.possible
    #TODO: should pop subsection grade or forbid to pop last problem score?
    if not modified_grade.graded_total.possible:
        modified_grade.graded_total.possible = 1e-6
    return subsection_grades
