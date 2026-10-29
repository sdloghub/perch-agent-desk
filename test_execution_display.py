import unittest
from execution_display import ExecutionDisplay
from harness_bridge import render_execution
class DisplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_coarse_status(self):
        events=[]
        async def emit(e):events.append(e)
        d=ExecutionDisplay(emit,'test')
        await d.show('模型进度说明','private reasoning')
        await d.show('调用工具 · secret_tool',{'password':'secret'})
        await d.show('调用工具 · second',{'content':'private'})
        await d.show('工具结果','private result')
        self.assertEqual(len(events),3)
        self.assertTrue(all(e['type']=='status' for e in events))
        self.assertNotIn('private',str(events));self.assertNotIn('secret',str(events))
    async def test_answer_only(self):self.assertEqual(render_execution(['sensitive tool result'],'answer'),'answer')
