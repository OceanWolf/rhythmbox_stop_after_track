# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2012 - Srijan Choudhary
# Copyright (C) 2012 - Radu Stoica
# Copyright (C) 2012 - fossfreedom
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


from gi.repository import Gtk, GObject, RB, Peas, Gio
import xml.etree.ElementTree as ET

ui_string = """
<ui>
        <popup name="BrowserSourceViewPopup">
            <placeholder name="PluginPlaceholder">
                <menuitem name="StopAfterTrackPopup" action="StopAfterTrack" label="Stop after this track" />
            </placeholder>
        </popup>
        <popup name="PlaylistViewPopup">
            <placeholder name="PluginPlaceholder">
                <menuitem name="StopAfterTrackPopup" action="StopAfterTrack" label="Stop after this track" />
            </placeholder>
        </popup>
        <popup name="QueuePlaylistViewPopup">
            <placeholder name="PluginPlaceholder">
                <menuitem name="StopAfterTrackPopup" action="StopAfterTrack" label="Stop after this track" />
            </placeholder>
        </popup>

    <menubar name="MenuBar">
        <menu name="ControlMenu" action="Control">
            <menuitem name="StopAfterCurrentTrack" action="StopAfterCurrentTrack"/>
        </menu>
    </menubar>
    <toolbar name="ToolBar">
        <placeholder name="ToolBarPluginPlaceholder">
            <toolitem name="StopAfterCurrentTrack" action="StopAfterCurrentTrack"/>
        </placeholder>
    </toolbar>
</ui>
"""


class Singleton(object):
    _instance = None
    def __new__(class_, *args, **kwargs):
        if not isinstance(class_._instance, class_):
            class_._instance = object.__new__(class_, *args, **kwargs)
            class_._instance._init()
        return class_._instance


class FakeUIManager(Singleton):
    def _init(self):
        self._action_groups = {}
        self._widgets = {}
        self._uids = {}
        self._current_uid = None

    def _get_new_uid(self):
        return len(self._uids)

    def insert_action_group(self, group, pos):
        self._action_groups[group.get_name()] = group

    def remove_action_group(self, group):
        del self._action_groups[group.get_name()]

    def add_ui_from_string(self, ui_str):
        try:
            self._current_uid = self._get_new_uid()
            ret = self._current_uid
            root = ET.fromstring(ui_string)
            for el in root:
                if el.tag == 'menuitem':
                    self.add_menuitem(el)
                elif el.tag == 'popup':
                    self.add_popup(el)
        finally:
            self.current_id = None

        return ret

    def remove_ui(self, ui_id):
        app = Gio.Application.get_default()
        for menu, index in self._uids[ui_id]:
            app.remove_plugin_menu_item(menu, index)

        del self._uids[ui_id]

    def get_widget(self, ref):
        # Very simple for now, too simple, but for this programme it works
        return self._widgets[ref]

    def add_popup(self, el, group_name=None):
        popup_type = el.attrib['name']

        menu_element = el.find('.//menuitem')
        action_name = menu_element.attrib['action']
        item_name = menu_element.attrib['name']

        item = Gio.MenuItem()
        item.set_detailed_action('win.' + action_name)
        item.set_label(menu_element.attrib['label'])
        app = Gio.Application.get_default()

        if popup_type == 'QueuePlaylistViewPopup':
            plugin_type = 'queue-popup'
        elif popup_type == 'BrowserSourceViewPopup':
            plugin_type = 'browser-popup'
        elif popup_type == 'PlaylistViewPopup':
            plugin_type = 'playlist-popup'
        else:
            raise KeyError('unknown type %s' % plugin_type)

        index = plugin_type + action_name
        app.add_plugin_menu_item(plugin_type, index, item)
        self._widgets['/' + popup_type] = item

        uid = self._current_uid
        if uid is not None:
            uid = self._get_new_uid()

        widgets_by_uid = self._uids.setdefault(uid, [])
        widgets_by_uid.append((plugin_type, index))

class StopAfterPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(StopAfterPlugin, self).__init__()

    def do_activate(self):
        print("Activating Plugin")
        self.stop_status = False  # Only used for stop after current song.
        shell = self.object
        self.action_stop_after_current = Gtk.ToggleAction(
                name='StopAfterCurrentTrack',
                label=('Stop After'),
                tooltip=('Stop playback after current song'),
                stock_id=Gtk.STOCK_MEDIA_STOP
                )
        self.activate_id = self.action_stop_after_current.connect('activate', self.toggle_status, shell)
        self.action_group = Gtk.ActionGroup(name='StopAfterPluginActions')
        self.action_group.add_action(self.action_stop_after_current)

        sp = shell.props.shell_player
        self.pec_id = sp.connect('playing-song-changed', self.playing_entry_changed)

        '''action = Gtk.Action(name="StopAfterTrack", label=_("_Stop after this track"),
                            tooltip=_("Stop playing after this track"),
                            stock_id='gnome-mime-text-x-python')'''
        action = Gio.SimpleAction(name="StopAfterTrack")
        action.connect('activate', self.stop_after_current_track, self.object)
        #self.action_group.add_action(action)
        shell.props.window.add_action(action)

        self.action_stop_after_current.set_active(False)
        self.action_stop_after_current.set_sensitive(False)

        #uim = shell.props.ui_manager
        uim = FakeUIManager()
        uim.insert_action_group(self.action_group,0)
        self.ui_id = uim.add_ui_from_string(ui_string)

        browser_source_view = uim.get_widget("/BrowserSourceViewPopup")
        #self.br_cb = browser_source_view.connect('show', self.activate_browser_source_view)
        
        #uim.ensure_update()

        self.previous_song = None
        self.stop_song = None

        print("Plugin Activated")

    def do_deactivate(self):
        print("Deactivating Plugin")
        shell = self.object
        #uim = shell.props.ui_manager
        uim = FakeUIManager()
        
        player = shell.props.shell_player
        browser_source_view = uim.get_widget("/BrowserSourceViewPopup")
        #browser_source_view.disconnect(self.br_cb)
        uim.remove_ui(self.ui_id)
        #uim.ensure_update()

        uim.remove_action_group(self.action_group)
        sp = shell.props.shell_player
        sp.disconnect (self.pec_id)
        self.action_group = None
        self.action_stop_after_current = None

        del self.ui_id
        del self.previous_song
        del self.stop_song
        
        print("Plugin Deactivated")

    def get_all_popups(self):
        # Returns a list with all the widgets we use for the context menu.
        shell = self.object
        manager = shell.props.ui_manager
        return (manager.get_widget("/BrowserSourceViewPopup/PluginPlaceholder/StopAfterTrackPopup"),
                manager.get_widget("/PlaylistViewPopup/PluginPlaceholder/StopAfterTrackPopup"),
                manager.get_widget("/QueuePlaylistViewPopup/PluginPlaceholder/StopAfterTrackPopup")
                )

    def toggle_status(self, action, shell):
        """Used for stop after current song"""
        if action.get_active():
            self.stop_status = True
        else:
            self.stop_status = False
        print(self.stop_status)

    def playing_entry_changed(self, sp, entry):
        print("Playing entry changed")
        print(entry)
        if entry is not None:
            self.action_stop_after_current.set_sensitive(True)
            if self.stop_status:
                self.action_stop_after_current.set_active(False)
                sp.stop()
        else:
            self.action_stop_after_current.set_sensitive(False)

        # Check what song was last played, stop if we should.
        # If not, check what song is playing and store it.
        if (self.previous_song is not None) and (self.previous_song == self.stop_song):
            sp.pause()
       
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
