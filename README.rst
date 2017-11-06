Description
-----------
This package provides two features grading for OpenEdx: passing_grade and vertical_grading.

Passing_grade feature allows to specify in studio minimal percent that should be earned
for each assignment category. If these requirements are not met, course is considered as
not passed even if overall percent is high enough. Messages about failed categories are shown
to student at the progress page.

Vertical grading adds new way of grading: scores are given for units, and scores for problem are used
only to compute fraction of unit max score that student have earned.
E.g, unit has max score 5 and consists of Problem1(1 point) and Problem2(2 points). If student
passed first one and failed the last one, his would earn for this unit 5*(1/(2+1)) = 1.66 points.

It was tested on Ficus release `"open-release/ficus.2"
<https://github.com/edx/edx-platform/tree/open-release/ficus.2>`_

Vertical Grading Feature Installation
-------------------------------------

1. Install this package, add it into the INSTALLED_APPS and run migrations if it is not done yet.

   ::

     python -m pip install -e git+https://github.com/zimka/vertical_grading.git#egg=vertical-grading
     python manage.py lms migrate npoed_grading_features --settings=YOUR_SETTINGS

2. Apply decorator 'enable_vertical_grading' to the next classes/functions

    * lms.djangoapps.grades.new.subsection_grade.py: SubsectionGrade
    * lms.djangoapps.grades.new.subsection_grade.py: ZeroSubsectionGrade
    * common.lib.xmodule.xmodule.graders.py: AssignmentFormatGrader
    * common.lib.xmodule.xmodule.vertical_block.py: VerticalBlock
    * cms.djangoapps.contentstore.views.item.py: create_xblock_info


  Example:
  ::

     ...
     from npoed_grading_features import enable_vertical_grading

     @enable_vertical_grading
     class SubsectionGrade(SubsectionGradeBase):
     ...

4. Copy static from static/vertical_grading/:

   * cms.static.js.views.modals.course_outline_modals.js
   * cms.templates.course_outline.html
   * cms.templates.js.course-outline.underscore
   * cms.templates.js.weight-editor.underscore


5. Enable feature in settings

  ::

    FEATURES["ENABLE_VERTICAL_GRADING"] = True


6. At the admin dashboard find NpoedGradingFeatures and add desired course with "Passing Grade" flag on.


Passing Grade Feature Installation
-------------------------------------
1. Install this package, add it into the INSTALLED_APPS and run migrations if it is not done yet (same to vertical grading).

   ::

     python -m pip install -e git+https://github.com/zimka/vertical_grading.git#egg=vertical-grading
     python manage.py lms migrate npoed_grading_features --settings=YOUR_SETTINGS

2. Apply decorator 'enable_passing_grade' to the next classes/functions

  *  cms.djangoapps.models.settings.course_grading.py: CourseGradingModel
  *  lms.djangoapps.grade.new.course_grade.py: CourseGrade
  *  lms.djangoapps.courseware.views.py: is_course_passed
  *  lms.djangoapps.courseware.views.py: _credit_course_requirements


  Example:
  ::

     ...
     from npoed_grading_features import enable_passing_grade

     @enable_passing_grade
     def _credit_course_requirements
     ...

4. Copy static from static/passing_grade/:

   * cms.static.js.views.settings.grader.js
   * cms.templates.js.course_grade_policy.underscore

5. Enable feature in settings

  ::

    FEATURES["ENABLE_PASSING_GRADE"] = True


6. At the admin dashboard find NpoedGradingFeatures and add desired course with "Passing Grade" flag on.
