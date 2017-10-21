from lms.djangoapps.grades.scores import get_score, possibly_scored
from xmodule.graders import ProblemScore

from .utils import feature_enabled


class VerticalBase(object):
    """
    This is base class that provides new way to compute subsection score.
    To minimize invasions into edX code we use special hack.
    Because the main graded element in VG is vertical(unit) but not the problem,
    score for vertical is computed based on problems it consists of and ProblemScore
    with this result is forged. These forged ProblemScores are being fed to grader then.
    """
    VERTICAL_CATEGORY = "vertical"

    @classmethod
    def _vertical_enabled(cls):
        return feature_enabled()

    @classmethod
    def _get_vertical_score(
            cls,
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block=None
    ):
        if block_key.category != cls.VERTICAL_CATEGORY:
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
