from django import template
from django.template.defaultfilters import stringfilter
from updates.models import MangaSeries, MangaChapters
import re

register = template.Library()

@register.simple_tag
def num_tracked(request):
    return MangaSeries.objects.count()

@register.simple_tag
def num_paused(request):
    return MangaSeries.objects.filter(paused=True).count()

@register.simple_tag
def last_updated(request):
    try:
        return MangaSeries.objects.latest('last_updated').last_updated.strftime("%d-%m-%Y")
    except:
        return 'no manga in record'

@register.filter
@stringfilter
def return_chapter_num(chapter_string):
    x = re.search(r"[0-9]*$", chapter_string)
    return x.group(0)
