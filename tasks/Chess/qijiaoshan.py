# This Python file uses the following encoding: utf-8

"""百鬼棋局“七角山”阵容及运营策略。

图片仍统一存放在 ``tasks/Chess/shikigami``。本文件只声明七角山需要
使用哪些通用式神资源；后续新增阵容时可按相同结构建立独立策略模块。
"""


QIJIAOSHAN = {
    'key': 'qijiaoshan',
    'display_name': '七角山',
    'shikigami': {
        'kaoru': {
            'display_name': '薰',
            'position': 1,
            'hand_images': ('c_kaoru.png',),
            'shop_images': ('c_kaoru_m.png',),
        },
        'hakulo': {
            'display_name': '白狼',
            'position': 2,
            'hand_images': ('c_hakulo.png',),
            'shop_images': ('c_hakulo_m.png',),
        },
        'yushanjin': {
            'display_name': '御馔津',
            'position': 3,
            'hand_images': ('c_yushanjin.png',),
            'shop_images': ('c_yushanjin_m.png',),
        },
        'komatsu': {
            'display_name': '小松丸',
            'position': 4,
            'hand_images': ('c_komatsu.png',),
            'shop_images': ('c_komatsu_m.png',),
        },
        'ichimokuren': {
            'display_name': '一目连',
            'position': 5,
            'hand_images': ('c_ichimokuren.png',),
            'shop_images': ('c_ichimokuren_m.png',),
        },
        'shishio': {
            'display_name': '寻森小鹿男',
            'position': 6,
            'hand_images': ('c_shishio.png',),
            'shop_images': ('c_shishio_m.png',),
        },
        'kasu': {
            'display_name': '萤草',
            'position': 7,
            'hand_images': ('c_kasu.png',),
            'shop_images': ('c_kasu_m.png',),
        },
        'yamakaze': {
            'display_name': '山风',
            'position': 8,
            'hand_images': ('c_yamakaze.png',),
            'shop_images': ('c_yamakaze_m.png',),
        },
        'hakuzosu': {
            'display_name': '梦山白藏主',
            'position': 9,
            'hand_images': ('c_hakuzosu.png',),
            'shop_images': ('c_hakuzosu_m.png',),
        },
    },
    # 阵容专属伴生卡仍使用通用“御魂类拖放”接口处理。
    'special_hand_cards': {
        'hakuzosu_protect': {
            'display_name': '守护之印',
            'images': ('c_hakuzosu_protect.png',),
            'action': 'equip_soul',
            'target_position': 1,
        },
    },
    'economy': {
        'pre_level_8_reserve': 44,
        'level_8_reserve': 25,
        'level_9_reserve': 0,
    },
}
