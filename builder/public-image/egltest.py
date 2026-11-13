#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check whether EGL works on the firmware-framebuffer DRM device (simpledrm) with the current environment (run as root on the live system).

Opens /dev/dri/card0 (or argv[1]), creates a GBM device, an EGL display on it, a surfaceless OpenGL ES context and prints the GL renderer.
KWin's DRM backend needs the same chain; this isolates it from the session so the graphics environment can be tuned in an emulator.
"""
import ctypes as C, os, sys

dev = sys.argv[1] if len(sys.argv) > 1 else '/dev/dri/card0'
try:
    fd = os.open(dev, os.O_RDWR)
except OSError as e:
    print('open', dev, 'failed:', e); sys.exit(2)
gbm = C.CDLL('libgbm.so.1'); egl = C.CDLL('libEGL.so.1'); gles = C.CDLL('libGLESv2.so.2')
gbm.gbm_create_device.restype = C.c_void_p
egl.eglGetPlatformDisplay.restype = C.c_void_p
egl.eglGetPlatformDisplay.argtypes = [C.c_uint, C.c_void_p, C.c_void_p]
egl.eglQueryString.restype = C.c_char_p
egl.eglQueryString.argtypes = [C.c_void_p, C.c_int]
egl.eglCreateContext.restype = C.c_void_p
egl.eglCreateContext.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int)]
egl.eglMakeCurrent.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
egl.eglBindAPI.argtypes = [C.c_uint]
gles.glGetString.restype = C.c_char_p
gdev = gbm.gbm_create_device(fd)
print('gbm device:', bool(gdev))
dpy = egl.eglGetPlatformDisplay(0x31D7, gdev, None)        # EGL_PLATFORM_GBM_KHR
print('egl display:', bool(dpy))
maj, mino = C.c_int(), C.c_int()
ok = egl.eglInitialize(C.c_void_p(dpy), C.byref(maj), C.byref(mino))
print('eglInitialize:', ok, '%d.%d' % (maj.value, mino.value), 'error 0x%x' % egl.eglGetError())
if not ok:
    sys.exit(3)
print('EGL_VENDOR:', egl.eglQueryString(C.c_void_p(dpy), 0x3053))
egl.eglBindAPI(0x30A0)                                       # EGL_OPENGL_ES_API
attr = (C.c_int * 3)(0x3098, 2, 0x3038)                      # EGL_CONTEXT_CLIENT_VERSION 2, EGL_NONE
ctx = egl.eglCreateContext(C.c_void_p(dpy), None, None, attr)
print('context:', bool(ctx), 'error 0x%x' % egl.eglGetError())
if ctx:
    made = egl.eglMakeCurrent(C.c_void_p(dpy), None, None, C.c_void_p(ctx))
    print('makeCurrent (surfaceless):', made, 'error 0x%x' % egl.eglGetError())
    if made:
        print('GL_RENDERER:', gles.glGetString(0x1F01), '| GL_VERSION:', gles.glGetString(0x1F02))
