import ddt
from mock import patch

from openedx.core.djangolib.testing.utils import get_mock_request

from lms.djangoapps.grades.new.course_grade_factory import CourseGradeFactory, CourseData
from lms.djangoapps.grades.tests.utils import answer_problem

from student.models import CourseEnrollment
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase, SharedModuleStoreTestCase

from .test_utils import BuildCourseMixin


@patch.dict('django.conf.settings.FEATURES', {'ENABLE_VERTICAL_GRADING': True})
class TestExpectedGrading(ModuleStoreTestCase, BuildCourseMixin):
    """
    Check that our testing method in BuildCourseMixin correctly calculates grade
    for course represented by tree.
    This test class uses a hard-coded block
    hierarchy with scores as follows:
                                                a
                                       +--------+--------+
                                       b                 c
                        +--------------+-----------+     |
                        d 5            e 1         f     g 10
                     +-----+     +-----+-----+     |     |
                     h     i     j     k     l     m     n
                   (2/5) (3/5) (0/1)   -   (1/3)   -   (6/10)

    """
    def setUp(self):
        super(TestExpectedGrading, self).setUp()
        self.course = CourseFactory.create()
        with self.store.bulk_operations(self.course.id):
            self.a = ItemFactory.create(parent=self.course, category="chapter", display_name="a")
            metadata = {'format':'Homework', 'graded':True}
            self.b = ItemFactory.create(parent=self.a, category="sequential", display_name="b", metadata=metadata)
            self.c = ItemFactory.create(parent=self.a, category="sequential", display_name="c", metadata=metadata)
            self.d = ItemFactory.create(parent=self.b, category="vertical", display_name="d")
            self.e = ItemFactory.create(parent=self.b, category="vertical", display_name="e")
            self.f = ItemFactory.create(parent=self.b, category="vertical", display_name="f")
            self.g = ItemFactory.create(parent=self.c, category="vertical", display_name="g")
            metadata.pop('graded')
            self.h = ItemFactory.create(parent=self.d, category="problem", display_name="h", metadata=metadata)
            self.i = ItemFactory.create(parent=self.d, category="problem", display_name="i", metadata=metadata)
            self.j = ItemFactory.create(parent=self.e, category="problem", display_name="j", metadata=metadata)
            self.k = ItemFactory.create(parent=self.e, category="html", display_name="k")
            self.l = ItemFactory.create(parent=self.e, category="problem", display_name="l", metadata=metadata)
            self.m = ItemFactory.create(parent=self.f, category="html", display_name="m")
            self.n = ItemFactory.create(parent=self.g, category="problem", display_name="n", metadata=metadata)

        grading_policy = {
            "GRADER": [
                {
                    "type": "Homework",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "HW",
                    "weight": 1.0,
                },
            ],
            "GRADE_CUTOFFS": {
                "Pass": 0.5,
            },
        }

        self.course.set_grading_policy(grading_policy)
        self.store.update_item(self.course, 0)
        self.course = self.store.get_course(self.course.id)

        self.request = get_mock_request(UserFactory())
        CourseEnrollment.enroll(self.request.user, self.course.id)

        answer_problem(self.course, self.request, self.h, score=2, max_value=5)
        answer_problem(self.course, self.request, self.i, score=3, max_value=5)
        answer_problem(self.course, self.request, self.j, score=0, max_value=1)
        answer_problem(self.course, self.request, self.l, score=1, max_value=3)
        answer_problem(self.course, self.request, self.n, score=6, max_value=10)

    def test_percents_coincide(self):
        """
        Checks that grade returned by .grade_tree method and manually calculated
        one are equal.
        """
        course_grade = CourseGradeFactory().create(self.request.user, self.course)
        pc = course_grade.percent
        subsection_grades = [
            (2. + 3. + 0. + 1.) / (5. + 5. + 1. + 3.),
            6./10
        ]
        expected_grade = sum(subsection_grades)/len(subsection_grades)
        expected_pc = round(expected_grade * 100 + 0.05) / 100
        self.assertEqual(pc, expected_pc)
        tree = {
            "a": {
                "b": ("Homework", {
                    "d": (1., {"h": (2., 5.), "i": (3., 5.),}),
                    "e": (1., {"j": (0., 1.), "k": (None, None), "l":(1.,3)}),
                    "f": (1., {"m":(None, None)})
                }),
                "c": ("Homework", {
                    "g": (1, {"n": (6., 10)})
                })
            }
        }
        computed_expected_pc = self._grade_tree(tree, enable_vertical=False)
        self.assertEqual(pc, computed_expected_pc)


@ddt.ddt
class TestCourseBuilding(ModuleStoreTestCase, BuildCourseMixin):
    """
    Tests that our testing method in BuildCourseMixin builds course correctly from
    tree, and calculated grades are correct for both Vertical and classical grading
                                                a
                                       +--------+--------+
                                       b                 c
                        +--------------+-----------+     |
                        d 5            e 1         f     g 10
                     +-----+     +-----+-----+     |     |
                     h     i     j     k     l     m     n
                   (2/5) (3/5) (0/1)   -   (1/3)   -   (6/10)

    """
    def setUp(self):
        super(TestCourseBuilding, self).setUp()
        self.course = CourseFactory.create()
        self.request = get_mock_request(UserFactory())

        grading_policy = {
            "GRADER": [
                {
                    "type": "Homework",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "HW",
                    "weight": 1.0,
                },
            ],
            "GRADE_CUTOFFS": {
                "Pass": 0.5,
            },
        }

        self.course.set_grading_policy(grading_policy)
        self.store.update_item(self.course, 0)
        self.course = self.store.get_course(self.course.id)
        CourseEnrollment.enroll(self.request.user, self.course.id)

    @ddt.data(False, True)
    def test_percent(self, enable_vertical):
        tree = {
            "a": {
                "b": ("Homework", {
                    "d": (0., {"h": (2., 5.), "i": (3., 5.),}),
                    "e": (1., {"j": (0., 1.), "k": (None, None), "l":(1.,3)}),
                    "f": (0., {"m":(None, None)})
                }),
                "c": ("Homework", {
                    "g": (0, {"n": (6., 10)})
                })
            }
        }
        self._enable_if_needed(enable_vertical)
        self._build_from_tree(tree)
        self._check_tree(tree, self.course)
        course_grade = CourseGradeFactory().create(self.request.user, self.course)
        pc = course_grade.percent

        subsection_grades = [
            (2. + 3. + 0. + 1.) / (5. + 5. + 1. + 3.),
            6./10
        ]
        expected_grade = sum(subsection_grades)/len(subsection_grades)
        if enable_vertical:
            expected_grade = 0.25
        expected_pc = round(expected_grade * 100 + 0.05) / 100
        self.assertEqual(pc, expected_pc)
        computed_expected_pc = self._grade_tree(tree, enable_vertical)
        self.assertEqual(pc, computed_expected_pc)
