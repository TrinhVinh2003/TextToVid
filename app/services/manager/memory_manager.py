from queue import Queue
from typing import Any, Dict

from app.services.manager.base_manager import TaskManager


class InMemoryTaskManager(TaskManager):
    """
    An in-memory implementation of TaskManager using Python's queue
    .Queue for task storage.
    Suitable for scenarios where task persistence is not required.
    """  # noqa: D205

    def create_queue(self) -> Queue:
        """
        Creates and returns an in-memory queue for task storage.

        Returns:
            Queue: A thread-safe queue for managing tasks.
        """
        return Queue()

    def enqueue(self, task: Dict[str, Any]) -> None:
        """
        Adds a task to the queue.

        Args:
            task (Dict[str, Any]): The task to enqueue, including the function,
            arguments, and keyword arguments.
        """
        self.queue.put(task)

    def dequeue(self) -> Dict[str, Any]:
        """
        Removes and returns the next task from the queue.

        Returns:
            Dict[str, Any]: The next task to process, including the function, arguments,
            and keyword arguments.
        """
        return self.queue.get()

    def is_queue_empty(self) -> bool:
        """
        Checks if the task queue is empty.

        Returns:
            bool: True if the queue is empty, False otherwise.
        """
        return self.queue.empty()
