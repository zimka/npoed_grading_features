"""
This file contains all necessary updates to apply vertical grading
"""
from collections import OrderedDict
from lazy import lazy

from django.conf import settings

from lms.djangoapps.grades.scores import get_score, possibly_scored
from xmodule.graders import ProblemScore


class VerticalBase(object):
    VERTICAL_CATEGORY = "vertical"

    def _vertical_enabled(self):
        return settings.FEATURES.get("ENABLE_VERTICAL_GRADING")

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
    This mixin should be inherited by SubsectionGrade.
    It provides two ways to compute scores: the 'classic' one and
    the 'unit-weighted' one.
    In case ot the last one units are considered as minimal graded element
    in course instead of the problem: they have their own weight, and problem's
    scores are used only to calculate complete percent for unit.
    Therefore it computes scores for units and mock them as problem scores.
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
