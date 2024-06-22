import cv2
import numpy as np
from djitellopy import tello
import time
from datetime import datetime
import tkinter as tk
import PIL
from ctypes import windll
from PIL import Image, ImageTk
import threading

try:
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass


class Notification(tk.Frame):
    def __init__(self, master, width, height, bg, image, text, close_img, img_pad, text_pad, font, y_pos):
        super().__init__(master, bg=bg, width=width, height=height)
        self.pack_propagate(0)

        self.y_pos = y_pos

        self.master = master
        self.width = width

        right_offset = 8

        self.cur_x = self.master.winfo_width()
        self.x = self.cur_x - (self.width + right_offset)

        img_label = tk.Label(self, image=image, bg=bg)
        img_label.image = image
        img_label.pack(side="left", padx=img_pad[0])

        message = tk.Label(self, text=text, font=font, bg=bg, fg="black")
        message.pack(side="left", padx=text_pad[0])

        close_btn = tk.Button(self, image=close_img, bg=bg, relief="flat", command=self.hide_animation, cursor="hand2")
        close_btn.image = close_img
        close_btn.pack(side="right", padx=5)


        self.place(x=self.cur_x, y=y_pos)

    def show_animation(self):
        if self.cur_x > self.x:
            self.cur_x -= 1
            self.place(x=self.cur_x, y=self.y_pos)

            self.after(1, self.show_animation)

    def hide_animation(self):
        if self.cur_x < self.master.winfo_width():
            self.cur_x += 1
            self.place(x=self.cur_x, y=self.y_pos)

            self.after(1, self.hide_animation)


# Create the main window
root = tk.Tk()
root.title("Face tracking application")
root.geometry("500x300")
root.resizable(False, False)
root.configure(bg="black")


# Change the icon of the window
root.iconbitmap("drone.ico")
root.update()

def on_closing():
    global running
    try:
        running = False
        root.destroy()
        me.land()

    except:
        pass


root.protocol("WM_DELETE_WINDOW", on_closing)

#MP4 format for videos
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out = cv2.VideoWriter(f'{timestamp}_tello_recording.mp4', fourcc, 30.0, (960, 720))

keepRecording = True
running = True
connected = False
lock1 = False
lock2 = True
lock3 = False
lock4 = True

warningIm = Image.open("warning.png")
warningIm = warningIm.resize((25, 25), PIL.Image.Resampling.LANCZOS)
warningIm = ImageTk.PhotoImage(warningIm)

okIm = Image.open("greenTick.png")
okIm = okIm.resize((25, 25), PIL.Image.Resampling.LANCZOS)
okIm = ImageTk.PhotoImage(okIm)

cim = Image.open("close.png")
cim = cim.resize((10, 10), PIL.Image.Resampling.LANCZOS)
cim = ImageTk.PhotoImage(cim)

loading = Image.open("loading.png")
loading = loading.resize((10, 10), PIL.Image.Resampling.LANCZOS)
loading = ImageTk.PhotoImage(loading)

img_pad = (5, 0)
text_pad = (5, 0)

low_charge_warning = Notification(root, 270, 55, "white", warningIm, "Charge your drone!", cim, img_pad, text_pad, "cambria 11", 8)
drone_online = Notification(root, 210, 55, "white", okIm, "Drone online!", cim, img_pad, text_pad, "cambria 11", 8)
drone_not_online = Notification(root, 270, 55, "white", warningIm, "Connect your drone!", cim, img_pad, text_pad, "cambria 11", 8)
drone_not_online2 = Notification(root, 280, 55, "white", warningIm, "Drone is not online!", cim, img_pad, text_pad, "cambria 11", 8)
drone_rec_start = Notification(root, 280, 55, "white", okIm, "Recording started!", cim, img_pad, text_pad, "cambria 11", 8)
drone_rec_stop = Notification(root, 280, 55, "white", warningIm, "Recording stopped!", cim, img_pad, text_pad, "cambria 11", 8)
connection_wait = Notification(root, 280, 55, "white", loading, "Connecting...", cim, img_pad, text_pad, "cambria 11", 8)
#drone
me = tello.Tello()


def takeoff_click_thread():

    global running
    global connected
    global lock1, lock2
    try:
        connection_wait.show_animation()
        if connected == False:
            me.connect()
            time.sleep(2.2)


    except:
        connection_wait.hide_animation()
        drone_not_online.show_animation()
        lock1 = False

    else:
        lock2 = False
        connected = True
        if me.get_battery() < 15:
            low_charge_warning.show_animation()
        else:
            connection_wait.hide_animation()
            drone_online.show_animation()

            # Getting the drones battery
            print(me.get_battery())
            me.streamon()
            me.takeoff()
            me.send_rc_control(0, 0, 25, 0)
            time.sleep(2.2)
            w, h = 360, 240
            fbRange = [6200, 6800]
            pid = [0.4, 0.4, 0]
            pError = 0

            def findFace(img):

                faceCascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = faceCascade.detectMultiScale(imgGray, 1.2, 8)
                myFaceListC = []
                myFaceListArea = []

                for (x, y, w, h) in faces:
                    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cx = x + w // 2
                    cy = y + h // 2
                    area = w * h
                    cv2.circle(img, (cx, cy), 5, (0, 255, 0), cv2.FILLED)
                    myFaceListC.append([cx, cy])
                    myFaceListArea.append(area)
                if len(myFaceListArea) != 0:
                    i = myFaceListArea.index(max(myFaceListArea))

                    return img, [myFaceListC[i], myFaceListArea[i]]
                else:
                    return img, [[0, 0], 0]

            def trackFace(info, w, pid, pError):
                area = info[1]
                x, y = info[0]
                fb = 0
                error = x - w // 2
                speed = pid[0] * error + pid[1] * (error - pError)
                speed = int(np.clip(speed, -100, 100))
                if area > fbRange[0] and area < fbRange[1]:
                    fb = 0
                elif area > fbRange[1]:
                    fb = -20
                elif area < fbRange[0] and area != 0:
                    fb = 20
                if x == 0:
                    speed = 0
                    error = 0

                me.send_rc_control(0, fb, 0, speed)
                return error

            while running:

                img = me.get_frame_read().frame
                img = cv2.resize(img, (w, h))
                img, info = findFace(img)
                pError = trackFace( info, w, pid, pError)
                cv2.imshow("Tello Video", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    me.land()

                    break


def takeoff_click():
    running = True
    global lock1, lock2
    if lock1 == False:
        lock1 = True
        lock2 = False
        takeoff_thread = threading.Thread(target=takeoff_click_thread)
        takeoff_thread.start()


def land_click():
    global running
    global lock2,lock1
    if lock2 == False:
        lock2 = True
        lock1 = False
        running = False
        me.land()


def rec_thread_click():
    global keepRecording
    global connected
    global lock3
    try:
        if connected == False:

            connection_wait.show_animation()
            me.connect()
    except:
        connection_wait.hide_animation()
        drone_not_online.show_animation()
        lock3 = False

    else:
        connected = True
        drone_rec_start.show_animation()

        me.connect()
        me.streamon()


        while keepRecording:
            frame = me.get_frame_read().frame
            out.write(frame)



#recording start
def on_button3_click():
    global lock3, lock4
    if lock3 == False:
        lock3 = True
        lock4 = False
        rec_thread = threading.Thread(target=rec_thread_click)
        rec_thread.start()


#recording stop
def on_button4_click():
    global lock4, lock3, lock2, lock1
    if lock4 == False:
        lock4 = True
        lock3 = False
        lock2 = True
        lock1 = False
        drone_rec_start.hide_animation()
        drone_rec_stop.show_animation()
        global keepRecording
        keepRecording = False
        out.release()
        me.streamoff()
        me.end()

button1 = tk.Button(root, text="takeoff", command=takeoff_click, font=('Arial', 9), bg='lightblue')
button1.grid(row=3, column=1, pady=20, padx=10, ipadx=10)

button2 = tk.Button(root, text="land", command=land_click, font=('Arial', 9), bg='lightblue')
button2.grid(row=4, column=1, pady=20, ipadx=20)

button3 = tk.Button(root, text="start rec", command=on_button3_click, font=('Arial', 9), bg='lightgreen')
button3.grid(row=5, column=1, pady=20, ipadx=5)

button4 = tk.Button(root, text="stop rec", command=on_button4_click, font=('Arial', 9), bg='red')
button4.grid(row=6, column=1, pady=20, ipadx=5)


# Start the main event loop
root.mainloop()

