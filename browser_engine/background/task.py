import threading


class Task:
    def __init__(self, task_code, *args):
        self.task_code = task_code
        self.args = args

    def run(self):
        self.task_code(*self.args)
        self.task_code = None
        self.args = None

class TaskRunner:
    def __init__(self, tab):
        self.tab = tab
        self.tasks = []
        self.condition = threading.Condition()

    def schedule_task(self, task):
        with self.condition:
            self.tasks.append(task)
            self.condition.notify_all()

    def run(self):
        task = None
        with self.condition:
            if self.tasks:
                task = self.tasks.pop(0)

        if task:
            task.run()