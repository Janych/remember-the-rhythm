#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import GObject
from gi.repository import Peas
from gi.repository import RB
from gi.repository import Gio
from gi.repository import GLib

from gi.repository.GLib import Variant
from remember_prefs import RememberPreferences
import subprocess

GSETTINGS_KEY = "org.gnome.rhythmbox.plugins.remember-the-rhythm"
KEY_PLAYBACK_TIME = 'playback-time'
KEY_LOCATION = 'last-entry-location'
KEY_PLAYLIST = 'playlist'
KEY_BROWSER_VALUES = 'browser-values'
KEY_PLAY_STATE = 'play-state'
KEY_SOURCE = 'source'
KEY_STARTUP_STATE = 'startup-state'


class RememberTheRhythm(GObject.Object, Peas.Activatable):
    __gtype_name = 'RememberTheRhythm'
    object = GObject.property(type=GObject.Object)

    first_run = False

    def __init__(self):
        GObject.Object.__init__(self)
        self.settings = Gio.Settings.new(GSETTINGS_KEY)
        self.location = self.settings.get_string(KEY_LOCATION)
        self.playlist = self.settings.get_string(KEY_PLAYLIST)
        self.playback_time = self.settings.get_uint(KEY_PLAYBACK_TIME)
        self.browser_values_list = self.settings.get_value(KEY_BROWSER_VALUES)
        self.play_state = self.settings.get_boolean(KEY_PLAY_STATE)
        self.source = None
        self.source_name = self.settings.get_string(KEY_SOURCE)
        self.startup_state = self.settings.get_uint(KEY_STARTUP_STATE)

    def do_activate(self):
        print ("DEBUG-do_activate")
        self.shell = self.object
        self.shell_player = self.shell.props.shell_player
        self.playlist_manager = self.shell.props.playlist_manager
        self.db = self.shell.props.db

        def try_load(*args):
            if len(self.playlist_manager.get_playlists()) == 0:
                GLib.idle_add(self._load_complete)
            else:
                self._load_complete()

        self.shell.props.db.connect('load-complete', try_load)

    def do_deactivate(self):
        self.first_run = True

    def _connect_signals(self):
        self.shell_player.connect('playing-changed', self.playing_changed)
        self.shell_player.connect('playing-source-changed', self.playing_source_changed)
        self.shell_player.connect('elapsed-changed', self.elapsed_changed)

    def _load_complete(self, *args, **kwargs):
        """
        called when load-complete signal is fired - this plays what was remembered
        :param args:
        :param kwargs:
        :return:
        """

        self._scenario = 5

        print("DEBUG - load_complete")
        if not self.location:
            self.first_run = True
            self._connect_signals()
            return

        entry = self.db.entry_lookup_by_location(self.location)
        print (self.location)
        if not entry:
            self.first_run = True
            self._connect_signals()
            return

        if self.startup_state == 5:
            playlists = self.playlist_manager.get_playlists()
            if playlists.__len__():
                last = playlists[len(playlists)-1]
                if (type(playlists[3]) == RB.StaticPlaylistSource):
                    self.source = last
        else:
            if self.playlist:
                playlists = self.playlist_manager.get_playlists()
                for playlist in playlists:
                    if playlist.props.name == self.playlist:
                        self.source = playlist
                        break

        # now switch to the correct source to play the remembered entry
        if not self.source:
            print (self.location)
            self.source = self.shell.guess_source_for_uri(self.location)

        # when dealing with playing we start a thread (so we don't block the UI
        # each stage we wait a bit for stuff to start working
        time = self.playback_time

        def scenarios():

            def init_source():
                print("\x1b[150G init source")
                if self.source:
                    views = self.source.get_property_views()
                    for i, view in enumerate(views):
                        if i < len(self.browser_values_list):
                            value = self.browser_values_list[i]
                            if value:
                                view.set_selection(value)
                    self.shell.props.display_page_tree.select(self.source)

            print ("scenario %d" % self._scenario)

            if self._scenario == 1:
                init_source()
                # If you need to select a playlist or other source and that's it
                if self.startup_state in [4,5]:
                    self._scenario = 5
                    return False
                # always mute the sound - this helps with the pause scenario
                # where we have to start playing first before pausing... but
                # we dont want to here what is playing

                ok,self.volume=self.shell_player.get_volume() # Я добавляю, чтобы звук не мешал
                self.shell_player.set_volume(0)
                self._scenario += 1
                return True

            if self._scenario == 2:
                # play the entry for the source chosen
                print (entry)
                print (self.source)
                self.shell_player.play_entry(entry, self.source)
                #self.shell_player.set_playing_time(time)
                self._scenario += 1
                return True

            if self._scenario == 3:
                # now pause if the preferences options calls for this.
                print (self.play_state)
                print (self.startup_state)
                if (not self.play_state and self.startup_state == 1) or \
                                self.startup_state == 2:
                    print ("pausing")
                    self.shell_player.pause()
                    # note for radio streams rhythmbox doesnt pause - it can only stop
                    # so basically nothing we can do - just let the stream play
                    self._scenario += 1
                    return True
                self._scenario += 1

            if self._scenario == 4:
                # for the playing entry attempt to move to the remembered time
                try:
                    self.shell_player.set_playing_time(time)
                except:
                    # fallthrough ... some streams - radio - cannot seek
                    pass
                self._scenario += 1
                return True

            # unmute and end the thread
            self.shell_player.set_volume(self.volume)
            return False

        self._scenario = 1
        GLib.timeout_add_seconds(1, scenarios)

        self._connect_signals()
        self.first_run = True

    def playing_source_changed(self, player, source, data=None):
        """
        called when user changes what is playing in a different source
        :param player:
        :param source:
        :param data:
        :return:
        """
        print ("DEBUG-playing source changed")
        if self._scenario != 5:
            return

        if source:
            self.source = source
            if self.source in self.playlist_manager.get_playlists():
                self.settings.set_string('playlist', self.source.props.name)
                self.settings.set_string('source', '')
            else:
                self.settings.set_string('playlist', '')
                self.settings.set_string('source', self.source.props.name)
                self.source_name = self.source.props.name

    def playing_changed(self, player, playing, data=None):
        """
        called when user changes what is actually playing
        :param player:
        :param playing:
        :param data:
        :return:
        """

        print("DEBUG-playing_changed")
        if self._scenario != 5:
            return

        entry = self.shell_player.get_playing_entry()

        if entry:
            print ("found entry")
            self.play_state = playing

            self.location = entry.get_string(RB.RhythmDBPropType.LOCATION)
            print (self.location)
        else:
            print ("not found entry")

        GLib.idle_add(self.save_rhythm, 0)


    def elapsed_changed(self, player, entry, data=None):
        """
        called when something is playing - remembers the time within a track
        :param player:
        :param entry:
        :param data:
        :return:
        """
        if not self.first_run:
            return

        if self._scenario < 4:
            try:
                self.shell_player.set_playing_time(self.playback_time)
            except:
                pass

        try:
            if self.playback_time:
                save_time = True
            else:
                save_time = False

            if save_time and self.playback_time == self.shell_player.get_playing_time()[1]:
                save_time = False

            self.playback_time = self.shell_player.get_playing_time()[1]

            GLib.idle_add(self.save_rhythm)

        except:
            pass


    def save_rhythm(self, pb_time=None):
        """
        This actually saves info into gsettings
        :param pb_time:
        :return:
        """
        if self.location:
            pb_time = pb_time is None and self.playback_time or pb_time is None
            self.settings.set_uint(KEY_PLAYBACK_TIME, pb_time)
            self.settings.set_string(KEY_LOCATION, self.location)
            #print ("last location %s" % self.location)
        self.settings.set_boolean(KEY_PLAY_STATE, self.play_state)

        if self.source:
            views = self.source.get_property_views()
            browser_values_list = []
            for view in views:
                browser_values_list.append(view.get_selection())
            self.browser_values_list = Variant('aas', browser_values_list)
            self.settings.set_value(KEY_BROWSER_VALUES, self.browser_values_list)


    def _import(self):
        """
        dummy routine to stop pycharm from optimising out the preferences import
        :return:
        """
        RememberPreferences()
