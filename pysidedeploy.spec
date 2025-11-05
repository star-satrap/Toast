[app]

# title of your application
title = Toast

# project directory. the general assumption is that project_dir is the parent directory
# of input_file
project_dir = .

# source file path
input_file = E:\MyCode\Python\Toast\toast.py

# directory where exec is stored
exec_directory = .

# path to .pyproject project file
project_file = 

# application icon
icon = E:\MyCode\Python\toast_python\DM.ico

[python]

# python path
python_path = E:\MyCode\Python\toast_python\.venv\Scripts\python.exe

# python packages to install
packages = Nuitka==2.4.8

# buildozer = for deploying Android application
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

# comma separated path to qml files required
# normally all the qml files required by the project are added automatically
qml_files = 

# excluded qml plugin binaries
excluded_qml_plugins = 

# qt modules used. comma separated
modules = Widgets,Network,Core,Gui

# qt plugins used by the application
plugins = networkaccess,tls,styles,platforms,platforms/darwin,platforminputcontexts,generic,platformthemes,networkinformation,accessiblebridge,egldeviceintegrations,iconengines,imageformats,xcbglintegrations

[android]

# path to pyside wheel
wheel_pyside = 

# path to shiboken wheel
wheel_shiboken = 

# plugins to be copied to libs folder of the packaged application. comma separated
plugins = 

[nuitka]

# usage description for permissions requested by the app as found in the info.plist file
# of the app bundle
# eg = extra_args = --show-modules --follow-stdlib
macos.permissions = 

# mode of using nuitka. accepts standalone or onefile. default is onefile.
mode = standalone

# (str) specify any extra nuitka arguments
extra_args = --quiet --noinclude-qt-translations --windows-console-mode=disable

[buildozer]

# build mode
# possible options = [release, debug]
# release creates an aab, while debug creates an apk
mode = debug

# contrains path to pyside6 and shiboken6 recipe dir
recipe_dir = 

# path to extra qt android jars to be loaded by the application
jars_dir = 

# if empty uses default ndk path downloaded by buildozer
ndk_path = 

# if empty uses default sdk path downloaded by buildozer
sdk_path = 

# other libraries to be loaded. comma separated.
# loaded at app startup
local_libs = 

# architecture of deployed platform
# possible values = ["aarch64", "armv7a", "i686", "x86_64"]
arch = 

