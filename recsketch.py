#!/usr/bin/env python

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import cairo
import os,datetime,re,subprocess,sys
import numpy

width = 1920
height = 6000
display_height = 1080
scroll = 0
surface = None
cr = None
last_x = 0
last_y = 0
drawing_mode = 'idle' #drawing modes: 'idle', 'drawing' (after mouse-down), 'erase' (after 'e' key pressed, but before mouse-down), 'erasing' (after mouse-down), 'hidecursor'
points = [] #points that make up the erase polygon
pngfile = ''

N_UNDO = 10
undo_pos = 0
n_redos = 0
n_undos = 0
undo_surface = []

show_lines = False

line_sep = 50
ex_height = 17

default_pressure = 0.6
last_pressure = 0.1

timestamp = ''
vidpid = ''
audpid = ''

lw = 0.5 #line width

def set_bg():
	cr.set_source_rgb(1,1,1) #white

def my_draw_line(x_i,y_i,x_f,y_f,p): #add some slightly shifted copies of the line for calligraphic effect
	global last_pressure
	cr.set_line_width(5*p) #set the line width based on stylus pressure
	#cr.set_line_join(cairo.LINE_JOIN_ROUND)
	#cr.set_line_cap(cairo.LINE_CAP_ROUND)

	shift = 4
	#shift = 0.8
	cr.set_source_rgba(0,0,0,1)
	cr.move_to(x_i - shift*last_pressure,y_i + shift*last_pressure + scroll)
	cr.line_to(x_f - shift*p,y_f + shift*p + scroll)
	cr.line_to(x_f + shift*p,y_f - shift*p + scroll)
	cr.line_to(x_i + shift*last_pressure,y_i - shift*last_pressure + scroll)
	cr.close_path()
	cr.fill()
	last_pressure = p

	#cr.set_line_width(0.5)
	cr.move_to(x_i,y_i + scroll)
	cr.line_to(x_f,y_f + scroll)
	cr.stroke()

def queue_draw_polygon(area): #find rectangle that fits around the polygon and queue it
	global points
	if len(points) > 0:
		min_x = points[0][0]
		max_x = points[0][0]
		min_y = points[0][1]
		max_y = points[0][1]
		for point in points[1:]:
			if point[0] < min_x:
				min_x = point[0]
			if point[0] > max_x:
				max_x = point[0]
			if point[1] < min_y:
				min_y = point[1]
			if point[1] > max_y:
				max_y = point[1]
		if min_x < 0:
			min_x = 0
		if min_y < 0:
			min_y = 0
		area.queue_draw_area(int(min_x)-1, int(min_y)-1, int(max_x)+1, int(max_y)+1)

def loadpng(filename):
	global pngfile
	pngfile = filename
	clear()
	try:
		img = cairo.ImageSurface.create_from_png(filename)
		cr.set_source_surface(img, (width - img.get_width())/2, (display_height - img.get_height())/2) #centre it
		#cr.set_source_surface(img, width - img.get_width(), 0)
		cr.paint()
		area.queue_draw_area(0,0,width,height)
	except IOError:
		print("Error reading png: " + filename)
	save()

def move(area, event):
	global cr, last_x, last_y, points
	if drawing_mode == 'drawing':
		#http://nullege.com/codes/show/src@d@o@dopey-HEAD@gui@freehand.py/384/gtk.gdk.AXIS_PRESSURE
		#event.device.set_axis_use(2, Gdk.AXIS_PRESSURE)
		#print event.device.get_n_axes()
		#print event.device.get_name()
		pressure = event.get_axis(3)
		if pressure is None:
			pressure = default_pressure

		my_draw_line(last_x,last_y,event.x,event.y,pressure)
		area.queue_draw_area(int(min(last_x,event.x))-5, int(min(last_y,event.y))-5, int(max(last_x,event.x))+5, int(max(last_y,event.y))+5)
		last_x = event.x
		last_y = event.y
	elif drawing_mode == 'erasing':
		queue_draw_polygon(area)
		last_x = event.x
		last_y = event.y
		points.append((int(event.x),int(event.y)))

def expose(area, event):
	global surface
	tmp_cr = area.get_window().cairo_create()
	tmp_cr.set_source_surface(surface,0,-scroll)
	tmp_cr.paint()

	tmp_cr.set_line_width(1)

	#show light blue horizontal lines as handwriting guides. can edit these out of the video afterwards with ffmpeg's chromakey filter
	if show_lines:
		start = -scroll % line_sep
		#tmp_cr.set_source_rgba(0,1,0,0.25) #chromakey=dfffdf:0.05
		tmp_cr.set_source_rgba(0,1,1,0.25) #chromakey=dfffff:0.05
		for i in range(start,1080,line_sep):
			tmp_cr.move_to(0,i)
			tmp_cr.line_to(width,i)
			tmp_cr.stroke()
			tmp_cr.move_to(0,i+ex_height)
			tmp_cr.line_to(width,i+ex_height)
			tmp_cr.stroke()

	tmp_cr.set_source_rgb(0,0,0)
	tmp_cr.set_dash([5.0,5.0])
	if drawing_mode == 'erasing' and len(points) > 0:
		tmp_cr.move_to(points[0][0],points[0][1])
		for point in points[1:]:
			tmp_cr.line_to(point[0],point[1])
		tmp_cr.line_to(points[0][0],points[0][1])
		tmp_cr.stroke()
	#if timestamp != '': #if making screen recording, mark bottom of recording rectangle
	#	tmp_cr.move_to(0,723)
	#	tmp_cr.line_to(width,723)
	#	tmp_cr.stroke()
	if timestamp == '': #now that recording is full screen, show a square when NOT recording
		tmp_cr.rectangle(10,10,10,10)
		tmp_cr.fill()

	if drawing_mode == 'erase' or drawing_mode == 'erasing':
		area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.CROSS))
	elif drawing_mode == 'hidecursor':
		area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.BLANK_CURSOR))
	else:
		area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.PENCIL))
	return False

def clear():
	set_bg()
	cr.rectangle(0,0,width,height)
	cr.fill()
	save()

def draw_polygon():
	global cr
	cr.move_to(points[0][0],points[0][1] + scroll)
	for point in points[1:]:
		cr.line_to(point[0],point[1] + scroll)
	cr.close_path()
	cr.fill()

def save(): #save the current surface for future undo
	global undo_pos, n_undos, n_redos
	undo_pos = (undo_pos + 1) % N_UNDO
	n_undos = min(N_UNDO,n_undos + 1)
	n_redos = 0
	undo_cr = cairo.Context(undo_surface[undo_pos])
	undo_cr.set_source_surface(surface,0,0)
	undo_cr.paint()

def paste(x,y):
	filename = os.popen('ls -c ~/*.png 2>/dev/null | head -n 1').read().strip() #last png created in home
	#print filename
	img = cairo.ImageSurface.create_from_png(filename)
	cr.set_source_surface(img, x,y)
	cr.paint()
	area.queue_draw_area(0,0,width,height)

def press(area, event): #mouse-down
	global last_x, last_y, drawing_mode, points, scroll

	if (event.button == 1): #left-click
		if drawing_mode == 'erase':
			last_x = event.x
			last_y = event.y
			drawing_mode = 'erasing'
			points = []
		else:
			global last_pressure
			last_pressure = 0.1
			cr.set_source_rgb(0,0,0)
			drawing_mode = 'drawing'
			last_x = event.x
			last_y = event.y

	elif (event.button == 2): #middle-click = paste
		paste(event.x, event.y + scroll)
	elif (event.button == 3): #right-click = erase
		last_x = event.x
		last_y = event.y
		drawing_mode = 'erasing'
		points = []
	#xinput set-button-map "Logitech USB Optical Mouse" 8 9 10 11 12
	elif (event.button == 8):
		#if timestamp == '':
		#	record()
		#else:
		if timestamp != '':
			stop_recording()
	else:
		print event.button

def release(area, event): #mouse-up
	global drawing_mode,points,cr
	if drawing_mode == 'erasing':
		set_bg()
		draw_polygon()
		queue_draw_polygon(area)
		area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.PENCIL))
	drawing_mode = 'idle'
	save()

def record():
	global timestamp,vidpid,audpid
	timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
	if show_lines:
		timestamp = timestamp + '-lines'
	area.queue_draw_area(0,0,width,height)

	###Now on yoga 260 we just record the entire screen, so finding the window geometry is no longer needed
	#info = os.popen('xwininfo -name RecSketch').read()
	#mo = re.search('geometry\s*(\d+)x(\d+)',info)
	#geom = '1920x1080'
	#corner = '0,0'
	#if int(mo.group(1)) == 1280: #use 720p if window is fullscreen
	#	geom = '1280x720'
	#	mo = re.search('Corners:\s*\+(\d+)\+(\d+)',info)
	#	corner = '0,' + str(int(mo.group(2)) + 1) #add 1 to cut off border
	#else:
	#	geom = mo.group(1) + 'x' + str(2*(int(mo.group(2))/2))
	#	mo = re.search('Corners:\s*\+(\d+)\+(\d+)',info)
	#	#corner = str(int(mo.group(1)) + 1) + ',' + str(int(mo.group(2)) + 1) #add 1 to cut off border
	#	corner = mo.group(1) + ',' + str(int(mo.group(2)) + 1) #add 1 to cut off border

	####Originally I had ffmpeg record the audio and video in one process, as below:
	#os.system('~/bin/FFmpeg/ffmpeg -y -video_size ' + geom + ' -framerate 30 -f x11grab -i :0.0+' + corner + ' -f pulse -i default -vcodec libx264 -preset fast -pix_fmt yuv420p -threads 0 -draw_mouse 1 ~/videos/maths/rec-' + timestamp + '.mkv &')
	#os.system('~/bin/FFmpeg/ffmpeg -y -video_size ' + geom + ' -framerate 30 -f x11grab -i :0.0+' + corner + ' -f pulse -i default -vcodec libx264 -crf 0 -preset ultrafast -pix_fmt yuv420p ~/videos/maths/rec-' + timestamp + '.mkv &')
	####but that leads to 'ALSA buffer xrun' errors and gaps in the audio, lack of sync. So then I recorded the audio and video in separate threads and mux it afterwards
	####that problem no longer exists on yoga 260 (faster processor) but now the audio stops a couple seconds before the video if they're stopped at the same time.
	####why? ffmpeg is 3.4.2-2 on yoga 260 (4.0 for the compiled one?), 2.8.14 on x200 tablet. was only 0.1-0.2 seconds difference before
	####now I kill the audio process after the video process (have to store the PIDs). Use "-shortest" flag when muxing so it cuts off the excess audio

	####these bash scripts output the ffmpeg pid. All ffmpeg output and errors go to ~/videos/maths/vidlog and audlog
	#vidpid = os.popen('$HOME/bin/recvid.sh ' + timestamp).read().strip()
	#audpid = os.popen('$HOME/bin/recaud.sh ' + timestamp).read().strip()

	####the audio ending first problem is gone now? ffmpeg version is 3.4.4-0ubuntu0.18.04.1. I guess they fixed it
	os.system('ffmpeg -y -video_size 1920x1080 -framerate 30 -f x11grab -i :0.0 -f alsa -i pulse -vcodec libx264 -preset ultrafast -pix_fmt yuv420p ~/videos/maths/rec-' + timestamp + '.mkv &')

	#os.system('ffmpeg -y -video_size ' + geom + ' -framerate 30 -f x11grab -i :0.0+' + corner + ' -vcodec libx264 -crf 0 -preset ultrafast -pix_fmt yuv420p $HOME/videos/maths/rec-' + timestamp + '_v.mkv &')
	#os.system('ffmpeg -y -f pulse -i default $HOME/videos/maths/rec-' + timestamp + '_a.mkv &')

	#os.system('ffmpeg -y -f alsa -i hw:0 $HOME/videos/maths/rec-' + timestamp + '_a.mkv &')
	#os.system('ffmpeg -y -f alsa -i hw:0 -ac 1 $HOME/videos/maths/rec-' + timestamp + '_a.mkv &')
def stop_recording():
	global timestamp
	#os.system('killall ffmpeg')

	####run this in background then delete the original files if successful
	#mux_cmd = 'ffmpeg -y -i $HOME/videos/maths/rec-' + timestamp + '_a.mkv -i $HOME/videos/maths/rec-' + timestamp + '_v.mkv -codec copy -shortest $HOME/videos/maths/rec-' + timestamp + '.mkv'
	#print '\n**************' + mux_cmd
	os.system('killall ffmpeg') #probably shouldn't do this. better to record the PID and just kill that process
	#os.system('(sleep 3 && killall ffmpeg) &')
	#os.system('(kill ' + vidpid + '&& sleep 3 && kill ' + audpid + '&& sleep 1 && ' + mux_cmd + ' > $HOME/videos/maths/muxlog 2>&1 && rm $HOME/videos/maths/rec-' + timestamp + '_[av].mkv) &')

	timestamp = ''
	area.queue_draw_area(0,0,width,height)

def key(area, event):
	#print event.keyval
	#print Gdk.keyval_name(event.keyval)
	global scroll,drawing_mode,timestamp,show_lines, undo_pos, n_redos, n_undos
	keyname = Gdk.keyval_name(event.keyval)
	if keyname == 'c': #clear screen
		clear()
		area.queue_draw_area(0,0,width,height)
	elif keyname == 'e': #erase
		if drawing_mode == 'erase': #if already in erase mode, go to normal mode
			area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.PENCIL))
			drawing_mode = 'idle'
		elif drawing_mode == 'idle' or drawing_mode == 'hidecursor':
			area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.CROSS))
			drawing_mode = 'erase'
	elif keyname == 'l': #show/hide blue lines
		show_lines = not show_lines
		area.queue_draw_area(0,0,width,height)
	elif keyname == 'f': #make the camera window fullscreen
		os.system("~/bin/resize_guvcview")
	elif keyname == 'h': #hide cursor
		if drawing_mode == 'hidecursor':
			area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.PENCIL))
			drawing_mode = 'idle'
		else:
			area.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.BLANK_CURSOR))
			drawing_mode = 'hidecursor'
	elif keyname == 'p': #paste png into top left corner
		paste(0,0)
		save()
	elif keyname.lower() == 'y': #yank (save current image as png in home directory)
		#find last line with anything drawn on it
		data = numpy.ndarray(shape=(height, width), dtype=numpy.uint32, buffer=surface.get_data())
		for i in range(0,height,5): #i is number of lines above bottom, we only examine every 5th line because it takes too long otherwise
			for j in range(0,width,5):
				if data[height - 1 - i][j] < 4294967295: #not white
					break
			if j < width - 5:
				break

		img = cairo.ImageSurface(cairo.FORMAT_ARGB32,width,height - i+20)
		img_cr = cairo.Context(img)
		img_cr.set_source_surface(surface, 0, 0)
		img_cr.paint()
		if keyname == 'Y' and len(sys.argv) > 1: #overwrite the initial png
			fn = sys.argv[1]
		else:
			fn = os.path.expanduser("~/maths " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ".png")
		img.write_to_png(fn)
	elif keyname == 'z': #undo
		if n_undos > 0:
			undo_pos = (undo_pos-1) % N_UNDO
			n_redos += 1
			n_undos -= 1
			cr.set_source_surface(undo_surface[undo_pos],0,0)
			cr.paint()
			area.queue_draw_area(0,0,width,height)
	elif keyname == 'v': #redo
		if n_redos > 0:
			undo_pos = (undo_pos+1) % N_UNDO
			n_redos -= 1
			n_undos += 1
			cr.set_source_surface(undo_surface[undo_pos],0,0)
			cr.paint()
			area.queue_draw_area(0,0,width,height)
	elif keyname == 'Escape': #cancel record
		if timestamp != '':
			os.system('killall ffmpeg')
			os.system('rm $HOME/videos/maths/rec-' + timestamp + '.mkv')
			#os.system('rm $HOME/videos/maths/rec-' + timestamp + '_[av].mkv')
			timestamp = ''
			area.queue_draw_area(0,0,width,height)
	elif keyname == 'r': #record
		#print timestamp
		if timestamp == '':
			record()
		else:
			stop_recording()
	elif keyname == 's': #s: stop
		stop_recording()
	elif keyname == 'Left': #Open previous png (by modification time)
		pics = os.popen('ls -c -w 1 ~/*.png').read().strip().split('\n')
		try:
			n = pics.index(pngfile)
		except ValueError:
			n = -1
		loadpng(pics[(n+1)%len(pics)])
	elif keyname == 'Right': #Open next png (by modification time)
		pics = os.popen('ls -c -w 1 ~/*.png').read().strip().split('\n')
		try:
			n = pics.index(pngfile)
		except ValueError:
			n = 0
		loadpng(pics[n-1])

def myscroll(area, event):
	global scroll
	if event.direction == Gdk.ScrollDirection.UP and scroll > 10:
		scroll -= 10
		area.queue_draw_area(0,0,width,height)
	elif event.direction == Gdk.ScrollDirection.DOWN:
		scroll += 10
		area.queue_draw_area(0,0,width,height)

def quit(widget):
	Gtk.main_quit()

window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
window.set_title("RecSketch")
window.connect("destroy", quit)

area = Gtk.DrawingArea()
area.connect("motion_notify_event", move)
area.connect("button_press_event", press)
area.connect("button_release_event", release)
area.connect("key_press_event", key)
area.connect("scroll_event", myscroll)
#area.connect('configure-event',conf)

area.set_events(Gdk.EventMask.EXPOSURE_MASK
   			#| Gdk.EventMask.LEAVE_NOTIFY_MASK
   			| Gdk.EventMask.KEY_PRESS_MASK
   			| Gdk.EventMask.BUTTON_PRESS_MASK
   			| Gdk.EventMask.BUTTON_RELEASE_MASK
   			| Gdk.EventMask.POINTER_MOTION_MASK
   			| Gdk.EventMask.SCROLL_MASK
   			| Gdk.EventMask.POINTER_MOTION_HINT_MASK)

area.set_size_request(1920, 1080) 
#add two for border
#area.set_size_request(1922, 722) #720p

window.add(area)
area.connect("draw", expose)

surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,width,height)
for i in range(0,N_UNDO):
	undo_surface.append(cairo.ImageSurface(cairo.FORMAT_ARGB32,width,height))
cr = cairo.Context(surface)
cr.set_line_width(lw)
clear()

if len(sys.argv) > 1:
	pngfile = sys.argv[1]
	img = cairo.ImageSurface.create_from_png(pngfile)
	cr.set_source_surface(img, 0,0)
	cr.paint()

area.show()
window.show()

area.set_can_focus(True)
area.grab_focus()

Gtk.main()
