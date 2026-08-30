cmake_minimum_required(VERSION 3.16)
project(audio_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

# libsndfile via vcpkg
find_package(SndFile CONFIG REQUIRED)

# Rubberband - try find_package first (vcpkg), fallback to manual
find_package(rubberband CONFIG QUIET)
if(NOT rubberband_FOUND)
    # Try pkg-config
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(RUBBERBAND rubberband)
    endif()
    # Manual fallback
    if(NOT RUBBERBAND_FOUND)
        find_path(RUBBERBAND_INCLUDE_DIR rubberband/RubberBandStretcher.h
            PATHS
                "C:/vcpkg/installed/x64-windows-static/include"
                "${CMAKE_SOURCE_DIR}/../rubberband-install/include"
        )
        find_library(RUBBERBAND_LIB
            NAMES rubberband rubberband-static
            PATHS
                "C:/vcpkg/installed/x64-windows-static/lib"
                "${CMAKE_SOURCE_DIR}/../rubberband-install/lib"
        )
        if(RUBBERBAND_INCLUDE_DIR AND RUBBERBAND_LIB)
            set(RUBBERBAND_FOUND TRUE)
        else()
            message(FATAL_ERROR "Could not find rubberband library")
        endif()
    endif()
endif()

add_executable(audio_engine main.cpp)

target_include_directories(audio_engine PRIVATE
    ${RUBBERBAND_INCLUDE_DIR}
    ${RUBBERBAND_INCLUDE_DIRS}
)

target_link_libraries(audio_engine PRIVATE
    SndFile::sndfile
)

if(rubberband_FOUND)
    target_link_libraries(audio_engine PRIVATE rubberband::rubberband)
elseif(RUBBERBAND_LIB)
    target_link_libraries(audio_engine PRIVATE ${RUBBERBAND_LIB})
else()
    target_link_libraries(audio_engine PRIVATE ${RUBBERBAND_LIBRARIES})
endif()

# Windows needs these for static linking
if(WIN32)
    target_link_libraries(audio_engine PRIVATE
        winmm ole32 oleaut32 uuid
    )
endif()
