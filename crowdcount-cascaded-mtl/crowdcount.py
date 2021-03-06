import sys
import time
import argparse

import cv2
import numpy as np

import ailia
# import original modules
sys.path.append('../util')
from utils import check_file_existance  # noqa: E402
from model_utils import check_and_download_models  # noqa: E402
from image_utils import load_image  # noqa: E402
import webcamera_utils  # noqa: E402


# ======================
# PARAMETERS
# ======================
WEIGHT_PATH = "crowdcount.onnx"
MODEL_PATH = "crowdcount.onnx.prototxt"
REMOTE_PATH = "https://storage.googleapis.com/ailia-models/crowd_count/"

IMAGE_PATH = 'test.jpeg'
SAVE_IMAGE_PATH = 'result.png'
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480


# ======================
# Arguemnt Parser Config
# ======================
parser = argparse.ArgumentParser(
    description='Single image crowd counting.'
)
parser.add_argument(
    '-i', '--input', metavar='IMAGEFILE_PATH',
    default=IMAGE_PATH,
    help='The input image path.'
)
parser.add_argument(
    '-v', '--video', metavar='VIDEO',
    default=None,
    help='The input video path. ' +
         'If the VIDEO argument is set to 0, the webcam input will be used.'
)
parser.add_argument(
    '-s', '--savepath', metavar='SAVE_PATH',
    default=SAVE_IMAGE_PATH,
    help='Save path for the result of the model.'
)
parser.add_argument(
    '-b', '--benchmark',
    action='store_true',
    help='Running the inference on the same input 5 times ' +
         'to measure execution performance. (Cannot be used in video mode)'
)
args = parser.parse_args()


# ======================
# Main functions
# ======================
def estimate_from_image():
    # prepare input data
    org_img = load_image(
        args.input,
        (IMAGE_HEIGHT, IMAGE_WIDTH),
        normalize_type='None'
    )
    input_data = load_image(
        args.input,
        (IMAGE_HEIGHT, IMAGE_WIDTH),
        rgb=False,
        normalize_type='None',
        gen_input_ailia=True
    )

    # net initialize
    env_id = ailia.get_gpu_environment_id()
    print(env_id)
    net = ailia.Net(MODEL_PATH, WEIGHT_PATH, env_id=env_id)

    # inference
    if args.benchmark:
        print('BENCHMARK mode')
        for i in range(5):
            start = int(round(time.time() * 1000))
            preds_ailia = net.predict(input_data)
            end = int(round(time.time() * 1000))
            print("\tailia processing time {} ms".format(end - start))
    else:
        preds_ailia = net.predict(input_data)

    # estimated crowd count
    et_count = int(np.sum(preds_ailia))

    # density map
    density_map = (255 * preds_ailia / np.max(preds_ailia))[0][0]
    density_map = cv2.resize(density_map, (IMAGE_WIDTH, IMAGE_HEIGHT))
    heatmap = cv2.applyColorMap(density_map.astype(np.uint8), cv2.COLORMAP_JET)
    cv2.putText(
        heatmap,
        f'Est Count: {et_count}',
        (40, 440),  # position
        cv2.FONT_HERSHEY_SIMPLEX,  # font
        0.8,  # fontscale
        (255, 255, 255),  # color
        2  # thickness
    )

    res_img = np.hstack((org_img, heatmap))
    cv2.imwrite(args.savepath, res_img)
    print('Script finished successfully.')


def estimate_from_video():
    # net initialize
    env_id = ailia.get_gpu_environment_id()
    print(env_id)
    net = ailia.Net(MODEL_PATH, WEIGHT_PATH, env_id=env_id)

    if args.video == '0':
        print('[INFO] Webcam mode is activated')
        capture = cv2.VideoCapture(0)
        if not capture.isOpened():
            print("[ERROR] webcamera not found")
            sys.exit(1)
    else:
        if check_file_existance(args.video):
            capture = cv2.VideoCapture(args.video)

    # create video writer if savepath is specified as video format
    if args.savepath != SAVE_IMAGE_PATH:
        f_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        f_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        save_h, save_w = webcamera_utils.calc_adjust_fsize(
            f_h, f_w, IMAGE_HEIGHT, IMAGE_WIDTH
        )
        # save_w * 2: we stack source frame and estimated heatmap
        writer = webcamera_utils.get_writer(args.savepath, save_h, save_w * 2)
    else:
        writer = None

    while(True):
        ret, frame = capture.read()
        if (cv2.waitKey(1) & 0xFF == ord('q')) or not ret:
            break

        input_image, input_data = webcamera_utils.preprocess_frame(
            frame,
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            data_rgb=False,
            normalize_type='None'
        )

        # inference
        preds_ailia = net.predict(input_data)

        # estimated crowd count
        et_count = int(np.sum(preds_ailia))

        # density map
        density_map = (255 * preds_ailia / np.max(preds_ailia))[0][0]
        density_map = cv2.resize(
            density_map,
            (input_image.shape[1], input_image.shape[0])
        )
        heatmap = cv2.applyColorMap(
            density_map.astype(np.uint8), cv2.COLORMAP_JET
        )
        cv2.putText(
            heatmap,
            f'Est Count: {et_count}',
            (40, 440),  # position
            cv2.FONT_HERSHEY_SIMPLEX,  # font
            0.8,  # fontscale
            (255, 255, 255),  # color
            2  # thickness
        )
        res_img = np.hstack((input_image, heatmap))
        cv2.imshow('frame', res_img)

        # save results
        if writer is not None:
            writer.write(res_img)

    capture.release()
    cv2.destroyAllWindows()
    print('Script finished successfully.')


def main():
    # model files check and download
    check_and_download_models(WEIGHT_PATH, MODEL_PATH, REMOTE_PATH)

    if args.video is not None:
        # video mode
        estimate_from_video()
    else:
        # image mode
        estimate_from_image()


if __name__ == "__main__":
    main()
