import os
import ctypes
from PIL import Image, ImageDraw, ImageFont

# SDL2 constants
SDL_INIT_VIDEO = 0x00000020
SDL_WINDOW_SHOWN = 0x00000004

# SDL2 library handles
libSDL2 = None
libSDL2_ttf = None

# Screen dimensions
screen_resolutions = {
    1: (720, 720, 18),
    2: (720, 480, 11),
    3: (640, 480, 11),
}

# Default values, will be set in draw_start
screen_width, screen_height, max_elem = 640, 480, 11

# Colors
colorBlue = (187, 114, 0, 255)
colorBlueD1 = (127, 79, 0, 255)
colorGray = (41, 41, 41, 255)
colorGrayL1 = (56, 56, 56, 255)
colorGrayD2 = (20, 20, 20, 255)
colorYellow = (255, 200, 0, 255)
colorYellowD1 = (180, 140, 0, 255)
colorWhite = (255, 255, 255, 255)
colorBlack = (0, 0, 0, 255)

# Font cache
font_cache = {}

# SDL objects
window = None
renderer = None

# PIL objects for offscreen rendering
activeImage = None
activeDraw = None


def init_sdl2():
    """Initialize SDL2 and SDL2_ttf"""
    global libSDL2, libSDL2_ttf, window, renderer
    
    try:
        libSDL2 = ctypes.CDLL('libSDL2-2.0.so.0')
        libSDL2_ttf = ctypes.CDLL('libSDL2_ttf-2.0.so.0')
    except Exception as e:
        return False
    
    # SDL_Init
    libSDL2.SDL_Init.argtypes = [ctypes.c_uint32]
    libSDL2.SDL_Init.restype = ctypes.c_int
    
    if libSDL2.SDL_Init(SDL_INIT_VIDEO) != 0:
        print("SDL_Init failed")
        return False
    
    # SDL_ttf_Init
    libSDL2_ttf.TTF_Init.argtypes = []
    libSDL2_ttf.TTF_Init.restype = ctypes.c_int
    
    if libSDL2_ttf.TTF_Init() != 0:
        libSDL2.SDL_Quit()
        return False
    
    # Create window
    libSDL2.SDL_CreateWindow.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
    libSDL2.SDL_CreateWindow.restype = ctypes.c_void_p
    
    window = libSDL2.SDL_CreateWindow(
        b"Tiny Scraper", 0, 0, screen_width, screen_height, SDL_WINDOW_SHOWN
    )
    
    if not window:
        libSDL2_ttf.TTF_Quit()
        libSDL2.SDL_Quit()
        return False
    
    # Create renderer
    libSDL2.SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    libSDL2.SDL_CreateRenderer.restype = ctypes.c_void_p
    
    SDL_RENDERER_SOFTWARE = 0x00000001
    renderer = libSDL2.SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE)
    
    if not renderer:
        libSDL2.SDL_DestroyWindow(window)
        libSDL2_ttf.TTF_Quit()
        libSDL2.SDL_Quit()
        return False
    
    return True


def draw_start(hw_info=0):
    """Initialize graphics system"""
    global activeImage, activeDraw, screen_width, screen_height, max_elem
    
    # Set screen resolution based on hardware info
    screen_width, screen_height, max_elem = screen_resolutions.get(hw_info, (640, 480, 11))
    
    if not init_sdl2():
        raise RuntimeError("Failed to initialize SDL2")
    
    activeImage = Image.new("RGBA", (screen_width, screen_height), color="black")
    activeDraw = ImageDraw.Draw(activeImage)


def draw_end():
    """Cleanup graphics system"""
    if libSDL2 and renderer:
        libSDL2.SDL_DestroyRenderer(renderer)
    if libSDL2 and window:
        libSDL2.SDL_DestroyWindow(window)
    if libSDL2_ttf:
        libSDL2_ttf.TTF_Quit()
    if libSDL2:
        libSDL2.SDL_Quit()


def create_image():
    """Create a new image"""
    return Image.new("RGBA", (screen_width, screen_height), color="black")


def draw_active(image):
    """Set active image for drawing"""
    global activeImage, activeDraw
    activeImage = image
    activeDraw = ImageDraw.Draw(activeImage)


def draw_paint():
    """Display the active image on screen"""
    global renderer, activeImage
    
    if not libSDL2 or not renderer or not activeImage:
        return
    
    # Get raw pixels from PIL image
    img = activeImage.convert("RGBA")
    pixels = img.tobytes()
    
    # Create SDL surface first
    libSDL2.SDL_CreateRGBSurfaceFrom.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, 
                                                 ctypes.c_int, ctypes.c_int, 
                                                 ctypes.c_uint32, ctypes.c_uint32, 
                                                 ctypes.c_uint32, ctypes.c_uint32]
    libSDL2.SDL_CreateRGBSurfaceFrom.restype = ctypes.c_void_p
    
    rmask = 0x000000FF
    gmask = 0x0000FF00
    bmask = 0x00FF0000
    amask = 0xFF000000
    
    surface = libSDL2.SDL_CreateRGBSurfaceFrom(
        pixels, screen_width, screen_height, 32, screen_width * 4,
        rmask, gmask, bmask, amask
    )
    
    if not surface:
        return
    
    # Create texture from surface
    libSDL2.SDL_CreateTextureFromSurface.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libSDL2.SDL_CreateTextureFromSurface.restype = ctypes.c_void_p
    
    texture = libSDL2.SDL_CreateTextureFromSurface(renderer, surface)
    
    # Free surface
    libSDL2.SDL_FreeSurface.argtypes = [ctypes.c_void_p]
    libSDL2.SDL_FreeSurface(surface)
    
    if not texture:
        return
    
    # Clear renderer
    libSDL2.SDL_SetRenderDrawColor.argtypes = [ctypes.c_void_p, ctypes.c_uint8, 
                                                ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
    libSDL2.SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255)
    libSDL2.SDL_RenderClear.argtypes = [ctypes.c_void_p]
    libSDL2.SDL_RenderClear(renderer)
    
    # Copy texture to renderer
    libSDL2.SDL_RenderCopy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, 
                                       ctypes.c_void_p, ctypes.c_void_p]
    libSDL2.SDL_RenderCopy(renderer, texture, None, None)
    
    # Present renderer
    libSDL2.SDL_RenderPresent.argtypes = [ctypes.c_void_p]
    libSDL2.SDL_RenderPresent(renderer)
    
    # Cleanup texture
    libSDL2.SDL_DestroyTexture.argtypes = [ctypes.c_void_p]
    libSDL2.SDL_DestroyTexture(texture)


def draw_clear():
    """Clear the screen with black"""
    global activeDraw
    activeDraw.rectangle((0, 0, screen_width, screen_height), fill="black")


def draw_text(position, text, font=15, color="white", **kwargs):
    """Draw text on screen"""
    global activeDraw
    
    font_size = font
    if font_size not in font_cache:
        # Try Chinese font first
        try:
            font_cache[font_size] = ImageFont.truetype(
                "/usr/share/fonts/source-han-sans-cn/SourceHanSansCN-Regular.otf", font_size
            )
        except:
            try:
                font_cache[font_size] = ImageFont.truetype(
                    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf", font_size
                )
            except:
                try:
                    font_cache[font_size] = ImageFont.truetype(
                        "/usr/share/fonts/TTF/DejaVuSansMono.ttf", font_size
                    )
                except:
                    font_cache[font_size] = ImageFont.load_default()
    
    activeDraw.text(position, text, font=font_cache[font_size], fill=color, **kwargs)


def draw_rectangle(position, fill=None, outline=None, width=1):
    """Draw a rectangle"""
    global activeDraw
    activeDraw.rectangle(position, fill=fill, outline=outline, width=width)


def draw_rectangle_r(position, radius, fill=None, outline=None):
    """Draw a rounded rectangle"""
    global activeDraw
    activeDraw.rounded_rectangle(position, radius, fill=fill, outline=outline)


def draw_circle(position, radius, fill=None, outline="white"):
    """Draw a circle"""
    global activeDraw
    activeDraw.ellipse(
        [position[0], position[1], position[0] + radius, position[1] + radius],
        fill=fill,
        outline=outline,
    )


def draw_log(text, fill=colorBlue, outline=colorBlueD1, width=500):
    """Draw a centered log message box"""
    x = (screen_width - width) / 2
    y = (screen_height - 80) / 2
    
    # Convert color tuples to hex strings for PIL
    def color_to_hex(c):
        if isinstance(c, tuple):
            return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        return c
    
    draw_rectangle_r([x, y, x + width, y + 80], 5, 
                     fill=color_to_hex(fill), 
                     outline=color_to_hex(outline))
    text_x = x + width / 2
    text_y = y + 40
    draw_text((text_x, text_y), text, anchor="mm")

# imgMain will be created after draw_start is called with hw_info
imgMain = None
