# -*- coding: utf-8 -*-
# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
#
# Copyright 2008-2021 Neongecko.com Inc. | All Rights Reserved
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
# US Patents 2008-2021: US7424516, US20140161250, US20140177813, US8638908, US8068604, US8553852, US10530923, US10530924
# China Patent: CN102017585  -  Europe Patent: EU2156652  -  Patents Pending

import os
import multiprocessing
import time
import pulsectl
import socket

from subprocess import Popen, PIPE

from mycroft_bus_client import Message
from neon_utils.message_utils import request_from_mobile
from youtube_searcher import search_youtube
from adapt.intent import IntentBuilder
from pafy import pafy
from neon_utils.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from neon_utils.logger import LOG
from mycroft.util.log import LOG
# from NGI.utilities.utilHelper import NeonHelpers


def embed_url(video_url):
    import re
    LOG.info(video_url)
    regex = r"(?:http:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)"
    return re.sub(regex, r"www.youtube.com/embed/\1", video_url)


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
        self.sock_path = self.settings['sock_path']
        self.volume = float(self.settings['volume'])

    def initialize(self):
        playnow_intent = IntentBuilder("playnow_intent").require("AgreementKeyword").build()
        self.register_intent(playnow_intent, self.handle_play_now_intent)

        not_now_intent = IntentBuilder("not_now_intent"). require("DeclineKeyword").build()
        self.register_intent(not_now_intent, self.handle_not_now_intent)

        self.disable_intent('playnow_intent')
        self.disable_intent('not_now_intent')

        # CommonPlay Event Handlers
        self.add_event("playback_control.next", self._handle_next)
        self.add_event("playback_control.prev", self._handle_prev)
        self.add_event("playback_control.pause", self._handle_pause)
        self.add_event("playback_control.resume", self._handle_resume)

        # Gui Event Handlers
        self.gui.register_handler('avmusic.next', self._handle_next)
        self.gui.register_handler('avmusic.prev', self._handle_prev)

        # self.disable_intent('playback_control_intent')

    def CPS_match_query_phrase(self, phrase, message):
        self.requested_options = []
        utterance = phrase.lower()
        if self.check_for_signal('CORE_skipWakeWord', -1):
            if self.voc_match(phrase, 'Neon'):
                pass
        LOG.info(utterance)

        # Clean keywords from search string (utterance)
        if not self.voc_match(phrase, "Video") and "youtube" not in utterance:
            self.requested_options.append("music_only")
        elif self.voc_match(phrase, "Video"):
            pass

        if self.voc_match(phrase, "Repeat") and self.voc_match(phrase, "Mix"):
            self.requested_options.append("playlist_repeat")
        elif self.voc_match(phrase, "Repeat"):
            self.requested_options.append("repeat")
        elif self.voc_match(phrase, "Mix"):
            self.requested_options.append("playlist")
        LOG.info(self.requested_options)
        if utterance.split()[0] in ("a", "some"):
            utterance = " ".join(utterance.split()[1:])

        link = None
        results = None
        # This is a specified URL
        for word in message.context.get("cc_data", {}).get("raw_utterance", utterance).split():
            if word.startswith("https://"):
                link = word
                results = [link]
                break
        # Search YouTube for this request
        if not link:
            LOG.debug(f"search: {utterance}")
            results = self._search_youtube(utterance)
            LOG.debug(results)
            if not results:
                LOG.warning(f"Search returned no results! results={results}")
                return None
            if len(results.get("videos")) > 0:
                link = embed_url(results.get("videos")[0].get("url"))
            else:
                LOG.warning(f"Search returned no video results! results={results}")
                return None
        LOG.info(f"Got video: {link}")

        if "news" in phrase and link:
            conf = CPSMatchLevel.GENERIC
        elif link:
            conf = CPSMatchLevel.TITLE
        else:
            conf = False
        return phrase, conf, {"results": results, "link": link, "skill_gui": True}

    def CPS_start(self, phrase, data, message=None):
        link = data["link"]
        results = data["results"]
        LOG.debug(f"AVMusic selected to play {link}")
        if not link:
            LOG.error("No Link!!")
            LOG.debug(results)
            # self.speak("No Link!")
            self.speak_dialog("TryAgain")
        else:
            # Mobile request
            if request_from_mobile(message):
                self._start_mobile_playback(link, message)
            # Server request
            elif self.server:
                # self.speak(str(self.search(utterance + "playlist")))
                LOG.debug(f"Link to send: {link}")
                if link.startswith("https://www.youtube.com"):
                    # self.speak(link)

                    # Send link to conversation (for history and other users
                    self.send_with_audio(link, None, message)

                else:
                    LOG.warning(f"Bad Link: {link}")
                    self.speak_dialog('TryAgain')
            # Local request
            else:
                self.enable_intent('playnow_intent')
                self.enable_intent('not_now_intent')
                while not self.request_queue.empty():
                    LOG.warning(f"DM: AVMusic Queue isn't empty!!!")
                    self.request_queue.get()
                LOG.debug(f'add to queue: {results.get("videos", [])[0]}')
                self.request_queue.put(results.get("videos", [])[0].get("url"))
                LOG.debug(self.request_queue.empty())
                self.video_results[self.get_utterance_user(message)] = {"current": 0, "results": results}
                if "http" not in phrase:
                    self.speak('Would you like me to play it now?', True)
                    t = multiprocessing.Process(target=self.check_timeout())  # TODO: Use skill event scheduler DM
                    t.start()
                else:
                    self.handle_play_now_intent(message)

    def _start_mobile_playback(self, link, message):
        """
        Handles a mobile intent match
        :param link: link for video
        :param message: Message associated with request
        """
        # TODO: Add a non-Klat server handler DM
        # Emit to requesting mobile user
        time.sleep(2)
        if link.startswith("https://www.youtube.com") and \
                "https://www.googleadservices.com" not in link:
            # self.speak("Here is your video.")
            self.mobile_skill_intent("link", {"link": link}, message)
            # self.socket_io_emit('link', f"&link={link}",
            #                     message.context["flac_filename"])
        elif link:
            LOG.warning(f"malformed youtube link: {link}")
            vid_id = link.split("&video_id=")[1].split("&")[0]
            fixed_link = f"https://www.youtube.com/embed/{vid_id}"
            LOG.debug(fixed_link)
            self.mobile_skill_intent("link", {"link": link}, message)
            # self.socket_io_emit('link', f"&link={fixed_link}",
            #                     message.context["flac_filename"])
        else:
            LOG.error("null link!")

    @staticmethod
    def _search_youtube(query) -> dict:
        """
        Search Youtube for the passed query and return a list of results
        :param query: Search term
        :return: dict of results or None
        """
        try:
            results = search_youtube(query)
        except IndexError:
            LOG.warning("No Results found!")
            results = None
        except Exception as e:
            LOG.error(e)
            results = None
        return results

    def _check_started(self):
        # DEPRECIATED METHOD
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
                            volume.value_flat = float(self.preference_skill()["volume"])
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

    def handle_play_now_intent(self, message):
        # TODO: Handle playback over
        # self.enable_intent('playback_control_intent')
        self.create_signal("AV_agreed_to_play")
        self.check_for_signal("AV_asked_to_wait")
        self.disable_intent('not_now_intent')
        self.disable_intent('playnow_intent')
        self.create_signal("AV_active")
        self.bus.emit(message.forward("neon.wake_words_state", {"enabled": True}))  # TODO: Move to CPS DM
        # if self.check_for_signal('CORE_skipWakeWord', -1):
        #     NeonHelpers.enable_ww()
        #     self.create_signal("AV_WW")
        LOG.debug(self.request_queue.empty())
        if not self.request_queue.empty():
            results = self.request_queue.get()
        elif self.video_results.get(self.get_utterance_user(message)):
            results = self.video_results[self.get_utterance_user(message)]["results"]
        else:
            results = None
        if results:
            try:
                self.speak_dialog('SayStop', {'ww': self.local_config['listener']['wake_word'].title()})
                # if d_hw == 'pi':
                #     self.process = Popen(["mpv", "--vid=no", self.search(utterance)],
                #                          stdout=DEVNULL, stderr=STDOUT)
                # else:
                LOG.debug(f"DM: {results}")
                # results = self.search(utterance)
                if results:
                    LOG.debug(results)
                    if isinstance(results, str):  # TODO: Depreciated? DM
                        link = results
                    elif isinstance(results, list):  # TODO: Depreciated? DM
                        link = results[0]
                    elif isinstance(results, dict):
                        link = results.get("videos", [])[0].get("url)")
                    else:
                        link = None
                        LOG.error(f"No link in results={results}")
                    if "playlist" in self.requested_options and not self.gui_enabled:
                        # TODO: Gui handle playlists DM
                        LOG.info("playlist requested")
                        if isinstance(results, list):
                            for result in results:
                                if "&list=" in result:
                                    link = playlist_url(result)
                                    break
                        elif isinstance(results, dict):
                            link = results.get("playlists", [])[0].get("url")
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
                        self._start_the_mpv(self.requested_options, link)
                        if self.process:
                            output, error = self.process.communicate()
                            # First Playback Attempt Failed
                            if self.process.returncode != 0 and not self.check_for_signal("AV_stoppedFromPause"):
                                LOG.warning("Failed at request:  %d %s %s" % (self.process.returncode, output, error))
                                # LOG.info("Trying again")
                                # if self.process.pid in self.pid:
                                #     self.pid.remove(self.process.pid)
                                try:
                                    LOG.debug("Second Attempt Start")
                                    self._start_the_mpv(self.requested_options, results[1])
                                    LOG.debug("Second Attempt Done")
                                    output, error = self.process.communicate()
                                    # Second Playback Attempt Failed
                                    if self.process:
                                        if self.process.returncode != 0 and not\
                                                self.check_for_signal("AV_stoppedFromPause"):
                                            LOG.warning("Failed at request:  %d %s %s" % (self.process.returncode,
                                                                                          output, error))
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

    def handle_not_now_intent(self):
        self.create_signal("AV_asked_to_wait")
        self.speak_dialog('ChangeMind')
        self.disable_intent('not_now_intent')

    def _handle_pause(self, message):
        """
        Handle request to pause playback
        :param message: Message associated with request
        """
        if self.check_for_signal("AV_active", -1):  # TODO: Signal isn't necessary? DM
            if self.gui_enabled:
                self.gui["status"] = "pause"
            elif not self.server:
                command = b'{"command": ["set", "pause", "yes"]}\n'
                try:
                    self.socket.send(command)
                    LOG.debug(self.socket.recv(1024))
                except Exception as e:
                    LOG.error(e)
            self.speak_dialog('SayResume', {'ww': self.local_config['listener']['wake_word'].title()},
                              message=message)

    def _handle_resume(self, message):
        """
        Handle request resume playback
        :param message: Message associated with request
        """
        if self.check_for_signal("AV_active", -1):  # TODO: Signal isn't necessary? DM
            if self.gui_enabled:
                self.gui["status"] = "play"
            elif not self.server:
                command = b'{"command": ["set", "pause", "no"]}\n'
                try:
                    self.socket.send(command)
                    LOG.debug(self.socket.recv(1024))
                except Exception as e:
                    LOG.error(e)
            self.speak("Resuming playback", message=message)

    def _handle_next(self, message):
        """
        Handle request to skip forward
        :param message: Message associated with request
        """
        # LOG.debug("got here")
        user = self.get_utterance_user(message)
        if self.gui_enabled:
            if user in self.video_results.keys():
                track_list = self.video_results[user].get("results", {}).get("videos", [])
                playing = self.video_results[user].get("current")
                playing += 1
                LOG.info(f"skipping. new source={track_list[playing]}")

                video = pafy.new(track_list[playing].get("url"))
                playstream = video.streams[0]
                LOG.info(video)
                self.gui["title"] = track_list[playing].get("title")
                # self.gui["title"] = str(video).split(":", 1)[1].strip().split("\n", 1)[0]
                self.gui["videoSource"] = playstream.url
                self.gui["status"] = "play"  # play, stop, pause
                self.video_results[user]["current"] = playing

        elif not self.server and self.check_for_signal("AV_active", -1):
            command = b'{"command": ["playlist_next"]}\n'
            try:
                self.socket.send(command)
                LOG.debug(self.socket.recv(1024))
            except Exception as e:
                LOG.error(e)
        self.speak("Skipping next", message=message)

    def _handle_prev(self, message):
        """
        Handle request to skip back
        :param message: Message associated with request
        """
        user = self.get_utterance_user(message)
        if self.gui_enabled:
            if user in self.video_results.keys():
                track_list = self.video_results[user].get("results", {}).get("videos", [])
                playing = self.video_results[user].get("current")
                playing -= 1
                if playing < 0:
                    playing = 0
                LOG.info(f"skipping. new source={track_list[playing]}")

                video = pafy.new(track_list[playing].get("url"))
                playstream = video.streams[0]
                LOG.info(video)
                self.gui["title"] = track_list[playing].get("title")
                # self.gui["title"] = str(video).split(":", 1)[1].strip().split("\n", 1)[0]
                self.gui["videoSource"] = playstream.url
                self.gui["status"] = "play"  # play, stop, pause
                self.video_results[user]["current"] = playing

        elif not self.server and self.check_for_signal("AV_active", -1):
            if self.gui_enabled:
                pass
            elif not self.server:
                command = b'{"command": ["playlist_prev"]}\n'
                try:
                    self.socket.send(command)
                    LOG.debug(self.socket.recv(1024))
                except Exception as e:
                    LOG.error(e)
        self.speak("Skipping back", message=message)

    def _start_the_mpv(self, options, vid_link, retry=False):
        """
        DEPRECIATED use CommonPlay for playback.
        :param options:
        :param vid_link:
        :param retry:
        :return:
        """
        LOG.info(vid_link)
        param_options = ["mpv", "--force-window", "--volume=100", "--audio-client-name=AVmusic",
                         "--input-ipc-server=" + self.sock_path]
        if self.devType:
            options.append("custom")

        if not retry:
            options_final = [self._options_mpv(x) for x in options if self._options_mpv(x) is not None]
        else:
            options_final = []
        param_options.extend(options_final)
        LOG.info(param_options)
        param_options.append(vid_link)
        LOG.info(param_options)
        try:
            self.process = Popen(param_options, stdout=PIPE, stdin=PIPE, stderr=PIPE)
            self._check_started()
            # self.pid.append(self.process.pid)
        except Exception as e:
            LOG.info(e)
        # LOG.info(self.pid)

    def _options_mpv(self, x):
        """
        DEPRECIATED. Use CommonPlay for playback.
        :param x:
        :return:
        """
        return {
            'music_only': "--vid=no",
            'repeat': '--loop',
            'playlist_repeat': '--loop-playlist',
            'custom': "--profile=" + self.devType if self.devType else None
            # 'news': str(self.npr_link)
        }.get(x, "")

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
                self.bus.emit(Message("neon.wake_words_state", {"enabled": False}))  # TODO: Move to CPS DM
                # time.sleep(0.5)
                # NeonHelpers.disable_ww()

            self.clear_signals('AV_')

            # Ensure queue is empty before next request
            while not self.request_queue.empty():
                self.request_queue.get()


def create_skill():
    return AVmusicSkill()
