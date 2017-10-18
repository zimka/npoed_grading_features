Description
-----------
This package provides new way of grading for OpenEdx. It was tested on Ficus release `"open-release/ficus.2"
<https://github.com/edx/edx-platform/tree/open-release/ficus.2>`_

Installation
------------

1. Install this package and enable feature both in lms and cms:

::

  python -m pip install -e git+https://github.com/zimka/vertical_grading.git#egg=vertical-grading
  FEATURES["ENABLE_VERTICAL_GRADING"] = True

2. Add mixins:

  - VerticalGradingSubsectionMixin to lms.djangoapps.grade.new.subsection_grade.py:SubsectionGrade
  - VerticalGradingZeroSubsectionMixin  to lms.djangoapps.grade.new.subsection_grade.py:ZeroSubsectionGrade
  - VerticalGradingBlockMixin to common.lib.xmodule.xmodule.vertical_block.py:VerticalBlock

::
    from vertical_grading import VerticalGradingBlockMixin
    ...
    class VerticalBlock(VerticalGradingBlockMixin, ...):


3. Apply decorator vertical_grading_xblock_info to cms.djangoapps.contentstore.item.py:create_xblock_info

4. Put static files from static folder:

  - xblock_info.js int cms.static.js.models
  - course_outline_modals.js into cms.static.js.views.modals
  - course_outline.html into cms.templates
  - course-outline.underscore into cms.templates.js
  - weight-editor.underscore into cms.templates.js
