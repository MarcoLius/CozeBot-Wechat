import os
from common.log import logger
from config import conf
from cozepy import (
    Coze,
    TokenAuth,
    setup_logging
)
from bridge.reply import Reply, ReplyType
import datetime
import random
from voice.voice import Voice
class CozeVoice(Voice):

    def __init__(self):
        self.coze_api_token = conf().get("coze_api_key")
        self.coze_api_base = conf().get("coze_api_base")
        self.coze_voice_id = conf().get("coze_voice_id")
        self.coze = Coze(auth=TokenAuth(token=self.coze_api_token), base_url=self.coze_api_base)
        
    def textToVoice(self, text):

        logger.debug("[COZE VOICE] text={}".format(text))
        
        speech_file = self.coze.audio.speech.create(input=text, voice_id=self.coze_voice_id)
        file_path = "tmp/" + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(0, 1000)) + ".mp3"
        if speech_file:
            speech_file.write_to_file(file_path)

            logger.info(f"Create speech of voice: {self.coze_voice_id} to file: {file_path}")
            return Reply(ReplyType.VOICE, file_path)
        else:
            logger.error(f"Failed to create speech for voice: {self.coze_voice_id}")
            return Reply(ReplyType.ERROR, "我暂时还无法听清您的语音，请稍后再试吧~")

    def voiceToText(self, voiceFile):
        result=self.coze.audio.transcriptions.create(file=voiceFile)
        text=result.text
        logger.info(f"Transcriptions of voice: {voiceFile} to text: {text}")
        return Reply(ReplyType.TEXT, text)