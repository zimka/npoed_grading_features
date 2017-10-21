from functools import wraps
from django.conf import settings


def feature_enabled():
    return settings.FEATURES.get("ENABLE_VERTICAL_GRADING")


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


def vertical_grading_assignment_grade(grade):
    """
    This is decorator for common.lib.xmodule.xmodule.py:AssignmentFormatGrader.grade
    It replaces subsection min-value-score drop by vertical min-value-score drop
    """
    if not feature_enabled():
        return grade

    def drop_lowest_problems(category_grade_sheet, drop_count):
        if not drop_count:
            return category_grade_sheet
        locations_to_scores = {}
        for subsection_key in category_grade_sheet:
            current_locations_to_scores = category_grade_sheet[subsection_key].locations_to_scores

    @wraps(grade)
    def wrapped(self, grade_sheet, *args, **kwargs):
        drop_count = self.drop_count
        self.drop_count = 0
        current_sheet = grade_sheet.get(self.category)
        if current_sheet:
            for k, v in current_sheet.items():
                graded_total = v.graded_total
                if graded_total:
                    print(k,type(v), graded_total.earned, "/", graded_total.possible)
                else:
                    print(k,type(v), graded_total)
        else:
            print(self.category, "NO_SHEET")
        print("--------")
        grade_results = grade(self, grade_sheet, *args, **kwargs)
        self.drop_count = drop_count
        return grade_results

    return wrapped
