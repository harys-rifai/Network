from django import template

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
