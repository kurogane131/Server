import asyncio
import websockets
import RPi.GPIO as GPIO
import time
import functools
import atexit
import os
import subprocess
import picamera
import io
import base64

class VideoFlag:
    def __init__(self):
        self.send_video = False
vf=VideoFlag()

def cleanup_gpio():
    # GPIOピンをクリーンアップ
    GPIO.cleanup()

async def wait_for_wifi(ssid):
    while True:
        connected_ssid = get_current_wifi_ssid()
        if connected_ssid == ssid:
            wait_for_ip_address()
            break
        else:
            await asyncio.sleep(5)
            
def get_current_wifi_ssid():
    try:
        result = subprocess.run(["iwconfig","wlan0"],capture_output=True,text=True)
        output_lines = result.stdout.splitlines()
        for line in output_lines:
            print("at line")
            if "ESSID" in line:
                ssid_start = line.find('"') + 1
                ssid_end = line.rfind('"')
                return line[ssid_start:ssid_end]
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def wait_for_ip_address():
    try:
        while True:
            result = subprocess.run(["ifconfig","wlan0"],capture_output=True,text=True)
            output_lines = result.stdout.splitlines()
            for line in output_lines:
                if "inet" in line:
                    ip_address = line.split()[1]
                    return ip_address
                time.sleep(1)
    except Exception as e:
        print("error:",e)
        
def setup_camera():
    camera = picamera.PiCamera()
    camera.resolution =(480,360)
    camera.vflip = True
    camera.hflip = True
    return camera

async def start_camera_stream(camera, websocket , send_video):
    
    while vf.send_video:
        frame_stream = io.BytesIO()
        camera.capture(frame_stream, format='jpeg',use_video_port=True)
        frame_stream.seek(0)
        send_frame = frame_stream.read()
        await websocket.send(base64.b64encode(send_frame))
        frame_stream.seek(0)
        frame_stream.truncate()
        await asyncio.sleep(0.03)
    

async def echo(websocket, path,pwm1,pwm2, camera):
    send_video = False
    async for message in websocket:      
        command = message.split(" ")
        print(message)
        if command[0] == "exit":
            await websocket.send("Roger")
            await websocket.close()
            if websocket.open:
                print("websocket open")
            else:
                print("websokcet closed")
        elif command[0] == "Live":
            await websocket.send("Lived")
            
        elif command[0] == "ON":
            vf.send_video= True
            asyncio.create_task(start_camera_stream(camera,websocket,vf.send_video))
        elif command[0] == "OFF":
            vf.send_video = False
          #  await start_camera_stream(camera,websocket,send_video)
            
        elif command[0] != "exit":
            if command[3] == "L":
                pwm1.ChangeDutyCycle(int(command[0]))
                if(command[1] == "1"):
                    GPIO.output(5,GPIO.HIGH)
                    GPIO.output(6,GPIO.LOW)
                else:
                    GPIO.output(5,GPIO.LOW)
                    GPIO.output(6,GPIO.HIGH)
            elif command[3] == "R":
                pwm2.ChangeDutyCycle(int(command[0]))
                if(command[1] == "1"):
                    GPIO.output(20,GPIO.HIGH)
                    GPIO.output(21,GPIO.LOW)
                else:
                    GPIO.output(20,GPIO.LOW)
                    GPIO.output(21,GPIO.HIGH)    
            
            
        
def setup_gpio():
    #GPIO set
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(13, GPIO.OUT)#PWM
    GPIO.setup(19, GPIO.OUT)#PWM
    # 利用するGPIOの初期設定、HIGH/LOW用
    GPIO.setup(5, GPIO.OUT)  
    GPIO.setup(6, GPIO.OUT)  
    GPIO.setup(20, GPIO.OUT)  
    GPIO.setup(21, GPIO.OUT)  
    # PWMの初期設定、１０ヘルツにする
    pwm1 = GPIO.PWM(13,10)
    pwm2 = GPIO.PWM(19,10)
    # PWMのスタート、コントローラーから来た数値を利用するので初期値は０にする
    pwm1.start(0)
    pwm2.start(0)
    
    return pwm1,pwm2

async def main():
    wifi_ssid = "******"
    await wait_for_wifi(wifi_ssid)
    
    pwm1 , pwm2 = setup_gpio()
    camera = setup_camera()
    echo_with_pwm = functools.partial(echo, pwm1=pwm1, pwm2=pwm2 ,camera=camera)
 
    
    server = await websockets.serve(echo_with_pwm,"192.168.0.100", 8080)  # ホストとポートを指定
    print("WebSocket server started")
    try:
 
        await server.wait_closed()
    finally:
        GPIO.cleanup()
        # プログラム終了時にcleanup_gpio()関数を実行
        atexit.register(cleanup_gpio)
       # os.system("sudo shutdown now")
    
if __name__ == "__main__":
    # メインループを実行
    asyncio.run(main())
