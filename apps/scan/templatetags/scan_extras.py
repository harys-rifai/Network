from django import template
from django.utils.http import urlencode
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(container, key):
    if isinstance(container, dict):
        return container.get(str(key))
    if isinstance(container, list):
        try:
            return container[int(key)]
        except (IndexError, ValueError):
            return None
    return None

@register.filter
def port_risk(port):
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
    if not mac:
        return 'Unknown'
    from ..scanner import mac_to_vendor
    return mac_to_vendor(mac)

@register.simple_tag(takes_context=True)
def sort_url(context, field, label=''):
    request = context.get('request')
    if not request:
        return label or field
    query = request.GET.copy()
    current_sort = query.get('sort', '')
    current_order = query.get('order', 'desc')
    if current_sort == field:
        if current_order == 'asc':
            query['order'] = 'desc'
        else:
            query['order'] = 'asc'
    else:
        query['sort'] = field
        query['order'] = 'desc'
    query.pop('page', None)
    href = '?' + query.urlencode()
    text = label or field
    if current_sort == field:
        if current_order == 'asc':
            text = mark_safe(text + ' <span class="sort-arrow">▲</span>')
        else:
            text = mark_safe(text + ' <span class="sort-arrow">▼</span>')
    return format_html('<a href="{}">{}</a>', href, text)

@register.simple_tag(takes_context=True)
def duplicate_counts(context, field):
    request = context.get('request')
    page_obj = context.get('page_obj')
    if not page_obj:
        return {}
    queryset = context.get('filtered_queryset') or page_obj.object_list
    from collections import Counter
    values = [getattr(obj, field) for obj in queryset if getattr(obj, field)]
    counts = Counter(values)
    return {val: cnt for val, cnt in counts.items() if cnt > 1}

@register.filter
def is_duplicate(value, counts):
    if not value:
        return False
    return counts.get(value, 0) > 1

@register.filter
def duplicate_count(value, counts):
    if not value:
        return 0
    return counts.get(value, 0)
