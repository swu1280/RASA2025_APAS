
import subprocess
import os

def run_script(script):
    print(f"▶️ Running {script} ...")
    result = subprocess.run(["python", script], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("⚠️", result.stderr)

def train_rasa():
    print("🎯 Training Rasa model ...")
    result = subprocess.run(["rasa", "train"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("⚠️", result.stderr)


#def launch_shell():
#    print("🧠 Launching Rasa shell ...")
#    subprocess.run(["rasa", "shell"])


if __name__ == "__main__":
    run_script("utter_generator.py")
    run_script("domain_auto_updater.py")
    train_rasa()
#    launch_shell()
