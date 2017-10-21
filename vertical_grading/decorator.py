from collections import OrderedDict
from functools import wraps

from lazy import lazy

from xblock.fields import Integer, Scope

from .utils import get_vertical_score, feature_enabled
from lms.djangoapps.grades.scores import possibly_scored
_ = lambda text: text


def build_subsection_grade(class_):

    def _vertical_compute_block_score(
            self,
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block=None,
    ):
        vertical_pseudo_problem_score = get_vertical_score(
            block_key,
            course_structure,
            submissions_scores,
            csm_scores,
            persisted_block
        )
        if vertical_pseudo_problem_score:
            self.locations_to_scores[block_key] = vertical_pseudo_problem_score

    def _compute_block_score(self, *args, **kwargs):
        if feature_enabled():
            return self._vertical_compute_block_score(*args, **kwargs)
        else:
            return self._problem_compute_block_score(self, *args, **kwargs)

    class_._problem_compute_block_score = class_._compute_block_score
    class_._vertical_compute_block_score = _vertical_compute_block_score
    class_._compute_block_score = _compute_block_score
    return class_


def build_zero_subsection_grade(class_):

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
            vertical_score = VerticalBase._get_vertical_score(
                block_key,
                course_structure=self.course_data.structure,
                submissions_scores={},
                csm_scores={},
                persisted_block=None,
            )
            if vertical_score:
                locations[block_key] = vertical_score
        return locations

    def locations_to_scores(self):
        if feature_enabled():
            return self._vertical_locations_to_scores
        else:
            return self._old_locations_to_scores

    class_._old_locations_to_scores = class_.locations_to_scores
    class_._vertical_locations_to_scores = lazy(_vertical_locations_to_scores)
    class_.locations_to_scores = property(locations_to_scores)
    return class_


def build_vertical_block(class_):
    class_.weight = Integer(
        display_name=_("Weight"),
        help=_(
            "Defines the contribution of the vertical to the category score."),
        default=0.0,
        scope=Scope.settings
    )
    return class_


def build_create_xblock_info(func):
    return vertical_grading_xblock_info(func)

replaced = {
    "SubsectionGrade": build_subsection_grade,
    "ZeroSubsectionGrade": build_zero_subsection_grade,
    "VerticalBlock": build_vertical_block,
    "create_xblock_info": build_create_xblock_info
}


def enable_vertical_grading(obj):
    name = obj.__name__
    if name in replaced:
        constructor = replaced.get(name)
        return constructor(obj)
    return obj


def vertical_grading_xblock_info(create_xblock_info):
    """
    This is decorator for cms.djangoapps.contentstore.item.py:create_xblock_info
    It adds vertical block weight to the available for rendering info
    """
    if not feature_enabled():
        return create_xblock_info

    @wraps(create_xblock_info)
    def wrapped(*args, **kwargs):
        xblock = kwargs.get('xblock', False) or args[0]
        xblock_info = create_xblock_info(*args, **kwargs)
        if xblock_info.get("category", False) == 'vertical':
            weight = getattr(xblock, 'weight', 0)
            xblock_info['weight'] = weight
            parent_xblock = kwargs.get('parent_xblock', None)
            if parent_xblock:
                xblock_info['format'] = parent_xblock.format
        return xblock_info

    return wrapped