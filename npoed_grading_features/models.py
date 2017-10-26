from django.db import models
from opaque_keys.edx.keys import CourseKey

_FEATURES = (
    "vertical_grading",
    "passing_grade"
)


class NpoedGradingFeatures(models.Model):
    """
    This models defines for which courses npoed grading features are enabled.
    """
    course_id = models.CharField(max_length=255, unique=True)
    vertical_grading = models.BooleanField(default=False)
    passing_grade = models.BooleanField(default=False)
    silence_minimal_grade_credit_requirement = models.BooleanField(
        default=True,
        verbose_name="This fields fixes auto-generation of minimal_grade requirement." \
                     "If you want to use this credit requirement, you must turn it OFF."
    )
    @classmethod
    def is_vertical_grading_enabled(cls, course_id):
        return cls._is_feature_enabled(course_id, 'vertical_grading')

    @classmethod
    def is_passing_grade_enabled(cls, course_id):
        return cls._is_feature_enabled(course_id, 'passing_grade')

    @classmethod
    def enable_vertical_grading(cls, course_id):
        cls._switch_feature(course_id, "vertical_grading", True)

    @classmethod
    def enable_passing_grade(cls, course_id):
        cls._switch_feature(course_id, "passing_grade", True)

    @classmethod
    def disable_vertical_grading(cls, course_id):
        cls._switch_feature(course_id, "vertical_grading", False)

    @classmethod
    def disable_passing_grade(cls, course_id):
        cls._switch_feature(course_id, "passing_grade", False)

    @classmethod
    def get(cls, course_id):
        cid = cls._get_id(course_id)
        try:
            return cls.objects.get(course_id=cid)
        except cls.DoesNotExist:
            return None

    @classmethod
    def _get_id(cls, course_id):
        if isinstance(course_id, CourseKey):
            return str(course_id)
        return course_id

    @classmethod
    def _is_feature_enabled(cls, course_id, feature):
        cid = cls._get_id(course_id)
        try:
            grading_features = cls.objects.get(course_id=cid)
            return getattr(grading_features, feature)
        except cls.DoesNotExist:
            return False

    @classmethod
    def _switch_feature(cls, course_id, feature, state):
        cid = cls._get_id(course_id)
        grading_features, created = cls.objects.get_or_create(course_id=cid)
        setattr(grading_features, feature, state)
        grading_features.save()
