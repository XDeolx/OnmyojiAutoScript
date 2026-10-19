from time import sleep

from module.atom.image import RuleImage
from module.exception import GameStuckError
from module.logger import logger


class AudioDownloadPrompt:
    I_AUDIO_DOWNLOAD_TITLE = RuleImage(
        roi_front=(536,175,292,41), roi_back=(536,175,292,41), threshold=0.85,
        method="Template matching", file="./tasks/SoulsTidy/simple/audio_download_title.png")
    I_AUDIO_DOWNLOAD_CANCEL = RuleImage(
        roi_front=(396,479,180,64), roi_back=(396,479,180,64), threshold=0.85,
        method="Template matching", file="./tasks/SoulsTidy/simple/audio_download_cancel.png")

    def dismiss_audio_download(self):
        for attempt in range(4):
            if not self.appear(self.I_AUDIO_DOWNLOAD_TITLE):
                return
            if attempt == 3 or not self.appear(self.I_AUDIO_DOWNLOAD_CANCEL):
                raise GameStuckError('Shikigami audio download prompt could not be dismissed')
            logger.info('Shikigami records: cancel optional audio download')
            self.click(self.I_AUDIO_DOWNLOAD_CANCEL)
            sleep(0.8)
            self.screenshot()
