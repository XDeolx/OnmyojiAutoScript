"""Locate scrollable wanted-quest rows independently of their screen slot."""
from copy import copy
import re
import cv2
import numpy as np

from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from tasks.WantedQuests.assets import WantedQuestsAssets
from tasks.WantedQuests.config import WQInfo, WQType

LABELS = {
    WQType.CHALLENGE: RuleImage((640, 286, 110, 29), (630, 270, 135, 300), 'Template matching', .8, './tasks/WantedQuests/wq/route_challenge.png'),
    WQType.EXPLORE: RuleImage((640, 361, 65, 29), (630, 270, 135, 300), 'Template matching', .8, './tasks/WantedQuests/wq/route_explore.png'),
    WQType.SECRET: RuleImage((640, 437, 65, 29), (630, 270, 135, 300), 'Template matching', .8, './tasks/WantedQuests/wq/route_secret.png'),
}

YOKAI_LABEL = RuleImage((640, 362, 65, 29), (630, 270, 135, 300),
                        'Template matching', .8, './tasks/WantedQuests/wq/route_yokai.png')

def ignored_route_label(label):
    """Classify only the isolated category badge, never the monster name."""
    label = ''.join(label.split()).strip('[]［］【】()（）:：.,，。')
    return label in ('御魂', '妖气')

def read_route_label(image, center):
    # The badge ends at x=709. Including the destination caused OCR to drop
    # 妖 and concatenate 气 with the monster name (气骨女 / 气跳跳).
    crop = image[center-23:center+23, 632:711]
    scaled = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    roi = (0, 0, scaled.shape[1], scaled.shape[0])
    return RuleOcr(roi=roi, area=roi, mode='Single', method='Default',
                   keyword='', name='wq_route_kind').ocr(scaled)

def locate_rows(image):
    template = WantedQuestsAssets.I_GOTO_1.image
    scores = cv2.matchTemplate(image[270:572, 1040:1165], template, cv2.TM_CCOEFF_NORMED)
    centers = []
    while True:
        _, value, _, (x, y) = cv2.minMaxLoc(scores)
        if value < .85:
            break
        centers.append(270 + y + template.shape[0] // 2)
        scores[max(0, y-40):y+41, :] = -1
    return sorted(centers)

def read_routes(image):
    routes, failed = [], False
    centers = locate_rows(image)
    for center in centers:
        label_image = image[center-23:center+23, 630:760]
        if cv2.minMaxLoc(cv2.matchTemplate(label_image, YOKAI_LABEL.image,
                                          cv2.TM_CCOEFF_NORMED))[1] >= .8:
            continue
        matches = []
        for kind, rule in LABELS.items():
            score = cv2.minMaxLoc(cv2.matchTemplate(label_image, rule.image, cv2.TM_CCOEFF_NORMED))[1]
            if score >= .8:
                matches.append((score, kind))
        kind = max(matches)[1] if matches else None
        if kind is None and ignored_route_label(read_route_label(image, center)):
            continue
        left = 758 if kind == WQType.CHALLENGE else 714
        crop = image[center-14:center+14, left:1025]
        scaled = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        roi = (0, 0, scaled.shape[1], scaled.shape[0])
        raw = RuleOcr(roi=roi, area=roi, mode='Single', method='Default', keyword='', name='wq_route_detail').ocr(scaled)
        text = ''.join(raw.split()).replace('：', ':')
        number = re.search(r'[数教]量[:：](\d+)', text)
        if kind is None or number is None or int(number[1]) <= 0:
            failed = True
            continue
        # Preserve the original exclusion of high secret floors.
        if kind == WQType.SECRET and re.search(r'[·.](捌|玖|拾|番外)', text):
            continue
        button = copy(WantedQuestsAssets.I_GOTO_1)
        button.roi_front = [1065, center-15, 75, 31]
        button.roi_back = (1040, center-25, 125, 50)
        destination = re.split(r'[（(]?[数教]量', text)[0]
        routes.append(WQInfo(kind, int(number[1]), button, destination))
    return routes, failed or not centers

def list_fingerprint(image):
    return image[270:572, 630:1025].copy()

def same_list(before, after):
    return float(np.mean(np.abs(before.astype(np.float32)-after.astype(np.float32)))) < 1.5
