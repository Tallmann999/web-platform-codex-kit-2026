from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
from inspect_project import inspect
from check_web_build import audit
from prepare_platform_docs import prepare

def tree_digest(root: Path) -> dict:
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}

class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def write(self,name,text=''):
        p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8'); return p
    def test_html_discovery(self):
        self.write('index.html','<html></html>')
        self.assertIn('index.html',inspect(self.root)['html_entry_candidates'])
    def test_phaser_and_scripts(self):
        self.write('package.json',json.dumps({'dependencies':{'phaser':'^4.2.1'},'scripts':{'build':'echo no-run'}}))
        d=inspect(self.root)
        self.assertEqual(d['engine_candidates'][0]['declared_version'],'^4.2.1')
        self.assertEqual(d['package_manifests'][0]['script_names'],['build'])
    def test_unity(self):
        self.write('ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.2.0f1\n')
        self.assertEqual(inspect(self.root)['engine_candidates'][0]['version'],'6000.2.0f1')
    def test_sdk_detection(self):
        self.write('src/sdk.js','window.PokiSDK.init()')
        self.assertIn('poki',inspect(self.root)['sdk_hints'])
    def test_skips_own_skill(self):
        self.write('.agents/skills/example/SKILL.md','YaGames PokiSDK')
        self.assertFalse(inspect(self.root)['sdk_hints'])
    def test_does_not_print_env(self):
        self.write('.env','SECRET_TOKEN=not-for-output')
        self.assertNotIn('not-for-output',json.dumps(inspect(self.root)))
    def test_invalid_manifest(self):
        self.write('package.json','{bad')
        self.assertTrue(any('Cannot parse' in w for w in inspect(self.root)['warnings']))
    def test_readonly_audit(self):
        self.write('index.html','<script src="main.js"></script>'); self.write('main.js','console.log(1)')
        before=tree_digest(self.root)
        inspect(self.root); audit(self.root)
        self.assertEqual(before,tree_digest(self.root))
    def test_valid_build(self):
        self.write('index.html','<img src="a.png">'); self.write('a.png','x')
        self.assertFalse(audit(self.root)['errors'])
    def test_missing_index(self):
        self.write('nested/index.html','')
        self.assertTrue(audit(self.root)['errors'])
    def test_missing_asset(self):
        self.write('index.html','<script src="gone.js"></script>')
        self.assertTrue(any('Missing HTML' in x for x in audit(self.root)['errors']))
    def test_yandex_host_sdk(self):
        self.write('index.html','<script src="/sdk.js"></script>')
        self.assertFalse(audit(self.root,'yandex')['errors'])
    def test_budget(self):
        self.write('index.html','a'*1000)
        self.assertTrue(audit(self.root,max_total_mb=0.0001)['errors'])
    def test_secret_filename(self):
        self.write('index.html',''); self.write('.env.production','secret')
        self.assertTrue(any('Potential secret' in x for x in audit(self.root)['errors']))
    def test_external_hosts(self):
        self.write('index.html','<script src="https://example.com/app.js?key=secret"></script>')
        d=audit(self.root,'poki')
        self.assertEqual(d['external_hosts'],['example.com'])
        self.assertNotIn('key=secret',json.dumps(d))
    def test_escape(self):
        self.write('index.html','<img src="../outside.png">')
        self.assertTrue(any('escapes' in x for x in audit(self.root)['errors']))
    def test_playgama_non_ascii(self):
        self.write('index.html',''); self.write('картинка.png','x')
        self.assertTrue(any('Non-Latin' in x for x in audit(self.root,'playgama')['errors']))
    def test_dry_run_no_writes(self):
        self.write('index.html','original')
        before=tree_digest(self.root)
        d=prepare(self.root,'yandex')
        self.assertEqual(d['status'],'PLAN_ONLY')
        self.assertEqual(before,tree_digest(self.root))
        self.assertFalse((self.root/'docs').exists())
    def test_generate_and_refuse_overwrite(self):
        d=prepare(self.root,'poki',True)
        self.assertTrue(d['status'].startswith('CREATED'))
        p=self.root/'docs/platforms/poki/PLATFORM_PROFILE.md'
        self.assertIn('Профиль poki',p.read_text(encoding='utf-8'))
        before=tree_digest(self.root)
        with self.assertRaises(FileExistsError): prepare(self.root,'poki',True)
        self.assertEqual(before,tree_digest(self.root))
    def test_invalid_platform(self):
        with self.assertRaises(ValueError): prepare(self.root,'../../escape',True)
    def test_symlink_output_refused(self):
        other=self.root/'outside'; other.mkdir()
        try: (self.root/'docs').symlink_to(other,target_is_directory=True)
        except OSError: self.skipTest('OS does not permit symlinks')
        with self.assertRaises(ValueError): prepare(self.root,'yandex',True)
    def test_symlink_build_detected(self):
        self.write('index.html',''); other=self.write('asset.dat','x')
        try: (self.root/'linked.dat').symlink_to(other)
        except OSError: self.skipTest('OS does not permit symlinks')
        self.assertTrue(any('Symlink' in x for x in audit(self.root)['errors']))

if __name__ == '__main__':
    unittest.main(verbosity=2)
