from ...gpu import *
import logging

prg = build_program('staff_paths')

path_point = np.dtype([('cost', np.float32), ('prev', np.int32)])
def paths(page, img=None, num_workers=512, scale=2.0):
    if img is None:
        img = page.img
    page.paths = thr.empty_like(Type(np.int32,
                                     (int(img.shape[0]/scale),
                                      int(img.shape[1]*8/scale), 2)))
    page.paths.fill(0)
    prg.staff_paths(img,
                    np.int32(img.shape[1]),
                    np.int32(img.shape[0]),
                    np.int32(page.staff_thick),
                    np.float32(2.0),
                    page.paths,
                    np.int32(page.paths.shape[1]),
                    np.int32(page.paths.shape[0]),
                    global_size=(num_workers,), local_size=(num_workers,))
    return page.paths

def stable_paths(page, img=None):
    if img is None:
        img = page.img
    if not hasattr(page, 'paths'):
        paths(page, img)
    h = page.paths.shape[0]
    w = page.paths.shape[1]
    path_end = thr.empty_like(Type(np.int32, h))
    prg.find_stable_paths(page.paths,
                          np.int32(w),
                          path_end,
                          global_size=(h,), local_size=(512,))
    path_end = path_end.get()
    stable_path_end = path_end[path_end >= 0]
    if not len(stable_path_end):
        return np.zeros((0, w), int)
    stable_path_end = thr.to_device(stable_path_end.astype(np.int32))
    path_list = thr.empty_like(Type(np.int32, (len(stable_path_end), w)))
    prg.extract_stable_paths(page.paths,
                             np.int32(w),
                             stable_path_end,
                             path_list,
                             global_size=(len(stable_path_end),),
                             local_size=(1,))
    return path_list

def stable_paths_py(page, img=None):
    if img is None:
        img = page.img
    if not hasattr(page, 'paths'):
        paths(page, img)
    
    starting_points = [[] for i in xrange(page.paths.shape[1])]
    # Trace each endpoint back along its shortest path
    x = page.paths.shape[1] - 1
    path_ys = np.arange(page.paths.shape[0])
    paths_py = page.paths.get().view(path_point).reshape(page.paths.shape[:2])
    while x > 0:
        path_ys = paths_py[path_ys, x]['prev']
        x -= 1
    for start_y, end_y, cost in zip(path_ys,
                                    xrange(paths_py.shape[0]),
                                    paths_py[:,-1]['cost']):
        starting_points[start_y].append((cost, end_y))
    stable_paths = []
    for from_y0 in starting_points:
        if not from_y0:
            continue
        cost_to_path = dict(from_y0)
        path_y = cost_to_path[min(cost_to_path)] # end y of min cost path
        path = []
        for x in xrange(paths_py.shape[1]-1, -1, -1):
            path.append(path_y)
            path_y = paths_py[path_y, x]['prev']
        stable_paths.append(list(reversed(path)))
    return stable_paths

def validate_and_remove_paths(page, img, stable_paths):
    pixel_sum = thr.empty_like(Type(np.int32, len(stable_paths)))
    pixel_sum.fill(0)
    prg.remove_paths(img,
                     np.int32(img.shape[1]),
                     np.int32(img.shape[0]),
                     stable_paths,
                     np.int32(stable_paths.shape[1]),
                     np.int32(2), # XXX
                     pixel_sum,
                     global_size=(len(stable_paths),), local_size=(1,))
    return pixel_sum

def all_staff_paths(page):
    img = page.img.copy()
    all_paths = []
    threshold = None
    while True:
        if hasattr(page, 'paths'):
            del page.paths
        paths = stable_paths(page, img)
        sums = validate_and_remove_paths(page, img, paths).get()
        if threshold is None:
            threshold = int(np.median(sums) * 0.8)
            all_paths.append(paths.get())
        else:
            valid = sums >= threshold
            if not valid.any():
                return np.concatenate(all_paths) * 2 # XXX: path_scale
            else:
                all_paths.append(paths.get()[valid])


def staves(page):
    staff_paths = all_staff_paths(page)
    # Sort the path y's in each column, which prevents paths crossing
    staff_paths = np.sort(staff_paths, axis=0)

    staves = []
    cur_staff = []
    last_line_pos = None
    for line in staff_paths:
        line_pos = np.median(line)
        if last_line_pos is None or line_pos - last_line_pos < page.staff_dist*2:
            cur_staff.append(line)
        elif cur_staff:
            # end of staff
            if len(cur_staff) != 5:
                logging.info('Throwing out staff with %d lines' % len(cur_staff))
            else:
                center_pos = np.median(cur_staff[2])
                staves.append([0, page.orig_size[1], center_pos,center_pos])
            cur_staff = [line]
        last_line_pos = line_pos
    if cur_staff:
        # end of staff
        if len(cur_staff) != 5:
            logging.info('Throwing out staff with %d lines' % len(cur_staff))
        else:
            center_pos = np.median(cur_staff[2])
            staves.append([0, page.orig_size[1], center_pos,center_pos])
    page.staves = np.array(staves, int)
    return page.staves
