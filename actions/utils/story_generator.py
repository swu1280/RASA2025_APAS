def normalize_name(text):
    return text.lower().replace(" ", "_").replace(".", "").replace(",", "")

def generate_stories_yaml(paths, filename="data/stories_auto.yml"):
    story_blocks = []
    for i, path in enumerate(paths):
        if len(path) < 2:
            continue
        story_name = normalize_name("_".join(path[1:3]))[:60]
        block = f"- story: {story_name}\n  steps:\n"
        for j, step in enumerate(path[1:]):
            if j == 0:
                block += f"  - intent: {normalize_name(step)}\n"
            else:
                block += f"  - action: utter_{normalize_name(step)}\n"
        story_blocks.append(block)
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(story_blocks))
    return len(story_blocks)
