import os
if os.name =="nt":
    os.environ["SDL_AUDIODRIVER"] = "directsound"
import math
import tkinter as tk
import random
import pyaudio
import soundfile as sf
import pygame
from tkinter import filedialog
import numpy as np
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
screen_width = 1000
screen_height = 1000
background_colour = (151, 89,154)
pygame.display.init()
pygame.font.init()
pygame.display.set_caption("Album Audio")
screen = pygame.display.set_mode((screen_width, screen_height), pygame.SCALED,)

PANEL_H=70
BAR_BASE = screen_height - PANEL_H
THEMES_DEF = [
    ("Graduation - Kanye", "bear.png", "background.jpg",
     {"panel": (50,15,70,200),"track": (110,60,130), "fill": (255,170,50), "text": (255,255,255),
      "bar_low": (255,200,50), "bar_high": (255,90,160), "wave": (255,255,255)}),
    ("Blonde - Frank Ocean", "frankocean.png", "blonded.jpg",
     {"panel": (40,35,30,200), "track": (90,85,70), "fill": (50,220,80), "text": (255,255,255),
      "bar_low": (30,255,80), "bar_high": (200,255,120), "wave": (50,220,80)})
]
panel_surf = pygame.Surface((screen_width, PANEL_H), pygame.SRCALPHA)
themes = []

for name, char_file, bg_file, style in THEMES_DEF:
    char_path = os.path.join(BASE_DIR, char_file)
    bg_path = os.path.join(BASE_DIR, bg_file)
    if os.path.exists(char_path) and os.path.exists(bg_path):
        char_img = pygame.image.load(char_path).convert_alpha()
        char_img = pygame.transform.scale(char_img, (200, 250))
        bg_img = pygame.image.load(bg_path).convert()
        bg_img = pygame.transform.scale(bg_img, (screen_width, screen_height))
        themes.append((name, char_img, bg_img, style))


if not themes:
    raise SystemExit(f"Could not find themes pictures in {BASE_DIR} :(")

base_count = len(themes)
CUSTOM_STYLE = {"panel": (40,40,60,200), "track": (90,90,110), "fill": (255,170,50),
                "text": (255,255,255), "bar_low": (255,200,50), "bar_high": (255,90,160),
                "wave": (255,255,255)

}

font_big = pygame.font.SysFont(None, 90)
font_small = pygame.font.SysFont(None, 40)

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

p = pyaudio.PyAudio()
stream = None

NUM_BARS=16
edges =[1,2,3,4,5,6,8,10,13,17,22,30,40,60,90,140,250]

bar_heights = [0.0] * NUM_BARS

window = np.hanning(CHUNK)
MIN_REF = 40
auto_max = MIN_REF
wave_ref = 2000.0
wave_y = np.zeros(256)
source = "mic"
file_samples = None
file_rate = 44100
file_duration =0
MODES =["bars", "wave", "circle"]
RING_POINTS = 64
CIRCLE_CX = screen_width //2 
BASE_R = 170
MAX_PARTICLES = 400
ring_heights = np.zeros(NUM_BARS)
particles = []
particle_layer = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
fill_layer = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
CIRCLE_CY = screen_height // 2 -40

SCALE = 5000
def stop_stream():
    global stream
    if stream is not None:
        try:
            stream.stop_stream()
            stream.close()
        except OSError:
            pass
        stream = None
def mic_aviable():
    global p

    p.terminate()
    p = pyaudio.PyAudio()
    test = None
    try:
        p.get_default_input_device_info()
        test = p.open(format=FORMAT,
                      channels=CHANNELS,
                      rate=RATE,
                      input=True,
                      frames_per_buffer=CHUNK)
        test.read(CHUNK, exception_on_overflow=False)
        return True     

    except Exception:
        return False

    finally:

        if test is not None:
            try:
                test.stop_stream()
                test.close()
            except Exception:
                pass

def output_aviable():
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return True
    except pygame.error:
        return False

def start_stream():
    global stream
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)



        return True
    except Exception:
        return False


def mix(c1,c2,t):
    return tuple(int(a + (b-a)*t)for a,b in zip(c1,c2))
def get_targets(spectrum):
    global auto_max
    values = np.array([np.mean(spectrum[edges[i]:edges[i+1]])for i in range(NUM_BARS)])
    values = values * (1+np.arange(NUM_BARS)*0.25)
    values = np.sqrt(values)
    auto_max = max(values.max(), auto_max*0.995, MIN_REF)
    return np.minimum(values / auto_max,1)*400
def draw_bars(spectrum, style):
    targets = get_targets(spectrum)
    
    bar_width = screen_width / NUM_BARS
    for i in range(NUM_BARS):
        speed = 0.6 if targets[i] > bar_heights[i] else 0.12   
        bar_heights[i] += (targets[i] - bar_heights[i]) * speed

        color = mix(style["bar_low"], style["bar_high"], i / (NUM_BARS - 1))

        x = int(i * bar_width) + 4
        h = int(bar_heights[i])
        pygame.draw.rect(screen, color, (x, BAR_BASE - h, int(bar_width) - 8, h))
    

def draw_wave(samples, style):
    global wave_ref

    seg = samples[:1024].reshape(256, 4).mean(axis=1)
    wave_ref = max(np.abs(seg).max(), wave_ref * 0.995, 2000)   
    target = seg / wave_ref * 300
    wave_y[:] += (target - wave_y) * 0.3

    padded = np.pad(wave_y, 1, mode="edge")
    smooth = np.convolve(padded, np.ones(3) / 3, mode="valid")

    xs = (np.arange(256) / 256 * screen_width).astype(int)
    ys = (screen_height // 2 + smooth).astype(int)
    points = list(zip(xs.tolist(), ys.tolist()))

    pygame.draw.lines(screen, style["wave"], False, points, 4)

def draw_circle(spectrum, style):
    targets = get_targets(spectrum)
    for i in range(NUM_BARS):
        speed = 0.6 if targets[i] > ring_heights[i] else 0.12
        ring_heights[i] += (targets[i] - ring_heights[i])*speed

    f = 1 -np.abs(np.linspace(-1,1, RING_POINTS, endpoint=False))
    amp = np.interp(f * (NUM_BARS -1), np.arange(NUM_BARS), ring_heights)
    angles = np.arange(RING_POINTS) / RING_POINTS *2*math.pi - math.pi /2

    cx,cy = CIRCLE_CX, CIRCLE_CY
    pts = []
    for a,h in zip(angles,amp):
        r = BASE_R + h * 0.45
        c,s = math.cos(a), math.sin(a)
        color = mix(style["bar_low"], style["bar_high"], min(h / 400,1))
        pygame.draw.line(screen, color, 
                         (cx + c * BASE_R, cy +s * BASE_R),
                         (cx +c* r, cy +s*r),4)

        pts.append((cx + c*r, cy+s *r))
    
    fill_layer.fill((0,0,0,0))
    pygame.draw.polygon(fill_layer, (*style["bar_low"],230), pts)
    pygame.draw.circle(fill_layer, (*style["bar_high"], 200), (cx,cy), BASE_R-8)
    screen.blit(fill_layer, (0,0))
    pygame.draw.lines(screen, style["wave"], True, pts, 2)
    pygame.draw.circle(screen,style["wave"], (cx,cy), BASE_R-8,2)

    bass = ring_heights[:3].mean() / 400
    spawn = int(bass*10) + (1 if random.random() < 0.3 else 0)
    for _ in range(spawn):
        if len(particles) < MAX_PARTICLES:
            life = random.randint(40,90)
            particles.append([random.uniform(0,2*math.pi), BASE_R+4,
                              1.2 + bass*5 + random.random()*1.5,
                              random.uniform(-0.006, 0.006),
                              life, life, random.choice((1,2,2,3))])


    particle_layer.fill((0,0,0,0))
    
    for pt in particles:
        pt[0] += pt[3]
        pt[1] += pt[2]
        pt[4] -= 1
        alpha = int(255*pt[4] / pt[5])
        px = int(cx + math.cos(pt[0] )* pt[1])
        py = int(cy + math.sin(pt[0])*pt[1])
        color = mix(style["bar_low"], style["bar_high"],min( pt[1] / 600, 1))
        pygame.draw.circle(particle_layer, (*color, alpha), (px,py), pt[6])

    particles[:] = [pt for pt in particles if pt[4] > 0]
    screen.blit(particle_layer, (0,0))
def draw_text(text, y, font, color):
    image = font.render(text, True, color)
    rect = image.get_rect(center=(screen_width // 2, y))
    screen.blit(image, rect)


def draw_progress(): 
    style = themes[current_theme][3]
    elapsed = max(0, pygame.mixer.music.get_pos() /1000)
    progress = min(elapsed / file_duration, 1) if file_duration >0 else 0
    
    panel_surf.fill(style["panel"])
    screen.blit(panel_surf, (0,BAR_BASE))

    fill_w = int(screen_width*progress)
    if fill_w>0:
        pygame.draw.rect(screen,style["fill"] , (0,BAR_BASE, fill_w, PANEL_H))
        
def get_audio():
    data = stream.read(CHUNK, exception_on_overflow=False)

    samples = np.frombuffer(data, dtype=np.int16).astype(float)

    level = math.sqrt(np.mean(samples * samples))

    spectrum = np.abs(np.fft.rfft(samples *window))
    return level, spectrum, samples

def open_file():
    global file_samples, file_rate, source, file_duration

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.ogg *.flac")])
    root.destroy()

    if not path:
        return False

    try:
        data, rate = sf.read(path, dtype="float32")
        pygame.mixer.init()
        pygame.mixer.music.load(path)
    except Exception as e:
        print(e)
        return False

    if data.ndim == 2:
        data = data.mean(axis=1)

    file_samples = data * 32768
    file_rate = rate
    source = "file"
    file_duration = len(data) /rate
    return True

def get_audio_file():
    ms = pygame.mixer.music.get_pos()
    if ms < 0:
        samples = np.zeros(CHUNK)
    else:
        pos = int(ms / 1000 * file_rate)
        samples = file_samples[pos:pos + CHUNK].astype(float)
        if len(samples) < CHUNK:
            samples = np.zeros(CHUNK)

    level = math.sqrt(np.mean(samples * samples))
    spectrum = np.abs(np.fft.rfft(samples*window))
    return level, spectrum, samples
def pick_image(title):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title = title,
        filetypes=[("Images", "*.jpg *.png *.jpeg *.bmp ")]
    )
    root.destroy()
    return path
def make_custom_theme():
    bg_path = pick_image("Choose your background")
    if not bg_path:
        return False
    char_path = pick_image("Choose your figure (PNG with transparent background works best)")
    if not char_path:
        return False

    try:
        bg_img = pygame.image.load(bg_path).convert()
        bg_img = pygame.transform.smoothscale(bg_img, (screen_width, screen_height))

        char_img = pygame.image.load(char_path).convert_alpha()
        w, h = char_img.get_size()
        new_h = 250
        new_w = min(int(w * new_h / h), 400)
        char_img = pygame.transform.smoothscale(char_img, (new_w, new_h))
    except Exception as e:
        print(e)
        return False

    theme = ("Custom", char_img, bg_img, CUSTOM_STYLE)
    if len(themes) > base_count:
        themes[base_count] = theme
    else:
        themes.append(theme)
    return True
def go_home():
    global stream, state, message, auto_max, wave_ref

    if pygame.mixer.get_init():
        pygame.mixer.music.stop()

    stop_stream()

    for i in range(NUM_BARS):
        bar_heights[i] = 0
    
    wave_y[:] = 0
    auto_max = MIN_REF
    wave_ref = 2000.0
    wave_y[:] = 0
    ring_heights[:] = 0
    particles.clear()
    message = ""
    state = "start"
    



def start_with_theme(index):
    global bear, background, state, message, bear_y, current_theme

    if source == "mic":
        if not start_stream():
            message = "Can not open the mike or mic :("
            state = "start"
            return

    else:
        pygame.mixer.music.play()



    bear = themes[index][1]
    background = themes[index][2]
    current_theme = index  
    bear_y = ground_y
    state = "play"


clock = pygame.time.Clock()
ground_y = screen_height -250
bear_y = ground_y

state = "start"
has_mic = mic_aviable() #  I just noticed that I spelled it wrong, but i am too lazy to change everything
message=""
mode = "bars"

current_theme = 0

running = True
while running:
    clock.tick(50)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()

        elif event.type == pygame.KEYDOWN and event.key ==  pygame.K_ESCAPE and state == "start":
            running = False

        
            
    
        
        elif event.type == pygame.KEYDOWN and state == "start":


            if event.key == pygame.K_m:
                has_mic = mic_aviable()
                message = ""


                if has_mic:
                    source = "mic"
                    state = "style"

                else:
                    message = "No mike or mic or mikey found :("


            if event.key == pygame.K_f:
                message = ""

                if not output_aviable():
                    message = "No audio output device found :("
                elif open_file():
                    state = "style"

                else:
                    message = "You did not select a file or your file could not be open :( "

            #if event.key == pygame.K_r:
                #has_mic = mic_aviable ()
                #message = ""
            

        elif event.type == pygame.KEYDOWN and state == "style":
            
            if event.key == pygame.K_h:
                go_home()

            elif event.unicode in tuple("0123456789"):
                choice = int(event.unicode) - 1
                if choice == base_count:
                    if make_custom_theme():
                        start_with_theme(base_count)
                    
                    else:
                        message = "No figure or background selected, or file could not be opened"
                elif 0 <= choice < base_count:
                    start_with_theme(choice)
           
        elif event.type == pygame.KEYDOWN and state == "play":
            if event.key == pygame.K_w:
                mode = MODES[(MODES.index(mode)+1)%len(MODES)]
                particles.clear()
            if event.key == pygame.K_h:
                go_home()
                


    if state == "start":
        screen.fill(background_colour)

        for i, theme in enumerate(themes[:base_count]):
            screen.blit(theme[1], (100 + i * 600,750))

        draw_text("Album Audio",300,font_big, (255,255,255))
        draw_text("Choose your audio source :)", 390, font_small, (255,255,255))

        draw_text("M - Mic or Mike", 500, font_small, (180,240,120))
        draw_text("F - Audio file", 560, font_small, (180,240,120))

        if message !="":
            draw_text(message, 700, font_small, (255,150,100))

        pygame.display.flip()
        continue
    if state == "style":
        screen.fill(background_colour)

        draw_text("Choose your style :)", 300, font_big, (255,255,255))

        for i in range(base_count):
            draw_text(f"{i+1} -  {themes[i][0]}", 430 + i * 60, font_small, (180, 240, 120))

        draw_text(f"{base_count+1} - Custom(own figure & background)",
                  430+ base_count*60,font_small, (180,240,120) )

        draw_text("H-Home", 430 + (base_count +1)* 60 +40, font_small, (255,150,100))

        if message!= "":
            draw_text(message, 800, font_small, (255,150,100))
        pygame.display.flip()
        continue


    if source =="file" and not pygame.mixer.music.get_busy():
        go_home()
        continue
    
    if source == "mic":
        try:
            level, spectrum, samples = get_audio()

        except (OSError, AttributeError):
            message = "Mic or mike error. Press M to retry or F for a file."


            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except OSError:
                    pass
                stream = None
            state="start"
            continue

    else:
        level, spectrum, samples = get_audio_file()
     




    jump_height = min(level / 20 , 700)
    target_y = ground_y - jump_height
    bear_y += (target_y - bear_y) * 0.15


    screen.blit(background, (0, 0))




    style= themes[current_theme][3]
    if mode == "bars":
        draw_bars(spectrum, style)
    elif mode == "wave":
        draw_wave(samples, style)
    else:
        draw_circle(spectrum, style)
    screen.blit(bear, (150, int(bear_y)))

    if source =="file":
        draw_progress()

    next_mode = MODES[(MODES.index(mode)+1) %len(MODES)]
    hint = font_small.render(f"Press W to change to {next_mode}", True, (255,255,255))
    
    screen.blit(hint, (20,20) )


    hint2 = font_small.render("Press H to go back to the start screen", True, (255, 255, 255))
            
    screen.blit(hint2, (20, 55))

    pygame.display.flip()


stop_stream()
p.terminate()
pygame.quit()
