from django import template

register = template.Library()

@register.filter
def sum_attribute(sequence, attribute):
    """Суммирует значения атрибута в последовательности"""
    return sum(getattr(item, attribute, 0) for item in sequence)