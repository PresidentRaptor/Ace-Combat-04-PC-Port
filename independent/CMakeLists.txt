cmake_minimum_required(VERSION 3.20)
project(ac4_independent_scalar_harness LANGUAGES C)

find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

# Synthetic ADDIU v0,zero,7; BREAK. No game or inherited build inputs.
set(generated "${CMAKE_CURRENT_BINARY_DIR}/synthetic.inc")
add_custom_command(OUTPUT "${generated}"
    COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/r5900_codegen.py"
            --base 0 --words 24020007 0000000d --output "${generated}"
    DEPENDS r5900_codegen.py r5900.py vu_macro.py
    VERBATIM)
add_executable(ac4-scalar-smoke scalar_smoke.c "${generated}")
set(bootstrap_generated "${CMAKE_CURRENT_BINARY_DIR}/generated_program.inc")
add_custom_command(OUTPUT "${bootstrap_generated}"
    COMMAND "${CMAKE_COMMAND}" -E copy "${generated}" "${bootstrap_generated}"
    DEPENDS "${generated}" VERBATIM)
add_executable(ac4-bootstrap-diagnostic bootstrap_main.c bootstrap_services.h ee_devices.h "${bootstrap_generated}")
target_compile_definitions(ac4-bootstrap-diagnostic PRIVATE AC4_PROGRAM_ENTRY=0)
foreach(harness ac4-scalar-smoke ac4-bootstrap-diagnostic)
    target_include_directories(${harness} PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
    if(MSVC)
        target_compile_options(${harness} PRIVATE /W4 /WX)
    else()
        target_compile_options(${harness} PRIVATE -Wall -Wextra -Werror)
    endif()
endforeach()
enable_testing()
add_test(NAME scalar-generated-execution COMMAND ac4-scalar-smoke)
add_test(NAME bootstrap-synthetic-execution
    COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/check_bootstrap_fixture.py"
            "$<TARGET_FILE:ac4-bootstrap-diagnostic>")
