# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/workspaces/knob-controller/esp-idf/components/bootloader/subproject"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/tmp"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/src/bootloader-stamp"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/src"
  "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/src/bootloader-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/src/bootloader-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/workspaces/knob-controller/lv_micropython/ports/esp32/build_test/bootloader-prefix/src/bootloader-stamp${cfgdir}") # cfgdir has leading slash
endif()
