#!/usr/bin/env python3
"""
Create Windows Shortcut for Meshtastic Simulator
Run this once to create a desktop shortcut
"""
import os
import sys

try:
    import winshell
    from win32com.client import Dispatch
except ImportError:
    print("ERROR: winshell or pywin32 not installed!")
    print("Please install: pip install pywin32 winshell")
    sys.exit(1)

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
bat_file = os.path.join(script_dir, 'run_simulator.bat')
desktop = winshell.desktop()
shortcut_path = os.path.join(desktop, 'Meshtastic Simulator.lnk')

# Create the shortcut
shell = Dispatch('WScript.Shell')
shortcut = shell.CreateShortCut(shortcut_path)
shortcut.TargetPath = bat_file
shortcut.WorkingDirectory = script_dir
shortcut.IconLocation = bat_file
shortcut.Description = "Meshtastic Network Simulator - Physics Accurate"
shortcut.save()

print(f"✅ Shortcut created successfully!")
print(f"📍 Location: {shortcut_path}")
print(f"🎮 You can now double-click the shortcut on your desktop to run the simulator!")
