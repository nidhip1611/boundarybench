"""Collects printed results so every experiment leaves a summary.txt next to its tables."""
import datetime
import os
import subprocess


class Report:
    def __init__(self, name, folder):
        self.name, self.folder, self.lines = name, folder, []
        try:
            commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                    cwd=os.path.dirname(__file__)).stdout.strip()
        except Exception:
            commit = "unknown"
        self.say(f"# {name} | run {datetime.datetime.now():%Y-%m-%d %H:%M} | commit {commit or 'unknown'}")

    def say(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.lines.append(s)

    def table(self, title, df, index=True):
        self.say(f"\n{title}")
        self.say(df.to_string(index=index))

    def save(self):
        path = os.path.join(self.folder, "summary.txt")
        with open(path, "w") as f:
            f.write("\n".join(self.lines) + "\n")
        print(f"\nsummary written to {path}")
