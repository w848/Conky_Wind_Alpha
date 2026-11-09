# Conky Windows

A desktop system monitor for Windows 11, in the spirit of [Conky](https://github.com/brndnmtthws/conky). It draws a transparent panel over the desktop with CPU, memory, disk, network, and process stats.

This is an independent project. It is not Conky itself, and it is not affiliated with the Conky authors.

## Run it

Double-click `RunConkyWin.bat`. The first launch creates a virtual environment and installs the two Python packages it needs.

Or, from this folder:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
pushd ..
Conky_Wind_Alpha\.venv\Scripts\python.exe -m Conky_Wind_Alpha --config Conky_Wind_Alpha\conkyrc
popd
```

The panel starts at the top-right of the screen and stays above other windows. Drag it to move it. Right-click it, or its tray icon, to reload, edit, let other windows cover it, paint it on the wallpaper, or quit.

`conkyrc` is the layout. Save the file and the panel reloads. A Lua-style `conky.config` / `conky.text` file works too, for the common settings and variables.

## Useful variables

Text variables follow Conky: `${cpu}`, `${mem}`, `${memperc}`, `${swap}`, `${fs_used /}`, `${downspeed}`, `${upspeed}`, `${uptime}`, `${time %H:%M}`, `${top name 1}`, `${battery}`, `${nodename}`, `${exec command}`.

Bars and graphs: `${cpubar}`, `${cpugraph}`, `${membar}`, `${fs_bar /}`, `${downspeedgraph}`.

Colors and layout: `${color}`, `${color1}`, `${hr 1}`, `${alignr}`, `${voffset 4}`, `${font Segoe UI:size=16}`.

`/` means the Windows system drive. `C:` and `D:` select a drive.

## Window modes

- `normal` sits on the desktop and lets other windows cover it
- `desktop` draws on the wallpaper, behind the icons
- `dock` stays above other windows

Turn on `click_through yes` if the panel should ignore the mouse. The tray icon still opens the menu.
