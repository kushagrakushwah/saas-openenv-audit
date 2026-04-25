import requests

TASK = "task1_easy"

class AgentClient:
    def __init__(self, base_url, task=TASK):
        self.base_url = base_url
        self.task = task

    def reset(self, seed=None):
        r = requests.post(f"{self.base_url}/{self.task}/reset",
                          params={"seed": seed} if seed else {})
        r.raise_for_status()
        return r.json()["observation"]

    def step(self, action):
        r = requests.post(f"{self.base_url}/{self.task}/step",
                          json={
                              "tool": action["tool"],
                              "software_id": action.get("software_id")
                          })
        r.raise_for_status()
        d = r.json()
        return d["observation"], d["reward"], d["done"], d["info"]

    def close(self):
        pass
