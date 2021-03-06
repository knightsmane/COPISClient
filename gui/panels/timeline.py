#!/usr/bin/env python3

import wx
from utils import set_dialog


"""
TODO: Improve timeline panel
"""
class TimelinePanel(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, style=wx.BORDER_DEFAULT)
        self.init_ui()

    def init_ui(self):
        hboxBottom = wx.BoxSizer()
        vboxCmd = wx.BoxSizer(wx.VERTICAL)
        self.cmd = wx.ListBox(self, style=wx.LB_SINGLE)
        vboxCmd.Add(self.cmd, 1, wx.EXPAND)

        hboxAddCmd = wx.BoxSizer()
        self.cmdWriter = wx.TextCtrl(self)
        hboxAddCmd.Add(self.cmdWriter, 1, wx.EXPAND)
        self.addBtn = wx.Button(self, wx.ID_ANY, label='Add')
        self.addBtn.Bind(wx.EVT_BUTTON, self.on_add_command)
        hboxAddCmd.Add(self.addBtn)
        vboxCmd.Add(hboxAddCmd, 0.5, wx.EXPAND)
        hboxBottom.Add(vboxCmd, 2, wx.EXPAND)

        vboxBtns = wx.BoxSizer(wx.VERTICAL)
        self.up_btn = wx.Button(self, wx.ID_ANY, label='Up')
        self.up_btn.direction = 'up'
        self.up_btn.Bind(wx.EVT_BUTTON, self.on_move_command)
        vboxBtns.Add(self.up_btn)
        self.down_btn = wx.Button(self, wx.ID_ANY, label='Down')
        self.down_btn.direction = 'down'
        self.down_btn.Bind(wx.EVT_BUTTON, self.on_move_command)
        vboxBtns.Add(self.down_btn)
        self.replace_btn = wx.Button(self, wx.ID_ANY, label='Replace')
        self.replace_btn.Bind(wx.EVT_BUTTON, self.on_replace_command)
        vboxBtns.Add(self.replace_btn)
        self.delete_btn = wx.Button(self, wx.ID_ANY, label='Delete')
        self.delete_btn.size = 'single'
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_command)
        vboxBtns.Add(self.delete_btn)
        self.delall_button = wx.Button(self, wx.ID_ANY, label='Delete All')
        self.delall_button.size = 'all'
        self.delall_button.Bind(wx.EVT_BUTTON, self.on_delete_command)
        vboxBtns.Add(self.delall_button)
        self.savetofile_btn = wx.Button(self, wx.ID_ANY, label='Save To File')
        vboxBtns.Add(self.savetofile_btn)
        self.sendall_btn = wx.Button(self, wx.ID_ANY, label='Send All')
        vboxBtns.Add(self.sendall_btn)
        self.sendsel_button = wx.Button(self, wx.ID_ANY, label='Send Sel')
        vboxBtns.Add(self.sendsel_button)
        hboxBottom.Add(vboxBtns)

        self.SetSizer(hboxBottom)
        self.Layout()

    def on_add_command(self, event):
        cmd = self.cmdWriter.GetValue()
        if cmd != '':
            self.cmd.Append(cmd)
            self.cmdWriter.SetValue('')

    def on_move_command(self, event):
        selected = self.cmd.GetStringSelection()

        if selected != '':
            direction = event.GetEventObject().direction
            index = self.cmd.GetSelection()
            self.cmd.Delete(index)

            if direction == 'up':
                index -= 1
            else:
                index += 1

            self.cmd.InsertItems([selected], index)

    def on_replace_command(self, event):
        selected = self.cmd.GetSelection()

        if selected != -1:
            replacement = self.cmdWriter.GetValue()

            if replacement != '':
                self.cmd.SetString(selected, replacement)
                self.cmdWriter.SetValue('')
            else:
                set_dialog('Please type command to replace.')
        else:
            set_dialog('Please select the command to replace.')

    def on_delete_command(self, event):
        size = event.GetEventObject().size
        if size == 'single':
            index = self.cmd.GetSelection()
            if index != -1:
                self.cmd.Delete(index)
            else:
                set_dialog('Please select the command to delete.')
        else:
            self.cmd.Clear()
