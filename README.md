# recsketch
Drawing program I use on linux when recording youtube videos. See for example [this video on solving trig equations](https://www.youtube.com/watch?v=-ldZSvglx1A).

## Requirements

Python, cairo bindings for GObject (see https://pygobject.readthedocs.io/en/latest/getting_started.html), ffmpeg if you want to use screen recording.

## Usage

To erase, use the right mouse button, or press 'e' then use the left mouse button (or stylus). This is a lasso-style erase (clear everything within the selection). If your stylus has extra buttons, you can set one of them to right-click.

Press 'c' to clear the screen.

Pressing the left/right arrow keys will cycle through any PNG files in your home directory (ordered by modification time). Press 'p' to paste the last PNG in the top left corner. Middle-click will paste it at the mouse position.

Press 'y' to save the current page as a png file in your home directory.

Press 'l' to toggle visibility of ruled lines across the page.

'z' to undo, 'v' to redo. (Those keys are next to each other on the dvorak keyboard layout that I use. You can easily change them by editing [recsketch.py](https://github.com/jennigorham/recsketch/blob/master/recsketch.py).)

You can scroll up and down with your mouse's scroll-wheel. 

Press 'r' to record (launches ffmpeg to record the screen). Press 's' to stop recording, or Escape to cancel recording (deletes recorded video). Pressing mouse button 8 will also stop recording. A black square will be visible in the top left corner when recording is stopped.
