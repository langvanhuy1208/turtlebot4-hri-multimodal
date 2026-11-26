#!/usr/bin/env python3
"""Local Vietnamese eSpeak NG synthesis, no network or audio recording."""
import ctypes
import ctypes.util
import sys


def speak(text,output=None):
    lib=ctypes.CDLL(ctypes.util.find_library('espeak-ng'))
    lib.espeak_Initialize.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
    if lib.espeak_Initialize(0,0,None,0)<0:raise RuntimeError('Cannot initialize speech output')
    lib.espeak_SetVoiceByName.argtypes=[ctypes.c_char_p]
    if lib.espeak_SetVoiceByName(b'vi')!=0:raise RuntimeError('Vietnamese voice unavailable')
    lib.espeak_SetParameter(1,165,0)
    data=text.encode('utf-8')+b'\0'
    lib.espeak_Synth.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    buffer=ctypes.create_string_buffer(data)
    code=lib.espeak_Synth(buffer,len(data),0,1,0,1,None,None)
    if code:raise RuntimeError('Speech synthesis failed')
    lib.espeak_Synchronize();lib.espeak_Terminate()

if __name__=='__main__':speak(' '.join(sys.argv[1:]))
