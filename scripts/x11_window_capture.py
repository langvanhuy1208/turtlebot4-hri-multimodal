#!/usr/bin/env python3
"""Capture only a window's actual XComposite backing pixmap, even if covered.

The content is captured from the application, not reconstructed or rendered
from ROS state. Requires an X11 desktop with a running compositor.
"""
import ctypes as ct
import numpy as np
from PIL import Image


class XImage(ct.Structure):
    _fields_=[('width',ct.c_int),('height',ct.c_int),('xoffset',ct.c_int),('format',ct.c_int),
              ('data',ct.c_void_p),('byte_order',ct.c_int),('bitmap_unit',ct.c_int),
              ('bitmap_bit_order',ct.c_int),('bitmap_pad',ct.c_int),('depth',ct.c_int),
              ('bytes_per_line',ct.c_int),('bits_per_pixel',ct.c_int),
              ('red_mask',ct.c_ulong),('green_mask',ct.c_ulong),('blue_mask',ct.c_ulong)]


class WindowCapture:
    def __init__(self):
        self.x=ct.CDLL('libX11.so.6');self.c=ct.CDLL('libXcomposite.so.1')
        self.x.XOpenDisplay.argtypes=[ct.c_char_p];self.x.XOpenDisplay.restype=ct.c_void_p
        self.x.XCloseDisplay.argtypes=[ct.c_void_p]
        self.x.XSync.argtypes=[ct.c_void_p,ct.c_int]
        self.c.XCompositeNameWindowPixmap.argtypes=[ct.c_void_p,ct.c_ulong]
        self.c.XCompositeNameWindowPixmap.restype=ct.c_ulong
        self.x.XGetGeometry.argtypes=[ct.c_void_p,ct.c_ulong,ct.POINTER(ct.c_ulong),
            ct.POINTER(ct.c_int),ct.POINTER(ct.c_int),ct.POINTER(ct.c_uint),ct.POINTER(ct.c_uint),
            ct.POINTER(ct.c_uint),ct.POINTER(ct.c_uint)]
        self.x.XGetImage.argtypes=[ct.c_void_p,ct.c_ulong,ct.c_int,ct.c_int,ct.c_uint,ct.c_uint,ct.c_ulong,ct.c_int]
        self.x.XGetImage.restype=ct.POINTER(XImage)
        self.x.XDestroyImage.argtypes=[ct.POINTER(XImage)]
        self.x.XFreePixmap.argtypes=[ct.c_void_p,ct.c_ulong]
        self.error_type=ct.CFUNCTYPE(ct.c_int,ct.c_void_p,ct.c_void_p)
        self.error_handler=self.error_type(lambda display,event:0)
        self.x.XSetErrorHandler.argtypes=[self.error_type]
        self.x.XSetErrorHandler(self.error_handler)
        self.display=self.x.XOpenDisplay(None)
        if not self.display:raise RuntimeError('Cannot open X11 display')

    def grab(self,window):
        window=int(window,16) if isinstance(window,str) else window
        pixmap=self.c.XCompositeNameWindowPixmap(self.display,window)
        self.x.XSync(self.display,False)
        if not pixmap:return None
        image=None
        try:
            root=ct.c_ulong();x=ct.c_int();y=ct.c_int();w=ct.c_uint();h=ct.c_uint();border=ct.c_uint();depth=ct.c_uint()
            if not self.x.XGetGeometry(self.display,pixmap,ct.byref(root),ct.byref(x),ct.byref(y),
                    ct.byref(w),ct.byref(h),ct.byref(border),ct.byref(depth)):return None
            image=self.x.XGetImage(self.display,pixmap,0,0,w.value,h.value,ct.c_ulong(-1).value,2)
            if not image:return None
            data=image.contents
            raw=ct.string_at(data.data,data.bytes_per_line*data.height)
            bpp=data.bits_per_pixel//8
            pixels=np.frombuffer(raw,dtype=np.uint8).reshape(data.height,data.bytes_per_line)[:,:data.width*bpp].reshape(data.height,data.width,bpp)
            value=np.zeros((data.height,data.width),dtype=np.uint32)
            for index in range(bpp):value|=pixels[:,:,index].astype(np.uint32) << (8*(index if data.byte_order==0 else bpp-index-1))
            channels=[]
            for mask in (data.red_mask,data.green_mask,data.blue_mask):
                shift=(mask&-mask).bit_length()-1
                channels.append(((value&mask)>>shift).astype(np.uint8))
            return Image.fromarray(np.stack(channels,axis=-1))
        finally:
            if image:self.x.XDestroyImage(image)
            self.x.XFreePixmap(self.display,pixmap)

    def close(self):
        if self.display:self.x.XCloseDisplay(self.display);self.display=None
