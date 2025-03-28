# actions/actions.py
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
import requests
from bs4 import BeautifulSoup

class ActionQueryDS422FromWeb(Action):
    def name(self):
        return "action_query_ds422_web"

    def run(self, dispatcher, tracker, domain):
        url = "https://www.wto.org/english/tratop_e/dispu_e/cases_e/ds422_e.htm"

        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            content = soup.find("div", {"id": "content"})

            summary = ""
            current_title = None

            for tag in content.find_all(["h3", "p", "ul"]):
                if tag.name == "h3":
                    current_title = tag.get_text(strip=True)
                    summary += f"\n\n== {current_title} ==\n"
                elif tag.name == "ul":
                    items = "\n".join(f"- {li.get_text(strip=True)}" for li in tag.find_all("li"))
                    summary += items + "\n"
                else:
                    summary += tag.get_text(strip=True) + "\n"

            dispatcher.utter_message(text="这是 DS422 的简要结构：")
            dispatcher.utter_message(text=summary[:1500] + "...\n（内容过长，仅显示部分）")

        except Exception as e:
            dispatcher.utter_message(text="读取 WTO 案件网页时出错，请稍后重试。")
            print(e)

        return []
