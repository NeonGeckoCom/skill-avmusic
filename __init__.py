# -*- coding: utf-8 -*-
# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
#
# Copyright 2008-2020 Neongecko.com Inc. | All Rights Reserved
#
# Notice of License - Duplicating this Notice of License near the start of any file containing
# a derivative of this software is a condition of license for this software.
# Friendly Licensing:
# No charge, open source royalty free use of the Neon AI software source and object is offered for
# educational users, noncommercial enthusiasts, Public Benefit Corporations (and LLCs) and
# Social Purpose Corporations (and LLCs). Developers can contact developers@neon.ai
# For commercial licensing, distribution of derivative works or redistribution please contact licenses@neon.ai
# Distributed on an "AS IS” basis without warranties or conditions of any kind, either express or implied.
# Trademarks of Neongecko: Neon AI(TM), Neon Assist (TM), Neon Communicator(TM), Klat(TM)
# Authors: Guy Daniels, Daniel McKnight, Regina Bloomstine, Elon Gasper, Richard Leeds
#
# Specialized conversational reconveyance options from Conversation Processing Intelligence Corp.
# US Patents 2008-2020: US7424516, US20140161250, US20140177813, US8638908, US8068604, US8553852, US10530923, US10530924
# China Patent: CN102017585  -  Europe Patent: EU2156652  -  Patents Pending
import base64
import os
# import signal
import urllib.error
import urllib.parse
import urllib.request
import multiprocessing
import time
import pulsectl
# import pyautogui
import socket
# from os.path import dirname
from subprocess import Popen, PIPE  # DEVNULL, STDOUT,

import requests
from adapt.intent import IntentBuilder
from bs4 import BeautifulSoup, SoupStrainer
# from youtube_searcher import search_youtube
from pafy import pafy

from mycroft.skills import CommonPlaySkill, CPSMatchLevel
# from mycroft.skills.core import MycroftSkill
from mycroft.util.log import LOG
from NGI.utilities.utilHelper import NeonHelpers
# from mycroft.util import create_signal, check_for_signal
# try:
#     from mycroft.device import device as d_hw
# except ImportError:
#     d_hw = 'desktop'


def embed_url(video_url):
    import re
    LOG.info(video_url)
    regex = r"(?:http:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)"
    return re.sub(regex, r"https://www.youtube.com/embed/\1", video_url)


def playlist_url(video_url):
    LOG.info(video_url)
    LOG.info(str(video_url.rpartition('=')[2]))
    return "http://www.youtube.com/playlist?list=" + video_url.rpartition('list=')[2]


class AVmusicSkill(CommonPlaySkill):
    def __init__(self):
        super(AVmusicSkill, self).__init__(name="AVmusicSkill")
        self.process = None
        self.pause_opts = ['pause', 'pause now']
        self.resume_opts = ['resume', 'proceed', 'continue']
        self.next_opts = ['next', 'skip', 'forward']
        self.prev_opts = ['previous', 'back', 'last']
        # Available Options reflect profiles located in ~/.config/mpv/mpv.conf
        available_options = ["generic", "server", "neonX", "neonPi",
                             "neonAlpha", "neonU", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
        self.devType = self.configuration_available["devVars"]["devType"]
        if self.devType in available_options:
            try:
                if not os.path.isfile(os.path.expanduser('~/.config/mpv/mpv.conf')):
                    self.devType = None
            except Exception as e:
                LOG.error(e)
        else:
            self.devType = None

        self.request_queue = multiprocessing.Queue()
        self.pause_queue = multiprocessing.Queue()
        self.video_results = dict()
        self.requested_options = []
        # self.pid = []
        self.check_for_signal("AV_agreed_to_play")
        self.check_for_signal("AV_asked_to_wait")
        self.check_for_signal("AV_playback_paused")
        if not self.server:
            self.pulse = pulsectl.Pulse('Mycroft-audio-service')
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        default = {
            'sock_path': '/tmp/mpv',
            'volume': 1.0,
            'quack_api': "J0dvb2dsZWJvdC8yLjEgKCtodHRwOi8vd3d3Lmdvb2dsZS5jb20vYm90Lmh0bWwpJw=="
            # 'news_link': "https://nprdmp-live01-aac.akacast.akamaistream.net/7/91/364917/v1/npr."
            #              "akacast.akamaistream.net/nprdmp_live01_aac?ck=1510413392918",
            # "mobile_news_link": "https://podcasts.google.com/?feed="
            #                     "aHR0cHM6Ly93d3cubnByLm9yZy9yc3MvcG9kY2FzdC5waHA_aWQ9NTAwMDA1"
            }
        self.init_settings(default)

        self.sock_path = self.ngi_settings.content['sock_path']
        self.volume = self.ngi_settings.content['volume']
        self.quackagent = {'User-Agent': base64.b64decode(self.settings["quack_api"])}
        # self.npr_link = self.ngi_settings.content['news_link']
        # self.mobile_news_link = self.ngi_settings.content['mobile_news_link']

    def initialize(self):
        playnow_intent = IntentBuilder("playnow_intent").require("AgreementKeyword").build()
        self.register_intent(playnow_intent, self.handle_play_now_intent)

        not_now_intent = IntentBuilder("not_now_intent"). require("DeclineKeyword").build()
        self.register_intent(not_now_intent, self.handle_not_now_intent)

        # playback_control_intent = IntentBuilder("playback_control_intent").require("Playback").build()
        # self.register_intent(playback_control_intent, self.handle_playback_intent)

        # # if not check_for_signal('skip_wake_word', -1):
        # av_music = IntentBuilder("AVmusic_intent").require("AVmusicKeyword").optionally(
        #     "Neon").optionally("Mix").optionally("Repeat").optionally("Video").build()
        # # else:
        # #     av_music = IntentBuilder("AVmusic_intent"). \
        # #         require("Neon").require("AVmusicKeyword").optionally("Mix").optionally("Repeat").build()
        # self.register_intent(av_music, self.av_music)

        # self.load_data_files(dirname(__file__))

        self.disable_intent('playnow_intent')
        self.disable_intent('not_now_intent')

        self.add_event("playback_control.next", self._handle_next)
        self.add_event("playback_control.prev", self._handle_prev)
        self.add_event("playback_control.pause", self._handle_pause)
        self.add_event("playback_control.resume", self._handle_resume)

        self.gui.register_handler('avmusic.next', self._handle_next)
        self.gui.register_handler('avmusic.prev', self._handle_prev)

        # self.disable_intent('playback_control_intent')

    def CPS_match_query_phrase(self, phrase, message):
        if self.neon_in_request(message):
            # self.stop()
            self.requested_options = []
            utterance = phrase.lower()
            if self.check_for_signal('CORE_skipWakeWord', -1):
                if self.voc_match(phrase, 'Neon'):
                    pass
                    # utterance = utterance.replace(message.data.get('Neon'), "")  # TODO: Better parse DM
            LOG.info(utterance)
            # if "video" not in utterance:
            #     self.requested_options.append("music_only")
            #     utterance = utterance.replace("video", "")

            # Clean keywords from search string (utterance)
            if not self.voc_match(phrase, "Video") and "youtube" not in utterance:
                self.requested_options.append("music_only")
            elif self.voc_match(phrase, "Video"):
                pass
                # utterance = utterance.replace(message.data.get("Video"), "")  # TODO: Better parse DM

            if self.voc_match(phrase, "Repeat") and self.voc_match(phrase, "Mix"):
                self.requested_options.append("playlist_repeat")
                # utterance = utterance.replace(message.data.get('Mix'), "")  # TODO: Better parse DM
                # utterance = utterance.replace(message.data.get('Repeat'), "")  # TODO: Better parse DM
            elif self.voc_match(phrase, "Repeat"):
                self.requested_options.append("repeat")
                # utterance = utterance.replace(message.data.get('Repeat'), "")  # TODO: Better parse DM
            elif self.voc_match(phrase, "Mix"):
                self.requested_options.append("playlist")
                # utterance = utterance.replace(message.data.get('Mix'), "")
            # else:
            #     self.requested_options.append("news")
            LOG.info(self.requested_options)
            # utterance = utterance.replace(message.data.get('AVmusicKeyword'), '').strip()  # TODO: Better parse DM
            if utterance.split()[0] in ("a", "some"):
                utterance = " ".join(utterance.split()[1:])

            # self.start_the_mpv(["repeat", "custom", "music_only"], self.utterance)

            # Check for a given link and use that, else search passed phrase
            link = None
            results = None
            for word in message.context.get("cc_data", {}).get("raw_utterance", utterance).split():
                if word.startswith("https://"):
                    link = word
                    results = [link]
                    break
            if not link:
                LOG.debug(f"search: {utterance}")
                results = self.search(utterance)
                LOG.debug(results)
                if len(results) > 0:
                    link = embed_url(str(results[0]))
            LOG.info(f"Got video: {link}")

            if "news" in phrase and link:
                conf = CPSMatchLevel.GENERIC
            elif link:
                conf = CPSMatchLevel.TITLE
            else:
                conf = False
            return (phrase, conf, {"results": results, "link": link, "skill_gui": True})

    def CPS_start(self, phrase, data, message=None):
        link = data["link"]
        results = data["results"]
        if not link:
            LOG.error("No Link!!")
            self.speak("No Link!")
        else:
            if self.server:
                # self.speak(str(self.search(utterance + "playlist")))
                LOG.debug(f"Link to send: {link}")
                if link.startswith("https://www.youtube.com"):
                    # self.speak(link)

                    # Send link to conversation (for history and other users
                    self.send_with_audio(link, None, message)

                    # Emit to requesting mobile user
                    if message.context["mobile"]:
                        LOG.debug("mobile")
                        time.sleep(2)
                        # if "news" in utterance:
                        #     self.speak("Here is the latest from NPR")
                        #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
                        #     message.data.get("flac_filename"))
                        # else:
                        if link.startswith("https://www.youtube.com") and \
                                "https://www.googleadservices.com" not in link:
                            # self.speak("Here is your video.")
                            LOG.debug(f"emit link={link} to mobile")
                            self.socket_io_emit('link', f"&link={link}",
                                                message.context["flac_filename"])
                        elif link:
                            LOG.warning(f"malformed youtube link: {link}")
                            vid_id = link.split("&video_id=")[1].split("&")[0]
                            fixed_link = f"https://www.youtube.com/embed/{vid_id}"
                            LOG.debug(fixed_link)
                            self.socket_io_emit('link', f"&link={fixed_link}",
                                                message.context["flac_filename"])
                        else:
                            LOG.error("null link!")
                else:
                    LOG.warning(f"Bad Link: {link}")
                    self.speak_dialog('TryAgain')
                # if message.data.get("mobile"):
                #     time.sleep(2)
                #     # if "news" in utterance:
                #     #     self.speak("Here is the latest from NPR")
                #     #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
                #     #     message.data.get("flac_filename"))
                #     # else:
                #     if link.startswith("https://www.youtube.com") and \
                #             "https://www.googleadservices.com" not in link:
                #         # self.speak("Here is your video.")
                #         self.socket_io_emit('link', f"&link={link}",
                #                             message.data.get("flac_filename"))
                #     elif link:
                #         LOG.warning(f"malformed youtube link: {link}")
                #         vid_id = link.split("&video_id=")[1].split("&")[0]
                #         fixed_link = f"https://www.youtube.com/embed/{vid_id}"
                #         LOG.debug(fixed_link)
                #         self.socket_io_emit('link', f"&link={fixed_link}",
                #                             message.data.get("flac_filename"))
                #     else:
                #         LOG.error("null link!")
                #         else:
                #             self.speak_dialog('TryAgain')
                # else:
                # self.speak(embed_url(str(self.search(utterance + "playlist"))))

            # Handle non-server mobile
            elif message.context["mobile"]:
                # Emit to requesting mobile user
                time.sleep(2)
                # if "news" in utterance:
                #     self.speak("Here is the latest from NPR")
                #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
                #     message.data.get("flac_filename"))
                # else:
                if link.startswith("https://www.youtube.com") and \
                        "https://www.googleadservices.com" not in link:
                    # self.speak("Here is your video.")
                    self.socket_io_emit('link', f"&link={link}",
                                        message.context["flac_filename"])
                elif link:
                    LOG.warning(f"malformed youtube link: {link}")
                    vid_id = link.split("&video_id=")[1].split("&")[0]
                    fixed_link = f"https://www.youtube.com/embed/{vid_id}"
                    LOG.debug(fixed_link)
                    self.socket_io_emit('link', f"&link={fixed_link}",
                                        message.context["flac_filename"])
                else:
                    LOG.error("null link!")
            else:
                self.enable_intent('playnow_intent')
                self.enable_intent('not_now_intent')
                while not self.request_queue.empty():
                    LOG.warning(f"DM: AVMusic Queue isn't empty!!!")
                    self.request_queue.get()
                LOG.debug(f"add to queue: {results[0]}")
                self.request_queue.put(results[0])
                LOG.debug(self.request_queue.empty())
                self.video_results["local"] = {"current": 0, "results": results}
                if "http" not in phrase:
                    self.speak('Would you like me to play it now?', True)
                    t = multiprocessing.Process(target=self.check_timeout())  # TODO: Use skill event scheduler DM
                    t.start()
                else:
                    self.handle_play_now_intent()

                # self.speak('Would you like me to play it now?', True) if "http" not in phrase else \
                #     self.handle_play_now_intent()

    def search(self, text):
        # results = search_youtube(text)
        query = urllib.parse.quote(text)
        url = "https://www.youtube.com/results?search_query=" + query
        # response = urllib.request.urlopen(url)
        # html = response.read()

        response = requests.get(url, headers=self.quackagent)
        html = response.text
        a_tag = SoupStrainer('a')
        soup = BeautifulSoup(html, "html.parser", parse_only=a_tag)
        results = []
        LOG.debug(soup)
        for vid in soup.findAll(attrs={'class': 'yt-uix-tile-link'}):
            vid_suffix = vid['href']
            LOG.debug(vid_suffix)

            # Check if link is a video link
            if vid_suffix.startswith("/watch?v="):
                results.append(f"http://www.youtube.com{vid_suffix}")
                # Return first valid search result
                # return f"http://www.youtube.com{vid_suffix}"
            # if not vid['href'].startswith("https://googleads.g.doubleclick.net/‌​") \
            #         and not vid['href'].startswith("/user") and not vid['href'].startswith("/channel"):
            #     LOG.info("http://www.youtube.com/" + vid['href'])
            #     return "http://www.youtube.com/" + vid['href']
        return results

    # def av_music(self, message):
    #     # if (self.check_for_signal("skip_wake_word", -1) and message.data.get("Neon")) \
    #     #         or not self.check_for_signal("skip_wake_word", -1) or self.check_for_signal("CORE_neonInUtterance"):
    #     if self.neon_in_request(message):
    #         # self.stop()
    #         self.requested_options = []
    #         utterance = message.data.get('utterance').lower()
    #         if self.check_for_signal('CORE_skipWakeWord', -1):
    #             if message.data.get('Neon'):
    #                 utterance = utterance.replace(message.data.get('Neon'), "")
    #         LOG.info(utterance)
    #         # if "video" not in utterance:
    #         #     self.requested_options.append("music_only")
    #         #     utterance = utterance.replace("video", "")
    #
    #         # Clean keywords from search string (utterance)
    #         if not message.data.get("Video") and "youtube" not in utterance:
    #             self.requested_options.append("music_only")
    #         elif message.data.get("Video"):
    #             utterance = utterance.replace(message.data.get("Video"), "")
    #
    #         if message.data.get("Repeat") and message.data.get("Mix"):
    #             self.requested_options.append("playlist_repeat")
    #             utterance = utterance.replace(message.data.get('Mix'), "")
    #             utterance = utterance.replace(message.data.get('Repeat'), "")
    #         elif message.data.get("Repeat"):
    #             self.requested_options.append("repeat")
    #             utterance = utterance.replace(message.data.get('Repeat'), "")
    #         elif message.data.get("Mix"):
    #             self.requested_options.append("playlist")
    #             utterance = utterance.replace(message.data.get('Mix'), "")
    #         # else:
    #         #     self.requested_options.append("news")
    #         LOG.info(self.requested_options)
    #         utterance = utterance.replace(message.data.get('AVmusicKeyword'), '').strip()
    #         if utterance.split()[0] in ("a", "some"):
    #             utterance = " ".join(utterance.split()[1:])
    #
    #         # self.start_the_mpv(["repeat", "custom", "music_only"], self.utterance)
    #
    #         # Check for a given link and use that, else search passed phrase
    #         link = None
    #         results = None
    #         for word in message.context.get("cc_data", {}).get("raw_utterance", utterance).split():
    #             if word.startswith("https://"):
    #                 link = word
    #                 results = [link]
    #                 break
    #         if not link:
    #             LOG.debug(f"search: {utterance}")
    #             results = self.search(utterance)
    #             LOG.debug(results)
    #             if len(results) > 0:
    #                 link = embed_url(str(results[0]))
    #         LOG.info(f"Got video: {link}")
    #
    #         if not link:
    #             LOG.error("No Link!!")
    #             self.speak("No Link!")
    #         else:
    #             if self.server:
    #                 # self.speak(str(self.search(utterance + "playlist")))
    #                 LOG.debug(f"Link to send: {link}")
    #                 if link.startswith("https://www.youtube.com"):
    #                     # self.speak(link)
    #
    #                     # Send link to conversation (for history and other users
    #                     self.send_with_audio(link, None, message)
    #
    #                     # Emit to requesting mobile user
    #                     if message.context["mobile"]:
    #                         LOG.debug("mobile")
    #                         time.sleep(2)
    #                         # if "news" in utterance:
    #                         #     self.speak("Here is the latest from NPR")
    #                         #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
    #                         #     message.data.get("flac_filename"))
    #                         # else:
    #                         if link.startswith("https://www.youtube.com") and \
    #                                 "https://www.googleadservices.com" not in link:
    #                             # self.speak("Here is your video.")
    #                             LOG.debug(f"emit link={link} to mobile")
    #                             self.socket_io_emit('link', f"&link={link}",
    #                                                 message.context["flac_filename"])
    #                         elif link:
    #                             LOG.warning(f"malformed youtube link: {link}")
    #                             vid_id = link.split("&video_id=")[1].split("&")[0]
    #                             fixed_link = f"https://www.youtube.com/embed/{vid_id}"
    #                             LOG.debug(fixed_link)
    #                             self.socket_io_emit('link', f"&link={fixed_link}",
    #                                                 message.context["flac_filename"])
    #                         else:
    #                             LOG.error("null link!")
    #                 else:
    #                     LOG.warning(f"Bad Link: {link}")
    #                     self.speak_dialog('TryAgain')
    #                 # if message.data.get("mobile"):
    #                 #     time.sleep(2)
    #                 #     # if "news" in utterance:
    #                 #     #     self.speak("Here is the latest from NPR")
    #                 #     #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
    #                 #     #     message.data.get("flac_filename"))
    #                 #     # else:
    #                 #     if link.startswith("https://www.youtube.com") and \
    #                 #             "https://www.googleadservices.com" not in link:
    #                 #         # self.speak("Here is your video.")
    #                 #         self.socket_io_emit('link', f"&link={link}",
    #                 #                             message.data.get("flac_filename"))
    #                 #     elif link:
    #                 #         LOG.warning(f"malformed youtube link: {link}")
    #                 #         vid_id = link.split("&video_id=")[1].split("&")[0]
    #                 #         fixed_link = f"https://www.youtube.com/embed/{vid_id}"
    #                 #         LOG.debug(fixed_link)
    #                 #         self.socket_io_emit('link', f"&link={fixed_link}",
    #                 #                             message.data.get("flac_filename"))
    #                 #     else:
    #                 #         LOG.error("null link!")
    #                 #         else:
    #                 #             self.speak_dialog('TryAgain')
    #                 # else:
    #                 # self.speak(embed_url(str(self.search(utterance + "playlist"))))
    #
    #             # Handle non-server mobile
    #             elif message.context["mobile"]:
    #                 # Emit to requesting mobile user
    #                 time.sleep(2)
    #                 # if "news" in utterance:
    #                 #     self.speak("Here is the latest from NPR")
    #                 #     self.socket_io_emit('link', f"&link={self.mobile_news_link}",
    #                 #     message.data.get("flac_filename"))
    #                 # else:
    #                 if link.startswith("https://www.youtube.com") and \
    #                         "https://www.googleadservices.com" not in link:
    #                     # self.speak("Here is your video.")
    #                     self.socket_io_emit('link', f"&link={link}",
    #                                         message.context["flac_filename"])
    #                 elif link:
    #                     LOG.warning(f"malformed youtube link: {link}")
    #                     vid_id = link.split("&video_id=")[1].split("&")[0]
    #                     fixed_link = f"https://www.youtube.com/embed/{vid_id}"
    #                     LOG.debug(fixed_link)
    #                     self.socket_io_emit('link', f"&link={fixed_link}",
    #                                         message.context["flac_filename"])
    #                 else:
    #                     LOG.error("null link!")
    #             else:
    #                 self.enable_intent('playnow_intent')
    #                 self.enable_intent('not_now_intent')
    #                 while not self.request_queue.empty():
    #                     LOG.warning(f"DM: AVMusic Queue isn't empty!!!")
    #                     self.request_queue.get()
    #                 self.request_queue.put(results)
    #                 self.speak('Would you like me to play it now?', True) if "http" not in \
    #                     message.data.get("utterance") else self.handle_play_now_intent()
    #                 t = multiprocessing.Process(target=self.check_timeout())
    #                 t.start()
    #
    #     # else:
    #     #     self.check_for_signal("CORE_andCase")

    def check_started(self):
        LOG.debug('socket start')
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists(self.sock_path):
            os.remove(self.sock_path)
        timeout = time.time() + 10
        while not os.path.exists(self.sock_path):
            if time.time() > timeout:
                break
            time.sleep(0.2)
        try:
            self.socket.connect(self.sock_path)
            fixed_vol = False
        except Exception as e:
            LOG.error(e)
            return

        try:
            while not fixed_vol and time.time() < timeout:
                for sink in self.pulse.sink_input_list():
                    try:
                        # LOG.debug('sink: ' + str(sink.name))
                        if str(sink.proplist.get('application.name')) == 'AVmusic':
                            # LOG.debug('DM: Found AVmusic!')
                            volume = sink.volume
                            volume.value_flat = self.volume
                            self.pulse.volume_set(sink, volume)
                            fixed_vol = True
                    except Exception as e:
                        LOG.error(e)
                        fixed_vol = True
                time.sleep(0.2)
            LOG.debug(self.socket.recv(2048))
        except Exception as e:
            LOG.error(e)

    def check_timeout(self):
        time_start = time.time()
        if not self.pause_queue.empty():
            while self.check_for_signal("AV_playback_paused", -1):
                if time.time() - time_start >= 50:
                    LOG.info("Paused too long")
                    self.pause_queue.get()
                    self.check_for_signal("AV_agreed_to_play")
                    self.check_for_signal("AV_playback_paused")
                    self.create_signal("AV_stoppedFromPause")
                    # self.disable_intent('playback_control_intent')
                    self.stop()
                    return

        if not self.request_queue.empty():
            while not self.check_for_signal("AV_agreed_to_play", -1):
                if time.time() - time_start >= 30:
                    if not self.check_for_signal("AV_asked_to_wait"):
                        self.request_queue.get()
                        LOG.info("Too much time passed")
                        self.disable_intent('not_now_intent')
                        self.disable_intent('playnow_intent')
                        self.clear_signals('AV_')
                        # self.disable_intent('playback_control_intent')
                        break
                    else:
                        LOG.info('Asked to wait')
                        time.sleep(20)
                        self.request_queue.get()

    # def handle_playback_intent(self, message):
    #     try:
    #         if not self.gui_enabled:
    #             self.socket.send(b'{"command": ["get_property_string", "pause"]}\n')
    #             response = self.socket.recv(1024).decode('utf-8')
    #             # LOG.debug(response)
    #             if '"data":"no"' in str(response):
    #                 paused = False
    #             else:
    #                 paused = True
    #         else:
    #             paused = None
    #         # LOG.debug(message.data.get('utterance'))
    #         # LOG.debug(message.data.get('Playback'))
    #         cmd = message.data.get('Playback')
    #         if cmd in self.prev_opts:
    #             command = b'{"command": ["playlist_prev"]}\n'
    #             self.speak("Skipping back")
    #         elif cmd in self.next_opts:
    #             command = b'{"command": ["playlist_next"]}\n'
    #             self.speak("Skipping next")
    #         elif cmd in self.pause_opts:
    #             command = b'{"command": ["set", "pause", "yes"]}\n'
    #             LOG.debug(f"DM: pause command, paused status was: {paused}")
    #             if self.gui_enabled:
    #                 self.gui["status"] = "pause"
    #             if not paused:
    #                 self.speak_dialog('SayResume', {'ww': self.user_info_available['listener']['wake_word'].title()})
    #         elif cmd in self.resume_opts:
    #             command = b'{"command": ["set", "pause", "no"]}\n'
    #             LOG.debug(f"DM: resume command, paused status was: {paused}")
    #             if self.gui_enabled:
    #                 self.gui["status"] = "play"
    #                 self.speak("Resuming playback")
    #             elif paused:
    #                 self.speak("Resuming playback")
    #         else:
    #             command = None
    #
    #         # If not gui, send mpv socket command
    #         if command and not self.gui_enabled:
    #             self.socket.send(command)
    #             LOG.debug(self.socket.recv(1024))
    #
    #         # if "pause" in message.data.get('utterance'):
    #         #     # if self.pause_queue.empty():
    #         #     self.socket.send(b'{"command": ["set", "pause", "yes"]}\n')
    #         #     LOG.debug(self.socket.recv(1024))
    #         #     self.speak_dialog('SayResume', {'ww': self.user_info_available['listener']['wake_word'].title()})
    #         #     # self.speak("The playback is paused. Say resume if you would like to continue")
    #         #     # self.pause_queue.put(self.process.pid)
    #         #     # t = multiprocessing.Process(target=self.check_timeout())
    #         #     # t.start()
    #         #     # self.create_signal("AV_playback_paused")
    #         #     #     # self.create_signal("AV_asked_to_wait")
    #         #     # # else:
    #         #     # #     self.speak("I am already holding a song for you. Say continue if you "
    #         #     #                "wish to play it or stop to exit")
    #         #     #     return
    #         # elif "next" in message.data.get('utterance'):
    #         #     self.socket.send(b'{"command": ["playlist_next"]}\n')
    #         #     LOG.debug(self.socket.recv(1024))
    #         # elif "previous" in message.data.get('utterance'):
    #         #     self.socket.send(b'{"command": ["playlist_prev"]}\n')
    #         #     LOG.debug(self.socket.recv(1024))
    #         # else:
    #         #     self.socket.send(b'{"command": ["set", "pause", "no"]}\n')
    #         #     LOG.debug(self.socket.recv(1024))
    #         #     # if not self.pause_queue.empty():
    #         #     #     self.speak("Alright, continuing")
    #         #     #     self.pause_queue.get()
    #         #     #     self.check_for_signal('AV_playback_paused')
    #         #     # else:
    #         #     #     self.speak("There is nothing to continue because I do not have anything on pause")
    #         #     #     return
    #         #
    #         # # pyautogui.moveTo(x=self.screen_width/2, y=self.screen_height/2)
    #         # # pyautogui.press('p')
    #     except Exception as e:
    #         LOG.info(e)
    #         self.stop()
    #         # if self.check_for_signal("AV_WW"):
    #         #     NeonHelpers.disable_ww()

    def handle_play_now_intent(self):
        # TODO: Handle playback over
        # self.enable_intent('playback_control_intent')
        self.create_signal("AV_agreed_to_play")
        self.check_for_signal("AV_asked_to_wait")
        self.disable_intent('not_now_intent')
        self.disable_intent('playnow_intent')
        self.create_signal("AV_active")
        if self.check_for_signal('CORE_skipWakeWord', -1):
            NeonHelpers.enable_ww()
            self.create_signal("AV_WW")
        LOG.debug(self.request_queue.empty())
        if not self.request_queue.empty():
            results = self.request_queue.get()
        elif self.video_results.get("local"):
            results = self.video_results["local"]["results"]
        else:
            results = None
        if results:
            try:
                self.speak_dialog('SayStop', {'ww': self.user_info_available['listener']['wake_word'].title()})
                # if d_hw == 'pi':
                #     self.process = Popen(["mpv", "--vid=no", self.search(utterance)],
                #                          stdout=DEVNULL, stderr=STDOUT)
                # else:
                LOG.debug(f"DM: {results}")
                # results = self.search(utterance)
                if results:
                    LOG.debug(results)
                    if isinstance(results, str):
                        link = results
                    elif isinstance(results, list):
                        link = results[0]
                    else:
                        link = None
                        LOG.error(f"No link in results={results}")
                    if "playlist" in self.requested_options and not self.gui_enabled:
                        # TODO: Gui handle playlists DM
                        LOG.info("playlist requested")
                        for result in results:
                            if "&list=" in result:
                                link = playlist_url(result)
                                break
                else:
                    link = None
                LOG.debug(link)

                if not link:
                    self.speak("No Results")
                else:
                    if self.gui_enabled:
                        LOG.debug(results)
                        video = pafy.new(link)
                        playstream = video.streams[0]
                        LOG.info(video)
                        self.gui["title"] = str(video).split(":", 1)[1].strip().split("\n", 1)[0]
                        self.gui["videoSource"] = playstream.url
                        self.gui["status"] = "play"  # play, stop, pause
                        self.gui.show_page("Video.qml")
                    else:
                        self.start_the_mpv(self.requested_options, link)
                        if self.process:
                            output, error = self.process.communicate()
                            # First Playback Attempt Failed
                            if self.process.returncode != 0 and not self.check_for_signal("AV_stoppedFromPause"):
                                LOG.info("Failed at request:  %d %s %s" % (self.process.returncode, output, error))
                                # LOG.info("Trying again")
                                # if self.process.pid in self.pid:
                                #     self.pid.remove(self.process.pid)
                                try:
                                    LOG.debug("Second Attempt Start")
                                    self.start_the_mpv(self.requested_options, results[1])
                                    LOG.debug("Second Attempt Done")
                                    output, error = self.process.communicate()
                                    # Second Playback Attempt Failed
                                    if self.process:
                                        if self.process.returncode != 0 and not\
                                                self.check_for_signal("AV_stoppedFromPause"):
                                            LOG.info("Failed at request:  %d %s %s" % (self.process.returncode, output,
                                                                                       error))
                                            self.speak_dialog('TryAgain')
                                            self.stop()
                                            # if self.check_for_signal("AV_WW"):
                                            #     NeonHelpers.disable_ww()
                                except TypeError or Exception as e:
                                    LOG.error(e)
                                    self.speak_dialog('TryAgain')
                                    self.stop()
                        else:
                            self.disable_intent('playback_control_intent')
                            try:
                                # self.pause_queue.get()
                                # self.pause_queue.get()
                                self.check_for_signal("AV_agreed_to_play")
                                self.check_for_signal("AV_playback_paused")
                            except Exception as e:
                                LOG.error(e)
                                self.stop()
                            # if self.check_for_signal("AV_WW"):
                            #     NeonHelpers.disable_ww()

            except TypeError or Exception as e:
                LOG.error(e)
                self.speak_dialog('TryAgain')
                # if self.check_for_signal("AV_WW"):
                #     NeonHelpers.disable_ww()
                self.stop()

            self.check_for_signal("AV_agreed_to_play")

    def start_the_mpv(self, options, vid_link, retry=False):
        LOG.info(vid_link)
        param_options = ["mpv", "--force-window", "--volume=100", "--audio-client-name=AVmusic",
                         "--input-ipc-server=" + self.sock_path]
        if self.devType:
            options.append("custom")

        if not retry:
            options_final = [self.options_mpv(x) for x in options if self.options_mpv(x) is not None]
        else:
            options_final = []
        param_options.extend(options_final)
        LOG.info(param_options)
        param_options.append(vid_link)
        # if "http" not in vid_link:
        #     results = self.search(vid_link)
        # param_options.append(str(playlist_url(results[0])) if
        #                      "playlist" in str(options) else str(self.search(vid_link)))
        # else:
        #     LOG.warning(f"Link passed as utterance! {vid_link}")
        #     # param_options.remove("--vid=no")
        #     vid_link = vid_link.replace('video', '').strip()
        #     param_options.append(vid_link)
        LOG.info(param_options)
        try:
            self.process = Popen(param_options, stdout=PIPE, stdin=PIPE, stderr=PIPE)
            self.check_started()
            # self.pid.append(self.process.pid)
        except Exception as e:
            LOG.info(e)
        # LOG.info(self.pid)

    def options_mpv(self, x):
        return {
            'music_only': "--vid=no",
            'repeat': '--loop',
            'playlist_repeat': '--loop-playlist',
            'custom': "--profile=" + self.devType if self.devType else None
            # 'news': str(self.npr_link)
        }.get(x, "")

    def handle_not_now_intent(self):
        self.create_signal("AV_asked_to_wait")
        self.speak_dialog('ChangeMind')
        self.disable_intent('not_now_intent')

    def _handle_pause(self, message):
        if self.check_for_signal("AV_active"):
            if self.gui_enabled:
                self.gui["status"] = "pause"
            elif not self.server:
                command = b'{"command": ["set", "pause", "yes"]}\n'
                self.socket.send(command)
                LOG.debug(self.socket.recv(1024))
            self.speak_dialog('SayResume', {'ww': self.user_info_available['listener']['wake_word'].title()},
                              message=message)

    def _handle_resume(self, message):
        if self.check_for_signal("AV_active"):
            if self.gui_enabled:
                self.gui["status"] = "play"
            elif not self.server:
                command = b'{"command": ["set", "pause", "no"]}\n'
                self.socket.send(command)
                LOG.debug(self.socket.recv(1024))
            self.speak("Resuming playback", message=message)

    def _handle_next(self, message):
        LOG.debug("got here")
        user = "local"
        if self.gui_enabled:
            if user in self.video_results.keys():
                track_list = self.video_results[user].get("results")
                playing = self.video_results[user].get("current")
                playing += 1
                LOG.info(f"skipping. new source={track_list[playing]}")

                video = pafy.new(track_list[playing])
                playstream = video.streams[0]
                LOG.info(video)
                self.gui["title"] = str(video).split(":", 1)[1].strip().split("\n", 1)[0]
                self.gui["videoSource"] = playstream.url
                self.gui["status"] = "play"  # play, stop, pause
                self.video_results[user]["current"] = playing

        elif not self.server and self.check_for_signal("AV_active", -1):
            command = b'{"command": ["playlist_next"]}\n'
            self.socket.send(command)
            LOG.debug(self.socket.recv(1024))
        self.speak("Skipping next", message=message)

    def _handle_prev(self, message):
        user = "local"
        if self.gui_enabled:
            if user in self.video_results.keys():
                track_list = self.video_results[user].get("results")
                playing = self.video_results[user].get("current")
                playing -= 1
                if playing < 0:
                    playing = 0
                LOG.info(f"skipping. new source={track_list[playing]}")

                video = pafy.new(track_list[playing])
                playstream = video.streams[0]
                LOG.info(video)
                self.gui["title"] = str(video).split(":", 1)[1].strip().split("\n", 1)[0]
                self.gui["videoSource"] = playstream.url
                self.gui["status"] = "play"  # play, stop, pause
                self.video_results[user]["current"] = playing

        elif not self.server and self.check_for_signal("AV_active", -1):
            if self.gui_enabled:
                pass
            elif not self.server:
                command = b'{"command": ["playlist_prev"]}\n'
                self.socket.send(command)
                LOG.debug(self.socket.recv(1024))
        self.speak("Skipping back", message=message)

    def stop(self):
        if not self.server:
            if self.gui_enabled:
                self.gui.clear()
            else:
                if self.check_for_signal("AV_active"):
                    try:
                        self.socket.send(b'{"command": ["quit"]}\n')
                        self.socket.close()
                    except Exception as e:
                        LOG.error(e)
                    # self.disable_intent("playback_control_intent")

            if self.check_for_signal("AV_WW"):
                time.sleep(0.5)
                NeonHelpers.disable_ww()

            self.clear_signals('AV_')

            # Ensure queue is empty before next request
            while not self.request_queue.empty():
                self.request_queue.get()

        # if self.process:
        #     self.check_for_signal("AV_agreed_to_play")
        #     self.check_for_signal("AV_asked_to_wait")
        #     self.check_for_signal("AV_playback_paused")
        #     LOG.info(self.pid)
        #     if self.process.pid in self.pid:
        #         self.pid.remove(self.process.pid)
        #     self.process.terminate()
        #     self.process.kill()
        #     self.process = None
        # if self.pid:
        #     for i in range(len(self.pid)):
        #         os.kill(i, signal.SIGTERM)


def create_skill():
    return AVmusicSkill()
