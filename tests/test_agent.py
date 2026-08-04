import asyncio
import unittest

from reports_wagent.agent import AgentService


class AgentServiceCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_stops_active_task(self) -> None:
        service = AgentService.__new__(AgentService)
        task = asyncio.create_task(asyncio.Event().wait())
        service._active_tasks = {"thread": task}

        self.assertTrue(service.cancel("thread"))
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_cancel_returns_false_without_active_task(self) -> None:
        service = AgentService.__new__(AgentService)
        service._active_tasks = {}

        self.assertFalse(service.cancel("thread"))


if __name__ == "__main__":
    unittest.main()
