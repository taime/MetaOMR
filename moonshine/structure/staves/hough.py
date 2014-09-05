from ...gpu import *
from ... import filter, hough, bitimage
from ...cl_util import max_kernel
import numpy as np

def staff_center_lines(page):
    staff_filt = filter.staff_center(page)
    page.staff_filt = staff_filt
    thetas = np.linspace(-np.pi/500, np.pi/500, 51)
    rhores = page.staff_thick*3
    page.staff_bins = hough.hough_line_kernel(staff_filt, rhores=rhores,
                              numrho=page.img.shape[0] // rhores, thetas=thetas)
    # Some staves may have multiple Hough peaks so we need to take many more
    # peaks than the number of staves. Also, the strongest Hough response
    # doesn't always correspond to the longest segment, so we need many peaks
    # to find the longest segment, corresponding to the complete staff.
    # Most images shouldn't need this many peaks, but performance doesn't
    # seem to be an issue.
    peaks = hough.houghpeaks(page.staff_bins,
                             thresh=max_kernel(page.staff_bins)/4.0)
    page.staff_peak_theta = thetas[peaks[:, 0]]
    page.staff_peak_rho = peaks[:, 1]
    lines = hough.hough_lineseg_kernel(staff_filt,
                                 page.staff_peak_rho, page.staff_peak_theta,
                                 rhores=rhores, max_gap=page.staff_dist*8).get()
    page.staff_center_lines = lines
    return lines

def staves(page):
    lines = staff_center_lines(page)
    staves = hough.hough_paths(lines)
    # Filter out staves which are too short
    good_staves = (staves[:, 1, 0] - staves[:, 0, 0]) > page.orig_size[1] / 2.0
    page.staves = np.ma.array(staves[good_staves], np.int32,
                              fill_value=-1)
    return page.staves

def show_staff_filter(page):
    import pylab as p
    # Overlay staff line points
    staff_filt = np.unpackbits(page.staff_filt.get()).reshape((4096, -1))
    staff_line_mask = np.ma.masked_where(staff_filt == 0, staff_filt)
    p.imshow(staff_line_mask, cmap='Greens')
def show_staff_segments(page):
    self.show_staff_filter()
    import pylab as p
    for (x0, y0), (x1, y1) in page.staff_center_lines:
        p.plot([x0, x1], [y0, y1], 'g')
