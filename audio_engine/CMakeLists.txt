cmake_minimum_required(VERSION 3.16)
project(audio_engine)

set(CMAKE_CXX_STANDARD 17)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SNDFILE REQUIRED sndfile)
pkg_check_modules(RUBBERBAND REQUIRED rubberband)

add_executable(audio_engine main.cpp)

target_include_directories(audio_engine PRIVATE
    ${SNDFILE_INCLUDE_DIRS}
    ${RUBBERBAND_INCLUDE_DIRS}
)

target_link_libraries(audio_engine PRIVATE
    ${SNDFILE_LIBRARIES}
    ${RUBBERBAND_LIBRARIES}
)

install(TARGETS audio_engine DESTINATION .)

