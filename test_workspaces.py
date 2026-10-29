import os
from pathlib import Path
import tempfile
import unittest
from workspace_store import WorkspaceStore,WorkspaceError

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=WorkspaceStore(self.root/'registry.db')
    def tearDown(self):self.tmp.cleanup()
    def test_real_directory_canonicalization_and_creation(self):
        a=self.store.register('u','项目 A',str(self.root/'project with spaces'),True)
        link=self.root/'link';link.symlink_to(a['path'],target_is_directory=True)
        self.assertEqual(self.store.register('u','同一个目录',str(link))['id'],a['id'])
        with self.assertRaises(WorkspaceError):self.store.register('u','bad','relative')
        with self.assertRaises(WorkspaceError):self.store.register('u','bad',str(self.root/'missing'))
        with self.assertRaises(WorkspaceError):self.store.get('other',a['id'])
        self.assertTrue(Path(a['path']).is_dir())
    def test_chat_binding_is_shared_and_frozen_when_default_changes(self):
        a=self.store.register('u','A',str(self.root/'a'),True);b=self.store.register('u','B',str(self.root/'b'),True)
        self.store.select('u',a['id'],make_default=True)
        first,_=self.store.resolve('u','chat1',self.root/'scratch')
        self.store.select('u',b['id'],make_default=True)
        second,_=self.store.resolve('u','chat1',self.root/'scratch')
        new,_=self.store.resolve('u','chat2',self.root/'scratch')
        self.assertEqual(first,second);self.assertEqual(str(first),a['path']);self.assertEqual(str(new),b['path'])
        self.store.select('u',None,'chat1');scratch,w=self.store.resolve('u','chat1',self.root/'scratch')
        self.assertIsNone(w);self.assertEqual(scratch,self.root/'scratch')
    def test_missing_directory_fails_instead_of_silent_fallback(self):
        a=self.store.register('u','A',str(self.root/'a'),True);self.store.select('u',a['id'],'chat')
        Path(a['path']).rmdir()
        with self.assertRaises(WorkspaceError):self.store.resolve('u','chat',self.root/'scratch')
        self.assertFalse((self.root/'scratch').exists())
    def test_remove_is_registry_only_and_used_workspace_is_protected(self):
        a=self.store.register('u','A',str(self.root/'a'),True);file=Path(a['path'])/'human.txt';file.write_text('keep')
        self.store.select('u',a['id'],'chat')
        with self.assertRaises(WorkspaceError):self.store.remove('u',a['id'])
        self.store.select('u',None,'chat');self.store.remove('u',a['id']);self.assertEqual(file.read_text(),'keep')

if __name__=='__main__':unittest.main(verbosity=2)
