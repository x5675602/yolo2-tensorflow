import tensorflow as tf
import numpy as np
import cv2
import csv

csv_path = './data.csv'  # 此文件给出了用于转换为tfrecord文件的图片地址
anchors_path = './anchors.txt'  # 读写anchor大小及个数的文件
tfrecord_path = './data.tfrecord'  # 用于保存tfrecord文件的地址

net_scale = 32
grid_w, grid_h = 18, 10  # 分别表示在宽度和高度尺度上的网格单元个数
n_classes = 6  # 此变量没有使用
iou_th = 0.7
in_w, in_h = grid_w*net_scale, grid_h*net_scale

def read_anchors_file(file_path):

    anchors = []
    with open(file_path, 'r') as file:
        for line in file.read().splitlines():
            anchors.append(map(float,line.split()))

    return np.array(anchors)

def iou_wh(r1, r2):

    min_w = min(r1[0],r2[0])
    min_h = min(r1[1],r2[1])
    area_r1 = r1[0]*r1[1]
    area_r2 = r2[0]*r2[1]
		
    intersect = min_w * min_h		
    union = area_r1 + area_r2 - intersect

    return intersect/union
	
def get_grid_cell(roi, raw_w, raw_h, grid_w, grid_h):

    x_center = roi[0] + roi[2]/2.0
    y_center = roi[1] + roi[3]/2.0
    grid_x = int(x_center/float(raw_w)*float(grid_w))
    grid_y = int(y_center/float(raw_h)*float(grid_h))
		
    return grid_x, grid_y

def get_active_anchors(roi, anchors):
    '''若roi与anchor之间的roi小于阈值，则anchor为激活状态
    '''
    indxs = []
    iou_max, index_max = 0, 0
    for i,a in enumerate(anchors):
        iou = iou_wh(roi[2:], a)
        if iou>iou_th:
            indxs.append(i)
        if iou > iou_max:
            iou_max, index_max = iou, i

    if len(indxs) == 0:
        indxs.append(index_max)

    return indxs

def read_csv_file(filename):
    '''
    args:
        filename: 此文件保存着用于转换为tfrecord文件的图片地址
    '''
    filenames = []
    rois = []
    classes = []
    with open(filename) as csvfile:
        i=['filename', 'rois', 'classes']
        csvdata = csv.DictReader(csvfile)
        for row in csvdata:
            filenames.append(row['filename'])  # 图片地址
            rois.append(row['rois'])  # 限位框(左上方的坐标以及宽度和高度)
            classes.append(row['classes'])  # 该图片中，对应限位框内的对象所属于的类别

    return filenames, rois, classes

def roi2label(roi, anchor, raw_w, raw_h, grid_w, grid_h):
    '''
    args: 
        roi:    限位框的左上方的坐标以及它的宽度和高度
        anchor: anchor box的宽度和高度
        raw_w:  图片原始的宽度
        raw_h:  图片原始的高度
        grid_w: 在宽度上的网格单元个数
        grid_h: 在高度上的网格单元个数
    '''
    # 计算限位框的中心
    x_center = roi[0] + roi[2] / 2.0
    y_center = roi[1] + roi[3] / 2.0

    grid_x = x_center / float(raw_w) * float(grid_w)
    grid_y = y_center / float(raw_h) * float(grid_h)

    grid_x_offset = grid_x - int(grid_x)
    grid_y_offset = grid_y - int(grid_y)

    roi_w_scale = roi[2] / anchor[0]
    roi_h_scale = roi[3] / anchor[1]

    label=[grid_x_offset, grid_y_offset, roi_w_scale, roi_h_scale]

    return label

def onehot(idx, num):
    '''没有使用
    '''
    ret = np.zeros([num], dtype=np.float32)
    ret[idx] = 1.0
	
    return ret

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def make_record():
    '''由图像集制作tfrecored文件
    '''

    anchors = read_anchors_file(anchors_path)
    n_anchors = np.shape(anchors)[0]
    csv_filenames, csv_rois, csv_classes = read_csv_file(csv_path)

    with tf.python_io.TFRecordWriter(tfrecord_path) as writer:
        for filename, rois, classes in zip(csv_filenames, csv_rois, csv_classes):
            rois = np.array(eval(rois), dtype=np.float32)
            classes = np.array(eval(classes), dtype=np.int32)

            img = cv2.imread(filename)
            raw_h = np.shape(img)[0]
            raw_w = np.shape(img)[1]
            img = cv2.resize(img, (in_w, in_h))

            label = np.zeros([grid_h, grid_w, n_anchors, 6], dtype=np.float32)

            for roi, cls in zip(rois,classes):
                active_indxs = get_active_anchors(roi, anchors)
                grid_x, grid_y = get_grid_cell(roi, raw_w, raw_h, grid_w, grid_h)
                for active_indx in active_indxs:
                    anchor_label = roi2label(roi, anchors[active_indx], raw_w, raw_h, grid_w, grid_h)		
                    label[grid_y, grid_x, active_indx] = np.concatenate((anchor_label, [cls], [1.0]))
                image_raw = img.tostring()
                label_raw = label.tostring()
		
                example = tf.train.Example(features=tf.train.Features(feature={
                        'label': tf.train.Feature(bytes_list=tf.train.BytesList(value=[label_raw])),
                        'image': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image_raw]))}))

                writer.write(example.SerializeToString())

if __name__ == "__main__":
    make_record()
