# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2012 - Srijan Choudhary
# Copyright (C) 2012 - Radu Stoica
# Copyright (C) 2012 - fossfreedom
# Copyright (C) 2024 - OceanWolf
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.


from gi.repository import Gtk, GObject, RB, Peas, Gio, GLib
import xml.etree.ElementTree as ET


class NewToggleAction(Gio.SimpleAction):
    def __init__(self, name):
        super().__init__(name=name, parameter_type=None, state=GLib.Variant.new_boolean(False))

    def set_active(self, state):
        """
        Sets the state of the action

        Parameters
        ----------
        state : boolean
            The new state of the action
        """
        self.change_state(GLib.Variant.new_boolean(state))


class StopAfterPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(StopAfterPlugin, self).__init__()
        self._widgets = []
        self._menu_items = []

    def do_activate(self):
        print("Activating Plugin")
        self.stop_status = False  # Only used for stop after current song.
        shell = self.object

        self.action_stop_after_current = NewToggleAction('StopAfterCurrentTrack')
        self.activate_id = self.action_stop_after_current.connect('change-state', self.toggle_status)

        sp = shell.props.shell_player
        self.pec_id = sp.connect('playing-song-changed', self.playing_entry_changed)

        action = Gio.SimpleAction(name="StopAfterTrack")
        action.connect('activate', self.stop_after_current_track, self.object)
        shell.props.window.add_action(action)

        # Add the tools
        self.add_toolbar_togglebutton()
        self.add_popups()

        #browser_source_view = uim.get_widget("/BrowserSourceViewPopup")
        #self.br_cb = browser_source_view.connect('show', self.activate_browser_source_view)

        self.previous_song = None
        self.stop_song = None

        # init the plugin to the current song
        self.playing_entry_changed(sp, sp.get_playing_entry())

        print("Plugin Activated")

    def do_deactivate(self):
        print("Deactivating Plugin")
        shell = self.object

        #browser_source_view = uim.get_widget("/BrowserSourceViewPopup")
        #browser_source_view.disconnect(self.br_cb)

        app = Gio.Application.get_default()
        for widget in self._widgets:
            widget.destroy()
        del self._widgets[:]

        for menu, index in self._menu_items:
            app.remove_plugin_menu_item(menu, index)
        del self._menu_items[:]

        sp = shell.props.shell_player
        sp.disconnect (self.pec_id)
        self.action_group = None
        self.action_stop_after_current = None

        del self.previous_song
        del self.stop_song

        print("Plugin Deactivated")

    def add_toolbar_togglebutton(self):
        action_name = 'StopAfterCurrentTrack'

        for child in self.object.props.window:
            for child2 in child:
                if 'Gtk.Toolbar' in str(child2):
                    toolbar = child2
        togg_btn_box = list(list(toolbar)[1])[0]

        image = Gtk.Image()
        image.set_from_icon_name('go-last-symbolic', Gtk.IconSize. LARGE_TOOLBAR)
        btn_stop_after_current = Gtk.ToggleButton(image=image, tooltip_text='Stop after current track')
        self._widgets += image, btn_stop_after_current

        btn_stop_after_current.set_detailed_action_name('win.' + action_name)
        btn_stop_after_current.set_sensitive(True)
        btn_stop_after_current.connect('toggled', lambda obj: self.action_stop_after_current.set_active(obj.get_active()))
        btn_stop_after_current.show()
        togg_btn_box.pack_end(btn_stop_after_current, False, False, 0)

    def add_popups(self):
        action_name = 'StopAfterTrack'
        label = 'Stop after this track'

        popup_types = {'BrowserSourceViewPopup': 'browser-popup',
                       'QueuePlaylistViewPopup': 'queue-popup',
                       'PlaylistViewPopup': 'playlist-popup'}

        for popup_type in popup_types:
            plugin_type = popup_types[popup_type]
            item = Gio.MenuItem()
            item.set_detailed_action('win.' + action_name)
            item.set_label(label)
            app = Gio.Application.get_default()

            index = plugin_type + action_name
            app.add_plugin_menu_item(plugin_type, index, item)
            self._menu_items.append([plugin_type, index])

    def get_all_popups(self):
        # Returns a list with all the widgets we use for the context menu.
        shell = self.object
        manager = shell.props.ui_manager
        return (manager.get_widget("/BrowserSourceViewPopup/PluginPlaceholder/StopAfterTrackPopup"),
                manager.get_widget("/PlaylistViewPopup/PluginPlaceholder/StopAfterTrackPopup"),
                manager.get_widget("/QueuePlaylistViewPopup/PluginPlaceholder/StopAfterTrackPopup")
                )

    def toggle_status(self, action, value):
        """Used for stop after current song"""
        print('status toggled')
        if value:
            self.stop_status = True
        else:
            self.stop_status = False
        print(self.stop_status)

    def _set_button_status(self, status):
        self.action_stop_after_current.set_enabled(status)
        self._widgets[1].set_sensitive(status)

    def stop(self, sp):
        self.previous_song = None
        self.action_stop_after_current.set_active(False)
        self._widgets[1].set_active(False)
        sp.stop()
        self._set_button_status(False)

    def playing_entry_changed(self, sp, entry):
        print("Playing entry changed")
        print(entry)
        if entry is not None:
            self.action_stop_after_current.set_enabled(True)
            if self.stop_status:
                self.stop(sp)
            else:
                self._set_button_status(True)
        else:
            self._set_button_status(False)
            self.action_stop_after_current.set_active(False)

        # Check what song was last played, stop if we should.
        # If not, check what song is playing and store it.
        if (self.previous_song is not None) and (self.previous_song == self.stop_song):
            self.stop_song = None  # TODO make this an option
            self.stop(sp)

        if sp.get_playing_entry() is not None:
            self.previous_song = sp.get_playing_entry().get_string(RB.RhythmDBPropType.LOCATION)
            print("Previous song set to {0}".format(self.previous_song))

    def activate_browser_source_view(self, data):
        selected_song = self.get_selected_song()
        for popup in self.get_all_popups():
            if selected_song is not None and self.stop_song == selected_song:
                popup.set_label(_('Do not pause after track'))
            else:
                popup.set_label(_('Pause after track'))

    def get_selected_song(self):
        shell = self.object
        page = shell.props.selected_page
        if not hasattr(page, "get_entry_view"):
            return None
        selected = page.get_entry_view().get_selected_entries()
        if selected != []:
            return selected[0].get_playback_uri()
        return None

    def stop_after_current_track(self, action, param, shell):
        """
        Parameters
        ----------
        action :
            The action that caused this, og Gio.SimpleAction
        param :
            I think we get the param list here, if so we should get none, so ignore it
        shell :
        The shell, why do we pass this in?
        """
        selected_song = self.get_selected_song()
        if self.stop_song is not None and self.stop_song == selected_song:
            print("a")
            self.stop_song = None
        else:
            print("b")
            self.stop_song = selected_song
