import lvgl as lv
import micropython

micropython.alloc_emergency_exception_buf(256)

LCD_WIDTH = 360
LCD_HEIGHT = 360

class SH8601:
    def __init__(self, cs=14, sclk=13, d0=15, d1=16, d2=17, d3=18, rst=21,
                 width=360, height=360, factor=4, double_buffer=True,
                 color_format=lv.COLOR_FORMAT.RGB565):
        self.width = width
        self.height = height
        self.factor = factor
        self.double_buffer = double_buffer
        self.pixel_size = lv.color_format_get_size(color_format)
        self.color_format = color_format

        import sh8601 as _hw
        _hw.init(cs, sclk, d0, d1, d2, d3, rst)

        self.buf_size = (width * height * self.pixel_size) // factor
        self.buf1 = bytearray(self.buf_size)
        self.buf2 = bytearray(self.buf_size) if double_buffer else None

        self.disp_drv = lv.display_create(width, height)
        self.disp_drv.set_color_format(color_format)
        self.disp_drv.set_buffers(
            self.buf1, self.buf2, self.buf_size,
            lv.DISPLAY_RENDER_MODE.PARTIAL)
        self.disp_drv.set_flush_cb(self._flush_cb)

    def _flush_cb(self, disp_drv, area, color_p):
        import sh8601 as _hw
        _hw.flush(disp_drv, area, color_p)

    def set_backlight(self, brightness):
        pass

    def sleep(self):
        pass

    def wake(self):
        pass
