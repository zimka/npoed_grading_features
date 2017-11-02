from django.db import models
from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey
import json

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


class CoursePassingGradeUserStatus(models.Model):
    course_id = models.CharField(max_length=255)
    user = models.ForeignKey(User)
    fail_status_messages = models.TextField(
        verbose_name="Message that specifies what user has to do to pass"
    )

    class Meta:
        unique_together = ("course_id", "user")

    @classmethod
    def get_passing_grade_status(cls, course_key, user):
        course_id = str(course_key)
        if not NpoedGradingFeatures.is_passing_grade_enabled(course_id):
            raise ValueError("Passing grade is not enabled for course {}.".format(
                course_id
            ))
        try:
            row = cls.objects.get(course_id=course_id, user=user)
            messages = json.loads(row.fail_status_messages)
        except cls.DoesNotExist:
            messages = tuple("You progress is not processed yet")
        return messages

    @classmethod
    def set_passing_grade_status(cls, course_key, user, fail_status_messages):
        course_id = str(course_key)
        if not NpoedGradingFeatures.is_passing_grade_enabled(course_id):
            raise ValueError("Passing grade is not enabled for course {}.".format(
                course_id
            ))
        row, created = cls.objects.get_or_create(course_id=course_id, user=user)
        row.fail_status_messages = json.dumps(fail_status_messages)
        row.save()
