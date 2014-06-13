from .opencl import *
import numpy as np

uint2 = cl.tools.get_or_register_dtype("uint2")
uint4 = cl.tools.get_or_register_dtype("uint4")
prg = build_program("copy_measure")
prg.copy_measure.set_scalar_arg_dtypes([
    None, uint2, None, None, np.uint32, None, uint4
])
def get_measure(page, staff, measure):
    for system in page.systems:
        barlines = system['barlines']
        if bar_start <= staff and staff < bar_stop:
            break
    else:
        raise Exception("Staff not found in barlines")
    if measure + 1 >= len(barlines):
        raise Exception("Measure out of bounds")
    # Round down measure start x
    x0 = barlines[measure, [0,1]].min() & -8
    # Round up measure end x
    x1 = -(-barlines[measure + 1, [0,1]].max() & -8)

    # Round up staff start y
    y0 = page.boundaries[staff][:, 1].min() & -8
    # Round down staff end y
    y1 = -(-page.boundaries[staff+1][:, 1].max() & -8)

    measure_pixel_size = (y1 - y0, (x1 - x0) // 8)
    measure_size = tuple(-(-i & -16) for i in measure_pixel_size)
    measure = cla.zeros(q, measure_size, np.uint8)
    device_b0 = cla.to_device(q, page.boundaries[staff][:, 1].astype(np.uint32))
    device_b1 = cla.to_device(q, page.boundaries[staff + 1][:, 1]
                                     .astype(np.uint32))
    prg.copy_measure(q, measure.shape[::-1], (1, 1),
                        page.img.data,
                        np.array(page.img.shape[::-1],
                                 np.uint32).view(uint2)[0],
                        device_b0.data, device_b1.data,
                        np.uint32(page.boundaries[staff][1, 0]
                                    - page.boundaries[staff][0, 0]),
                        measure.data,
                        np.array([x0 // 8, y0] + list(measure_size[::-1]),
                                 np.uint32).view(uint4)[0]).wait()
    return measure, (x0, x1, y0, y1)

class Measure:
    page = None
    staff_num = None
    measure_num = None
    image = None
    bounds = None
    start_pitch = None # Set to clef and key signature of previous measure
    pitch_elements = None
    final_pitch = None # Final clef and key signature after this measure
    def __init__(self, page, staff_num, measure_num):
        self.page = page
        self.staff_num = staff_num
        self.measure_num = measure_num
        self.page_staff_y = page.staves[staff_num, [2,3]].sum()/2.0

    def get_image(self):
        if self.image is None:
            self.image, self.bounds = get_measure(self.page,
                                            self.staff_num, self.measure_num)
            self.staff_y = self.page_staff_y - self.bounds[2]
        return self.image
def build_bars(page):
    bars = []
    for system in page.systems:
        bar = []
        for measure in xrange(len(system['barlines']) - 1):
            m = []
            for staff in xrange(system['start'], system['stop']):
                m.append(Measure(page, staff, measure))
            bar.append(m)
        bars.append(bar)
    page.bars = bars
