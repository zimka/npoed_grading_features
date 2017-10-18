"""
This file contains mixins that should be used in edx to apply vertical grading.
"""
from collections import OrderedDict
from lazy import lazy

from xblock.fields import Integer, Scope


from lms.djangoapps.grades.scores import get_score, possibly_scored
from xmodule.graders import ProblemScore

from .utils import feature_enabled
_ = lambda text: text


class VerticalBase(object):
    """
    This is base class that provides new way to compute subsection score.
    To minimize invasions into edX code we use special hack.
    Because the main graded element in VG is vertical(unit) but not the problem,
    score for vertical is computed based on problems it consists of and ProblemScore
    with this result is forged. These forged ProblemScores are being fed to grader then.
    """
    VERTICAL_CATEGORY = "vertical"

    def _vertical_enabled(self):
        return feature_enabled()

    def _get_vertical_score(
            self,
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block=None
    ):
        if block_key.category != self.VERTICAL_CATEGORY:
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


class VerticalGradingSubsectionMixin(VerticalBase):
    """
    This mixin should be inherited by lms.djangoapps.grade.new.subsection_grade.py:SubsectionGrade.
    It changes the way score is computed for subsection.
    """

    def __init__(self, *args, **kwargs):
        if self._vertical_enabled():
            self._compute_block_score = self._vertical_compute_block_score
        super(VerticalGradingSubsectionMixin, self).__init__(*args, **kwargs)

    def _vertical_compute_block_score(
            self,
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block=None,
    ):
        vertical_pseudo_problem_score = self._get_vertical_score(
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block
        )
        if vertical_pseudo_problem_score:
            self.locations_to_scores[block_key] = vertical_pseudo_problem_score


class VerticalGradingZeroSubsectionMixin(VerticalBase):
    """
    This mixin should be inherited by lms.djangoapps.grade.new.subsection_grade.py:ZeroSubsectionGrade.
    """
    def __init__(self, *args, **kwargs):
        if self._vertical_enabled():
            self.locations_to_scores = self._vertical_locations_to_scores
        super(VerticalGradingZeroSubsectionMixin).__init__(*args, **kwargs)

    @lazy
    def _vertical_locations_to_scores(self):
        """
        Overrides the locations_to_scores member variable in order
        to return empty scores for all scorable problems in the
        course.
        """
        locations = OrderedDict()  # dict of problem locations to ProblemScore
        for block_key in self.course_data.structure.post_order_traversal(
                filter_func=possibly_scored,
                start_node=self.location,
        ):
            vertical_score = self._get_vertical_score(
                block_key,
                course_structure=self.course_data.structure,
                submissions_scores={},
                csm_scores={},
                persisted_block=None,
            )
            if vertical_score:
                locations[block_key] = vertical_score
        return locations


class VerticalGradingBlockMixin(object):
    """
    This is mixin for common.lib.xmodule.xmodule.vertical_block.py:VerticalBlock
    It adds field 'weight' field to the verticals
    """
    weight = Integer(
        display_name=_("Weight"),
        help=_(
            "Defines the contribution of the vertical to the category score."),
        default=0.0,
        scope=Scope.settings
    )
