from django.shortcuts import render
from django.urls import reverse_lazy

from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.core.exceptions import ValidationError

from django.core.files import File
import tempfile

from django import forms
from .forms import AddMangaForm
from .models import MangaSeries, MangaChapters

from django.core import files
from io import BytesIO

from bs4 import BeautifulSoup
import requests
import pandas as pd
import json
import csv
import re

from datetime import datetime, timedelta

#Class to get values from the manga webpage
class MangaURLValues(object):
    def __init__(self, manga_URL):
        self.manga_URL = manga_URL
        # parse soup and return as page_content
        page_response = requests.get(str(self.manga_URL))
        page_content = BeautifulSoup(page_response.content, "html.parser")
        self.page_content = page_content

    #This function --> returns the list of all chapters for a manga website URL
    def get_chapterList(self):
        chapterList = []
        #use beautifulsoup to
        filtered = self.page_content.findAll(lambda tag: tag.name == 'div' and tag.get('class') == ['row'])[:10]
        #for all div tags in the soup, find the ones with class == 'row' EXACTLY
        #output first 10 chapters
        if not filtered:
            filtered = self.page_content.findAll(lambda tag: tag.name == 'li' and tag.get('class') == ['a-h'])[:10]
        for div in filtered:
            #under each div tag, find the title of the a tag, which contains the title of the manga
            chapter = div.find('a')['href']
            #Adds a new entry to the list for every chapter
            chapterList.append(chapter)
        self.chapterList = chapterList
        return self.chapterList

    #This function --> returns the name of manga from soup
    #param {manga_URL} --> the URL of website
    #uses self.get_soup()
    def get_mangaName(self):
        manga_firstTag = self.page_content.find("ul", { "class" : "manga-info-text" })
        try:
            if manga_firstTag is None:
                self.mangaName = self.page_content.find("div", { "class" : "story-info-right" }).find('h1').text
            else:
                self.mangaName = manga_firstTag.findNext('h1').text
        except:
            return False
        return self.mangaName

    def get_mangaImage(self):
        try:
            self.link = self.page_content.find("span", { "class" : "info-image" }).find('img')['src']
        except:
            self.link = self.page_content.find("div", { "class" : "manga-info-pic" }).find('img')['src']
        return self.link

    def get_latestChapter(self):
        chapter_fullName = self.page_content.find(lambda tag: tag.name == 'div' and tag.get('class') == ['row'])
        if not chapter_fullName:
            chapter_fullName = self.page_content.find(lambda tag: tag.name == 'li' and tag.get('class') == ['a-h'])
        self.chapter_name = chapter_fullName.find('a').contents[0]
        return self.chapter_name


# Create your views here.

# order the objects being displayed --> paused at the bottom --> otherwise name alphabetical
### add a pause and delete button ###

def homepage(request):
    if request.method == 'POST':
        request_button = request.POST
        if 'pause' in request_button:
            to_pause = request_button.getlist('pause')[0]
            manga = MangaSeries.objects.get(pk=to_pause)
            manga.paused = True
            manga.save()
        elif 'unpause' in request_button:
            to_unpause = request_button.getlist('unpause')[0]
            manga = MangaSeries.objects.get(pk=to_unpause)
            manga.paused = False
            manga.save()
        elif 'delete' in request_button:
            to_delete = request_button.getlist('delete')[0]
            manga = MangaSeries.objects.get(pk=to_delete).delete()

    if request.user.is_authenticated:
        manga_series = MangaSeries.objects.filter(user=request.user).order_by('paused')
        return render(request, "index.html", {'manga_series':manga_series})
    else:
        return render(request, "index.html")

@login_required
def add_manga(request):
    if request.method == 'POST':
        # get data from form
        form = AddMangaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            manga_URL = data['manga_URL']
            user = request.user

            # use class to get manga name and list of 10 latest chapters
            website = MangaURLValues(manga_URL)
            website_manga_name = website.get_mangaName()
            website_manga_chapters = website.get_chapterList() # list of ten latest chapters as a URL
            website_latest_chapter = website.get_latestChapter() # name of latest chapter
            # datetime object for when manga is added
            now = datetime.now()

            ### VALIDATION NEEDED FOR NO CHAPTERS AND URL 404 NOT FOUND
            # error message needs to be red
            if website_manga_name == False:
                messages.add_message(request, messages.INFO, "manga not found.")
                return render(request, "add_manga.html", {"form":form})

            # add the manga series to database
            manga_series_data = MangaSeries(name=website_manga_name, manga_URL=manga_URL, last_updated=now, latest_chapter=website_latest_chapter, user=user)
            manga_series_data.save()

            # add image
            image_URL = str(website.get_mangaImage())
            print(image_URL)
            resp = requests.get(image_URL, stream=True)
            # if image exists
            #if resp.status_code == requests.codes.ok:

            file_name = image_URL.split("/")[-1]
            lf = tempfile.NamedTemporaryFile()
            # Read the streamed image in sections
            for block in resp.iter_content(1024 * 8):
                # If no more file then stop
                if not block:
                    break
                # Write image block to temporary file
                lf.write(block)
            manga_series_data.image.save(file_name, files.File(lf))

            # add the 10 lateste chapters associated with the manga series
            for chapter in website_manga_chapters:
                manga_latest_data = MangaChapters(chapter_URL=chapter, manga_series=manga_series_data, user=user)
                manga_latest_data.save()

            messages.add_message(request, messages.INFO, str(website_manga_name) + " successfully added.")
    else:
        form = AddMangaForm()

    return render(request, "add_manga.html", {"form":form})

@login_required
def update_manga(request):
    if request.method == 'POST':
        request_button = request.POST
        if 'update_now' in request_button:
            user = request.user

            display_list = []
            all_updated = []

            for manga in MangaSeries.objects.filter(paused=False):
                manga_URL = manga.manga_URL
                manga_chapters = MangaChapters.objects.filter(manga_series=manga)
                website = MangaURLValues(manga_URL)

                # update the last_updated field
                manga.last_updated = datetime.now()
                manga.latest_chapter = website.get_latestChapter()
                manga.save()

                old_chapters_list = manga_chapters.values_list('chapter_URL', flat=True)
                updated_chapters_list = website.get_chapterList()

                difference_manga_list = sorted([item for item in updated_chapters_list if item not in old_chapters_list])

                if difference_manga_list:
                    # update database with newest CHAPTERS

                    ### what is more efficient? delete all chapters and update??? ORRR delete the difference and update???
                    manga_chapters.delete()
                    for chapter in updated_chapters_list:
                        manga_latest_data = MangaChapters(chapter_URL=chapter, manga_series=manga, user=user)
                        manga_latest_data.save()

                    # open the chapters
                    display_dict = {}
                    display_dict['manga'] = manga
                    display_dict['update_list'] = difference_manga_list
                    display_list.append(display_dict)

                    all_updated.extend([{"url":url, "name":manga.name + " chapter " + str(re.search(r"[0-9]*$", url).group(0))} for url in difference_manga_list])

            if display_list:
                 new_manga_flag = True
            else:
                new_manga_flag = False

            return render(request, "update_manga_display.html", {"display_list":display_list, "all_updated":json.dumps(all_updated), "new_manga_flag":new_manga_flag})
    else:
        return render(request, "update_manga.html")
