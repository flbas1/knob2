# Firmware C Extensions

This directory contains C source files for MicroPython C extension modules.

These are only needed for hardware functionality not exposed by
standard MicroPython modules. The main candidate is:

- `sh8601_flush.c` — QSPI DMA display flush (if Python is too slow)

## Building

C extensions are compiled into the MicroPython firmware via the
lv_micropython build system. Add source files to `mymodule.cmake`:

```cmake
list(APPEND MICROPY_SOURCE_MOD ${CMAKE_CURRENT_LIST_DIR}/sh8601_flush.c)
```

## Registering a Module

```c
#include "py/obj.h"
#include "py/runtime.h"

STATIC mp_obj_t my_func(mp_obj_t arg) {
    // C implementation
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(my_func_obj, my_func);

STATIC const mp_rom_map_elem_t my_module_globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_mymodule) },
    { MP_ROM_QSTR(MP_QSTR_my_func), MP_ROM_PTR(&my_func_obj) },
};
STATIC MP_DEFINE_CONST_DICT(my_module_globals_table, my_module_globals);

const mp_obj_module_t my_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&my_module_globals_table,
};

MP_REGISTER_MODULE(MP_QSTR_mymodule, my_module, MODULE_MYMODULE_ENABLED);
```
