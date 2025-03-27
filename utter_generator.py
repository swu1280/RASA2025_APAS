
import yaml
import re

def normalize(text):
    return text.replace("_", " ").capitalize()

def extract_utterances_from_stories(story_file="data/stories_auto.yml"):
    with open(story_file, "r", encoding="utf-8") as f:
        content = f.read()

    return sorted(set(re.findall(r"utter_[a-zA-Z0-9_]+", content)))

def generate_responses_yaml(utterances, output_file="data/responses_auto.yml"):
    responses = {"responses": {}}
    for utter in utterances:
        responses["responses"][utter] = [{"text": normalize(utter)}]

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(responses, f, allow_unicode=True)

    return output_file, len(utterances)

if __name__ == "__main__":
    utterances = extract_utterances_from_stories()
    output_file, count = generate_responses_yaml(utterances)
    print(f"✅ 已生成 {count} 个响应，写入 {output_file}")
