[app]
title = InkReader
package.name = inkreader
package.domain = io.github.danylosmashniuk
source.dir = src
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 0.1
icon.filename = %(source.dir)s/icon.png
requirements = python3,kivy==2.3.0,plyer,android
p4a.branch = v2024.01.21
orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE
android.api = 33
android.ndk = 25b
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
