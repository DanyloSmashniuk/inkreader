[app]
title = InkReader
package.name = inkreader
package.domain = io.github.danylosmashniuk
source.dir = src
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 0.1
icon.filename = %(source.dir)s/icon.png
presplash.filename = assets/presplash.png
android.presplash_color = #E6E6E0
requirements = python3,kivy==2.3.1,plyer,android
p4a.branch = master
orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE
android.manifest.intent_filters = assets/intent_filters.xml
android.manifest.launch_mode = singleTask
android.api = 36
android.ndk = 28c
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
