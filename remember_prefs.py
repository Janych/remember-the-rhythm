from gi.repository import PeasGtk
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gio
import rb


GSETTINGS_KEY = "org.gnome.rhythmbox.plugins.remember-the-rhythm"
KEY_STARTUP_STATE = 'startup-state'

class RememberPreferences(GObject.Object, PeasGtk.Configurable):
    """
    Preferences for the Plugins. It holds the settings for
    the plugin and also is the responsible of creating the preferences dialog.
    """
    __gtype_name__ = 'RememberPreferences'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        """
        Initialises the preferences, getting an instance of the settings saved
        by Gio.
        """
        GObject.Object.__init__(self)
        self.settings = Gio.Settings.new(GSETTINGS_KEY)
        self._first_run = True

    def do_create_configure_widget(self):
        """
        Creates the plugin's preferences dialog
        """
        print("DEBUG - create_display_contents")
        # create the ui
        builder = Gtk.Builder()
        builder.add_from_file(rb.find_plugin_file(self,
                                                  'ui/remember_preferences.ui'))
        builder.connect_signals(self)

        # bind the toggles to the settings
        self._playpause_rb = builder.get_object('play_pause_radiobutton')
        self._play_rb = builder.get_object('play_radiobutton')
        self._pause_rb = builder.get_object('pause_radiobutton')
        self._source_rb = builder.get_object('select_source_radiobutton')
        self._playlist_rb = builder.get_object('select_playlist_radiobutton')

        startup_state = self.settings[KEY_STARTUP_STATE]

        if startup_state == 1:
            self._playpause_rb.set_active(True)
        elif startup_state == 2:
            self._pause_rb.set_active(True)
        elif startup_state == 3:
            self._play_rb.set_active(True)
        elif startup_state == 4:
            self._source_rb.set_active(True)
        else:
            self._playlist_rb.set_active(True)

        self._first_run = False

        return builder.get_object('remember_box')

    def on_startup_toggled(self, toggle_button):
        if self._first_run:
            return

        if toggle_button == self._playlist_rb:
            startup_state = 5
        elif toggle_button == self._source_rb:
            startup_state = 4
        elif toggle_button == self._play_rb:
            startup_state = 3
        elif toggle_button == self._pause_rb:
            startup_state = 2
        else:
            startup_state = 1

        self.settings[KEY_STARTUP_STATE] = startup_state
