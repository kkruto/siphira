from django import template
from django.utils.safestring import mark_safe

from ..markdown import render as render_markdown

register = template.Library()


@register.filter(name='markdown')
def markdown_filter(value):
    return mark_safe(render_markdown(value))


@register.filter
def pct(part, whole):
    """Integer percentage, safe when the denominator is zero."""
    try:
        whole = float(whole)
        if whole <= 0:
            return 0
        return round(float(part) / whole * 100)
    except (TypeError, ValueError):
        return 0


@register.simple_tag
def query_replace(request, **kwargs):
    """Rebuild the querystring with some params swapped — for filters/paging."""
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f'?{encoded}' if encoded else '?'
