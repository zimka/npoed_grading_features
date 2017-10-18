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
