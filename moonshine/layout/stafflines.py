from .. import hough
import numpy as np
from scipy.ndimage import maximum_filter

class StaffLines:
  HOUGH_LORES_THETA = np.pi / 500
  HOUGH_HIRES_THETA = np.pi / 2500
  HOUGH_NUM_THETA   = 5
  def __init__(self, page):
    self.page = page
    # Hough transform with low theta resolution
    # (we will later build a Hough transform with a higher resolution
    # centered on each peak in this image)
    self.H = hough.hough_line(self.page.im != 0,
                 rho_res=self.page.staff_thick,
                 ts=np.linspace(-self.HOUGH_LORES_THETA*self.HOUGH_NUM_THETA,
                                 self.HOUGH_LORES_THETA*self.HOUGH_NUM_THETA,
                                2*self.HOUGH_NUM_THETA+1))

  def crop_staff_peak(self, r, t):
    """ r, t: index into self.H
        the line should be almost horizontal (t ~= 0)
        return cropped image around possible staff area, image bounds,
        and adjusted real-valued r and t
    """
    theta = (t - self.HOUGH_NUM_THETA)*self.HOUGH_LORES_THETA
    rho0 = np.double(r*self.page.staff_thick)
    b0 = rho0 / np.cos(theta) # y-intercept
    if np.cos(theta) >= 0:
      # y = (rho - x sin theta) / cos theta
      ymin = rho0 / np.cos(theta)
      ymax = (rho0 - self.page.im.shape[1] * np.sin(theta)) / np.cos(theta)
    ymin = int(np.rint(ymin)) - self.page.staff_dist*5
    ymax = int(np.rint(ymax)) + self.page.staff_dist*5 + 1
    img = self.page.im[ymin:ymax]
    rho = rho0 * (b0 - ymin) / b0
    return img, slice(ymin,ymax), rho, theta
    
  def staff_from_peak(self, r, t):
    theta0 = (t - self.HOUGH_NUM_THETA) * self.HOUGH_LORES_THETA
    # Build hi-res Hough transform centered on (r, t) and calculate
    # the corresponding peak