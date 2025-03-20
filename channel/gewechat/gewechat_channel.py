import os
import time
from urllib.parse import urlparse
import socket
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
import uvicorn

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.gewechat.gewechat_message import GeWeChatMessage
from common.log import logger
from common.singleton import singleton
from common.tmp_dir import TmpDir
from config import conf, save_config
from lib.gewechat import GewechatClient
from voice.audio_convert import mp3_to_silk
import uuid

MAX_UTF8_LEN = 2048

@singleton
class GeWeChatChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.base_url = conf().get("gewechat_base_url")
        if not self.base_url:
            logger.error("[gewechat] base_url is not set")
            return
        self.token = conf().get("gewechat_token")
        self.client = GewechatClient(self.base_url, self.token)

        # 如果token为空，尝试获取token
        if not self.token:
            logger.warning("[gewechat] token is not set，trying to get token")
            token_resp = self.client.get_token()
            # {'ret': 200, 'msg': '执行成功', 'data': 'tokenxxx'}
            if token_resp.get("ret") != 200:
                logger.error(f"[gewechat] get token failed: {token_resp}")
                return
            self.token = token_resp.get("data")
            conf().set("gewechat_token", self.token)
            save_config()
            logger.info(f"[gewechat] new token saved: {self.token}")
            self.client = GewechatClient(self.base_url, self.token)

        self.app_id = conf().get("gewechat_app_id")
        if not self.app_id:
            logger.warning("[gewechat] app_id is not set，trying to get new app_id when login")

        self.download_url = conf().get("gewechat_download_url")
        if not self.download_url:
            logger.warning("[gewechat] download_url is not set, unable to download image")

        logger.info(f"[gewechat] init: base_url: {self.base_url}, token: {self.token}, app_id: {self.app_id}, download_url: {self.download_url}")

        # 添加FastAPI应用实例
        self.fastapi_app = FastAPI()
        # 配置静态文件（为后续网页功能预留）
        # static_dir = "static"
        # if os.path.exists(static_dir) and os.path.isdir(static_dir):
        #     self.fastapi_app.mount("/static", StaticFiles(directory=static_dir), name="static")
        # else:
        #     logger.warning(f"[gewechat] 静态文件目录 {static_dir} 不存在，跳过挂载")

    def startup(self):
        # 如果app_id为空或登录后获取到新的app_id，保存配置
        app_id, error_msg = self.client.login(self.app_id)
        if error_msg:
            logger.error(f"[gewechat] login failed: {error_msg}")
            return

        # 如果原来的self.app_id为空或登录后获取到新的app_id，保存配置
        if not self.app_id or self.app_id != app_id:
            conf().set("gewechat_app_id", app_id)
            save_config()
            logger.info(f"[gewechat] new app_id saved: {app_id}")
            self.app_id = app_id

        # 获取本机实际IP地址（需确保服务器有公网可达的IP）
        # def get_local_ip():
        #     try:
        #         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #         s.connect(('8.8.8.8', 80))
        #         ip = s.getsockname()[0]
        #         s.close()
        #         return ip
        #     except:
        #         return '0.0.0.0'

        # # 自动生成正确的回调地址
        # local_ip = get_local_ip()
        # port = 9919  # 使用配置的端口或默认端口
        callback_url = conf().get("gewechat_callback_url")
        logger.info(f"[gewechat] 设置回调地址: {callback_url}")
        # 新FastAPI路由配置
        parsed_url = urlparse(callback_url)
        port = parsed_url.port
        logger.info(f"[gewechat] 启动FastAPI服务器: {callback_url}, 使用端口 {port}")


        # 注册路由
        @self.fastapi_app.get(parsed_url.path)
        async def handle_get(request: Request):
            return await Query().GET(request)
            
        @self.fastapi_app.post(parsed_url.path)
        async def handle_post(request: Request):
            return await Query().POST(request)

        # 启动服务器
        config = uvicorn.Config(
            app=self.fastapi_app,
            host="0.0.0.0",
            port=port,
            log_config=None
        )
        self.server = uvicorn.Server(config)
        
        # 将服务器启动移到新线程
        import threading
        server_thread = threading.Thread(target=self.server.run, daemon=True)
        server_thread.start()
        
        #设置gewechat_callback_url
        time.sleep(3)
        try:
            data = self.client.set_callback(self.token, callback_url)
            logger.info(f"[gewechat] 设置回调地址: {data}")
            if isinstance(data, dict) and data.get("ret") == 200:
                logger.info(f"[gewechat] 设置回调地址成功: {callback_url}")
            else:
                logger.error(f"[gewechat] 设置回调地址失败: {data}")
                return
        except Exception as e:
            logger.error(f"[gewechat] 设置回调地址时发生错误: {str(e)}")
            return
    def send(self, reply: Reply, context: Context):
        receiver = context["receiver"]
        gewechat_message = context.get("msg")
        if reply.type in [ReplyType.TEXT, ReplyType.ERROR, ReplyType.INFO]:
            reply_text = reply.content
            ats = ""
            if gewechat_message and gewechat_message.is_group:
                ats = gewechat_message.actual_user_id
            self.client.post_text(self.app_id, receiver, reply_text, ats)
            logger.info("[gewechat] Do send text to {}: {}".format(receiver, reply_text))
        elif reply.type == ReplyType.VOICE:
            try:
                content = reply.content
                if content.endswith('.mp3'):
                    # 如果是mp3文件，转换为silk格式
                    silk_path = os.path.splitext(content)[0] + '.silk'
                    duration = mp3_to_silk(content, silk_path)
                    voice_duration = min(duration*1000, 60000)
                    callback_url = conf().get("gewechat_callback_url")
                    silk_url = callback_url + "?file=" + silk_path
                    self.client.post_voice(app_id=self.app_id, to_wxid=receiver, voice_url=silk_url, voice_duration=voice_duration)
                    logger.info(f"[gewechat] 发送语音给 {receiver}: {silk_url}, 时长: {voice_duration}秒")
                    return
                else:
                    logger.error(f"[gewechat] voice file is not mp3, path: {content}, only support mp3")
            except Exception as e:
                logger.error(f"[gewechat] send voice failed: {e}")
        elif reply.type == ReplyType.IMAGE_URL:
            img_url = reply.content
            self.client.post_image(self.app_id, receiver, img_url)
            logger.info("[gewechat] sendImage url={}, receiver={}".format(img_url, receiver))
        elif reply.type == ReplyType.IMAGE:
            image_storage = reply.content
            image_storage.seek(0)
            # Save image to tmp directory
            img_data = image_storage.read()
            img_file_name = f"img_{str(uuid.uuid4())}.png"
            img_file_path = TmpDir().path() + img_file_name
            with open(img_file_path, "wb") as f:
                f.write(img_data)
            # Construct callback URL
            callback_url = conf().get("gewechat_callback_url")
            img_url = callback_url + "?file=" + img_file_path
            self.client.post_image(self.app_id, receiver, img_url)
            logger.info("[gewechat] sendImage, receiver={}, url={}".format(receiver, img_url))
        elif reply.type == ReplyType.LINK:
            # 从reply.content字典获取参数
            title = reply.content.get("title")
            desc = reply.content.get("desc")
            link_url = reply.content.get("link_url")
            thumb_url = reply.content.get("thumb_url")
        
            thumb_url = thumb_url or "https://lf-flow-web-cdn.doubao.com/obj/flow-doubao/doubao/logo-doubao-overflow.png"
            # 执行发送
            self.client.post_link(
                app_id=self.app_id,
                to_wxid=receiver,
                title=title,
                desc=desc,
                link_url=link_url,
                thumb_url=thumb_url
            )
            logger.info("[gewechat] sendLink, receiver={}, title={}, desc={}".format(receiver, title, desc))


class Query:
    async def GET(self, request: Request):
        file_path = request.query_params.get("file", "")
        test = request.query_params.get("test", "")
        
        if test == "1":
            logger.info("[gewechat] 收到连通性测试请求")
            return PlainTextResponse("OK")
            
        if file_path:
            # 保留原有的路径安全检查逻辑
            clean_path = os.path.abspath(file_path)
            tmp_dir = os.path.abspath("tmp")
            
            if not clean_path.startswith(tmp_dir):
                logger.error(f"[gewechat] Forbidden access to file outside tmp directory: file_path={file_path}, clean_path={clean_path}, tmp_dir={tmp_dir}")
                raise HTTPException(status_code=403)
                
            if os.path.exists(clean_path):
                return FileResponse(clean_path)
            else:
                logger.error(f"[gewechat] File not found: {clean_path}")
                raise HTTPException(status_code=404)
                
        return PlainTextResponse("gewechat callback server is running")

    async def POST(self, request: Request):
        channel = GeWeChatChannel()
        data = await request.json()
        logger.debug("[gewechat] receive data: {}".format(data))
        
        # gewechat服务发送的回调测试消息
        if isinstance(data, dict) and 'testMsg' in data and 'token' in data:
            logger.debug(f"[gewechat] 收到gewechat服务发送的回调测试消息")
            return "success"

        gewechat_msg = GeWeChatMessage(data, channel.client)
        
        # 微信客户端的状态同步消息
        if gewechat_msg.ctype == ContextType.STATUS_SYNC:
            logger.debug(f"[gewechat] ignore status sync message: {gewechat_msg.content}")
            return "success"

        # 忽略非用户消息（如公众号、系统通知等）
        if gewechat_msg.ctype == ContextType.NON_USER_MSG:
            logger.debug(f"[gewechat] ignore non-user message from {gewechat_msg.from_user_id}: {gewechat_msg.content}")
            return "success"

        # 忽略来自自己的消息
        if gewechat_msg.my_msg:
            logger.debug(f"[gewechat] ignore message from myself: {gewechat_msg.actual_user_id}: {gewechat_msg.content}")
            return "success"

        # 忽略过期的消息
        if int(gewechat_msg.create_time) < int(time.time()) - 60 * 5: # 跳过5分钟前的历史消息
            logger.debug(f"[gewechat] ignore expired message from {gewechat_msg.actual_user_id}: {gewechat_msg.content}")
            return "success"

        context = channel._compose_context(
            gewechat_msg.ctype,
            gewechat_msg.content,
            isgroup=gewechat_msg.is_group,
            msg=gewechat_msg,
        )
        if context:
            channel.produce(context)
        return "success"