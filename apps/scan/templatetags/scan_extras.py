from django import template
from django.utils.http import urlencode
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from collections import Counter

register = template.Library()


@register.filter
def get_item(container, key):
    """Get item from dict or list by key/index."""
    if isinstance(container, dict):
        return container.get(str(key))
    if isinstance(container, list):
        try:
            return container[int(key)]
        except (IndexError, ValueError, TypeError):
            return None
    return None


@register.filter
def port_risk(port):
    """Classify port risk level."""
    high = {21, 23, 3389, 445, 139, 2375}
    medium = {22, 80, 443, 3306, 5432, 6379, 1433}
    low = {53, 5353, 5000, 7000, 9200, 5601}
    try:
        p = int(port)
    except (TypeError, ValueError):
        return 'Low'
    if p in high:
        return 'High'
    if p in medium:
        return 'Medium'
    return 'Low'


@register.filter
def mac_vendor_from_mac(mac):
    """Resolve MAC address to vendor name."""
    if not mac:
        return 'Unknown'
    from ..scanner import mac_to_vendor
    return mac_to_vendor(mac)


@register.simple_tag(takes_context=True)
def sort_url(context, field, label=''):
    """Generate sortable column header link with arrow indicator."""
    request = context.get('request')
    if not request:
        return label or field.replace('_', ' ').title()

    query = request.GET.copy()
    current_sort = context.get('current_sort', '')
    current_order = context.get('current_order', 'desc')

    # Toggle order if clicking same field, otherwise default to desc
    if current_sort == field:
        new_order = 'asc' if current_order == 'desc' else 'desc'
    else:
        new_order = 'desc'

    query['sort'] = field
    query['order'] = new_order
    query.pop('page', None)  # Reset to page 1 on sort change

    href = '?' + query.urlencode()
    text = label or field.replace('_', ' ').title()

    # Add arrow indicator if this is the active sort
    if current_sort == field:
        arrow = '▲' if current_order == 'asc' else '▼'
        text = mark_safe(f'{text} <span class="sort-arrow">{arrow}</span>')

    return format_html('<a href="{}">{}</a>', href, text)


@register.simple_tag(takes_context=True)
def duplicate_counts(context, field):
    """
    Return a dict of {value: count} for values that appear more than once.
    Uses the full filtered_queryset (DB aggregate) for accuracy across all pages.
    Falls back to current page items if no queryset available.
    """
    queryset = context.get('filtered_queryset')

    if queryset is not None:
        # DB-level aggregation — efficient even for large datasets
        try:
            from django.db.models import Count
            dupes = (
                queryset
                .exclude(**{f'{field}__isnull': True})
                .exclude(**{field: ''})
                .values(field)
                .annotate(_cnt=Count('id'))
                .filter(_cnt__gt=1)
            )
            return {entry[field]: entry['_cnt'] for entry in dupes}
        except Exception:
            pass

    # Fallback: count from current page only
    page_obj = context.get('page_obj')
    if not page_obj:
        return {}
    values = [getattr(obj, field, None) for obj in page_obj.object_list]
    counts = Counter(v for v in values if v)
    return {v: c for v, c in counts.items() if c > 1}


@register.filter
def is_duplicate(value, counts):
    """Check if a value appears in the duplicate counts dict."""
    if not value or not counts:
        return False
    return value in counts


@register.filter
def duplicate_count(value, counts):
    """Get the count for a duplicate value."""
    if not value or not counts:
        return 0
    return counts.get(value, 0)
