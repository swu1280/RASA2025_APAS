# rasa/actions/actions.py

from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import Tracker
from rasa_sdk.events import SlotSet

import requests
import uuid
import os

from .utils.xmind_parser import extract_paths_from_xmind
from .utils.story_generator import generate_stories_yaml

class ActionParseUploadedXmind(Action):
    def name(self):
        return "action_parse_uploaded_xmind"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Step 1: 获取用户输入中可能存在的 URL
        user_msg = tracker.latest_message.get("text", "")
        url = self.extract_url(user_msg)

        if not url:
            dispatcher.utter_message(text="❌ 未检测到有效的 .xmind 文件链接，请提供有效的 URL。")
            return []

        # Step 2: 下载文件
        try:
            local_filename = f"files/{uuid.uuid4().hex}.xmind"
            response = requests.get(url)
            response.raise_for_status()
            with open(local_filename, "wb") as f:
                f.write(response.content)
        except Exception as e:
            dispatcher.utter_message(text=f"❌ 下载文件失败：{e}")
            return []

        # Step 3: 解析 xmind 内容，生成 stories
        try:
            paths = extract_paths_from_xmind(local_filename)
            count = generate_stories_yaml(paths)
            dispatcher.utter_message(text=f"✅ 成功解析文件，生成 {count} 条对话路径，已写入 stories_auto.yml。")
        except Exception as e:
            dispatcher.utter_message(text=f"❌ 解析 .xmind 文件失败：{e}")
        finally:
            os.remove(local_filename)  # 删除临时文件

        return []

    def extract_url(self, text):
        import re
        urls = re.findall(r"(https?://[^\s]+)", text)
        for url in urls:
            if url.endswith(".xmind"):
                return url
        return None
