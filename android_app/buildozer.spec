[app]
# App information
title = DALLE Mobile
package.name = dallemobile
package.domain = com.dalle

# Source code
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt

# Version
version = 1.0

# Application requirements
requirements = python3,kivy==2.3.0,kivymd==1.2.0,openai,requests,pillow,certifi,charset-normalizer,idna,urllib3

# Permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# Android specific
android.minapi = 21
android.ndk = 23b
android.sdk = 33
android.accept_sdk_license = True
android.arch = arm64-v8a

# iOS specific
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.7.0

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
