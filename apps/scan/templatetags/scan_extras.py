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
