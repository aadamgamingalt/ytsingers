cmake_minimum_required(VERSION 3.16)
project(audio_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

find_package(SndFile CONFIG REQUIRED)

add_executable(audio_engine main.cpp)

target_link_libraries(audio_engine PRIVATE SndFile::sndfile)

if(WIN32)
    target_link_libraries(audio_engine PRIVATE winmm ole32 oleaut32 uuid)
endif()

install(TARGETS audio_engine DESTINATION .)
