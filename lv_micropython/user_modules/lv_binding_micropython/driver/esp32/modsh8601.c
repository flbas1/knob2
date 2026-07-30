#include <stdlib.h>
#include <string.h>
#include "py/obj.h"
#include "py/runtime.h"

#define STATIC static
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_sh8601.h"

#pragma push_macro("LV_CONF_PATH")
#undef LV_CONF_PATH
#include "lvgl/src/display/lv_display.h"
#include "lvgl/src/misc/lv_area.h"
#pragma pop_macro("LV_CONF_PATH")

typedef struct {
    mp_obj_base_t base;
    void *data;
} lvmp_struct_t;

typedef struct {
    esp_lcd_panel_handle_t panel;
    esp_lcd_panel_io_handle_t io;
    lv_display_t *current_disp;
    bool initialized;
} sh8601_state_t;

static sh8601_state_t state = {0};

static bool color_trans_done_cb(esp_lcd_panel_io_handle_t io,
                                 esp_lcd_panel_io_event_data_t *edata,
                                 void *user_ctx) {
    (void)io;
    (void)edata;
    (void)user_ctx;
    if (state.current_disp) {
        lv_display_flush_ready(state.current_disp);
    }
    return false;
}

STATIC mp_obj_t mod_sh8601_init(size_t n_args, const mp_obj_t *args) {
    int cs = mp_obj_get_int(args[0]);
    int sclk = mp_obj_get_int(args[1]);
    int d0 = mp_obj_get_int(args[2]);
    int d1 = mp_obj_get_int(args[3]);
    int d2 = mp_obj_get_int(args[4]);
    int d3 = mp_obj_get_int(args[5]);
    int rst = mp_obj_get_int(args[6]);
    size_t max_transfer = 360 * 360 * 2;

    spi_bus_config_t buscfg = SH8601_PANEL_BUS_QSPI_CONFIG(
        sclk, d0, d1, d2, d3, max_transfer);
    ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &buscfg, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_spi_config_t io_config = SH8601_PANEL_IO_QSPI_CONFIG(
        cs, color_trans_done_cb, &state);
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(
        (esp_lcd_spi_bus_handle_t)SPI3_HOST, &io_config, &state.io));

    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = rst,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16,
    };
    sh8601_vendor_config_t vendor_config = {
        .init_cmds = NULL,
        .init_cmds_size = 0,
        .flags.use_qspi_interface = 1,
    };
    panel_config.vendor_config = &vendor_config;

    ESP_ERROR_CHECK(esp_lcd_new_panel_sh8601(
        state.io, &panel_config, &state.panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(state.panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(state.panel));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(state.panel, true));

    state.initialized = true;
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mod_sh8601_init_obj, 7, 7, mod_sh8601_init);

STATIC mp_obj_t mod_sh8601_flush(mp_obj_t disp_drv_obj, mp_obj_t area_obj,
                                  mp_obj_t color_p_obj) {
    if (!state.initialized) {
        lv_display_flush_ready((lv_display_t *)0);
        return mp_const_none;
    }

    lvmp_struct_t *disp_s = (lvmp_struct_t *)MP_OBJ_TO_PTR(disp_drv_obj);
    lvmp_struct_t *area_s = (lvmp_struct_t *)MP_OBJ_TO_PTR(area_obj);
    lv_display_t *disp = (lv_display_t *)disp_s->data;
    const lv_area_t *area = (const lv_area_t *)area_s->data;

    mp_buffer_info_t bufinfo;
    if (!mp_get_buffer(color_p_obj, &bufinfo, MP_BUFFER_READ)) {
        lv_display_flush_ready(disp);
        return mp_const_none;
    }
    uint8_t *color_p = (uint8_t *)bufinfo.buf;

    state.current_disp = disp;

    int x1 = area->x1 & ~1;
    int y1 = area->y1 & ~1;
    int x2 = (area->x2 + 2) & ~1;
    int y2 = (area->y2 + 2) & ~1;

    esp_lcd_panel_draw_bitmap(state.panel, x1, y1, x2, y2, color_p);

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(mod_sh8601_flush_obj, mod_sh8601_flush);

STATIC const mp_rom_map_elem_t mp_module_sh8601_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_sh8601)},
    {MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&mod_sh8601_init_obj)},
    {MP_ROM_QSTR(MP_QSTR_flush), MP_ROM_PTR(&mod_sh8601_flush_obj)},
};
STATIC MP_DEFINE_CONST_DICT(mp_module_sh8601_globals, mp_module_sh8601_globals_table);

const mp_obj_module_t mp_module_sh8601 = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&mp_module_sh8601_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sh8601, mp_module_sh8601);
