import pkgutil
import shutil
import os
from io import StringIO
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def get_package_file_stream(feature, x):
    name = 'static/' +feature + "/"+ x
    return StringIO(unicode(pkgutil.get_data("npoed_grading_features", name)))


def get_edx_file_stream(x):
    names = x.split(".")
    filename = ".".join(names[-2:])
    addr = _EDX_PLATFORM + "/".join(names[:-2]) + "/"+  filename
    return open(addr, 'w')


_EDX_PLATFORM = "/edx/app/edxapp/edx-platform/"
_STATIC_BY_TYPE = {
    "passing_grade": [
        "cms.static.js.views.settings.grader.js",
        "cms.templates.js.course_grade_policy.underscore"
    ],
    "vertical_grading": [
        "cms.static.js.views.modals.course_outline_modals.js",
        "cms.templates.course_outline.html",
        "cms.templates.js.course-outline.underscore",
        "cms.templates.js.weight-editor.underscore"
    ]
}
_ENABLED_BY_TYPE = {
    "passing_grade":"ENABLE_PASSING_GRADE",
    "vertical_grading":"ENABLE_VERTICAL_GRADING"
}


class Command(BaseCommand):
    """
    This command loads static files from package to edx. It's supposed
    that there is no difference in them since ginkgo release.
    """

    args = "<{passing_grade, vertical_grading}>"
    help = "Loads static for grading feature. Edx default static is replaced!"\
           "Example:" \
           "'./manage.py lms load_static_grading_feature passing_grade --settings=SETTINGS'"

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        feature_type = args[0]
        if feature_type not in _STATIC_BY_TYPE.keys():
            raise CommandError("Unknown feature type: '{}'. Use 'passing_grade' or 'vertical_grading'".format(feature_type))
        self.load_static(feature_type)

    def load_static(self, feature_type):
        if not settings.FEATURES.get(_ENABLED_BY_TYPE[feature_type]):
            message = "Feature '{}' is not enabled in django settings."" \
            ""Add key '{}' with value True, then run command again".format(
                feature_type,
                _ENABLED_BY_TYPE[feature_type]
            )
            raise CommandError(message)

        for name in _STATIC_BY_TYPE[feature_type]:
            f = get_package_file_stream(feature_type, name)
            g = get_edx_file_stream(name)
            shutil.copyfileobj(f, g)
        message = "Static were loaded successfully for feature '{}'.".format(feature_type)
        self.stdout.write(
            message
        )