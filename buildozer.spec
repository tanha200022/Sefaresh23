[app]
title = مدیریت سفارشات
package.name = orderapp
package.domain = org.orderapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json
version = 1.0

requirements = python3,kivy==2.2.1,arabic_reshaper,python-bidi,pillow

orientation = portrait
fullscreen = 0

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
