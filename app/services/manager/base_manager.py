import threading
from queue import Empty, Queue
from typing import Any, Callable


class TaskManager:
    """
    Manages the execution of tasks with a limit on the number of concurrent tasks.

    Attributes:
        max_concurrent_tasks (int): Maximum number of tasks to execute concurrently.
        current_tasks (int): Counter for currently running tasks.
    """

    def __init__(self, max_concurrent_tasks: int)->None:
        """
        Initializes the TaskManager.

        Args:
            max_concurrent_tasks (int): Maximum number of tasks to execute concurrently.
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.current_tasks = 0
        self.lock = threading.Lock()
        self.queue = Queue()

    def add_task(self, func: Callable, *args: Any, **kwargs: Any) ->None:
        """
        Adds a task to the manager, either executing it immediately or enqueuing it.

        Args:
            func (Callable): The function to execute.
            *args (Any): Positional arguments for the function.
            **kwargs (Any): Keyword arguments for the function.
        """
        with self.lock:
            if self.current_tasks < self.max_concurrent_tasks:
                self._log(
                    f"Executing task: {func.__name__}, current_tasks: {self.current_tasks}"  # noqa: COM812, E501
                )
                self.execute_task(func, *args, **kwargs)
            else:
                self._log(
                    f"Enqueuing task: {func.__name__}, current_tasks: {self.current_tasks}"  # noqa: COM812, E501
                )
                self.queue.put({"func": func, "args": args, "kwargs": kwargs})

    def execute_task(self, func: Callable, *args: Any, **kwargs: Any) ->None:
        """
        Executes a task in a new thread.

        Args:
            func (Callable): The function to execute.
            *args (Any): Positional arguments for the function.
            **kwargs (Any): Keyword arguments for the function.
        """
        thread = threading.Thread(
            target=self.run_task, args=(func, *args), kwargs=kwargs, daemon=True
        )
        thread.start()

    def run_task(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """
        Runs a task, handling its lifecycle within the manager.

        Args:
            func (Callable): The function to execute.
            *args (Any): Positional arguments for the function.
            **kwargs (Any): Keyword arguments for the function.
        """
        try:
            with self.lock:
                self.current_tasks += 1
            func(*args, **kwargs)
        except Exception as e:
            self._log(f"Error while executing task {func.__name__}: {e}")
        finally:
            self.task_done()

    def check_queue(self) -> None:
        """Checks the task queue and starts the next task if capacity allows."""
        with self.lock:
            if self.current_tasks < self.max_concurrent_tasks:
                try:
                    task_info = self.queue.get_nowait()
                except Empty:
                    return
                func = task_info["func"]
                args = task_info.get("args", ())
                kwargs = task_info.get("kwargs", {})
                self.execute_task(func, *args, **kwargs)

    def task_done(self)-> None:
        """Marks a task as done and checks the queue for the next task."""
        with self.lock:
            self.current_tasks -= 1
        self.check_queue()

    def _log(self, message: str)->None:
        """
        Logs a message to the console.

        Args:
            message (str): The message to log.
        """
        print(message)  # Replace with `logging.info(message)` for a production setup.
