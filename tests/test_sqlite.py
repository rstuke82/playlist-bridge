"""Disposable migration and API regression tests with deterministic service fixtures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from playlist_bridge import legacy, api
from playlist_bridge.storage import Repository, FILES


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.patches = [patch.object(legacy, 'CONFIG_DIR', self.directory),
                        patch.object(legacy, 'CONFIG_FILE', self.directory / 'config.json')]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()
        self.temp.cleanup()

    def seed(self):
        c = legacy.Config()
        c.config['playlists'] = [{'source': 'spotify', 'source_id': 'one', 'source_url': 'https://open.spotify.com/playlist/one', 'plex_playlist_name': 'Test', 'plex_playlist_id': '8', 'last_synced': '2026-01-01'}]
        c.mapping = {'spotify:one': {'Song|Artist': '1'}}
        c.source_snapshots = {'spotify:one': {'tracks': [{'title':'Song','artist':'Artist'}]}}
        c.save()
        return c

    def test_import_counts_exact_data_and_idempotence(self):
        original = {'plex': {'url':'http://plex'}, 'playlists':[{'source':'spotify','source_id':'one','favorite':True,'auto_sync':False}], 'sync_history':[{'result':'ok'}], 'notifications':{'enabled':True}, 'notification_history':[{'event':'sent'}]}
        (self.directory/'config.json').write_text(json.dumps({'_schema_version':2,'data':original}))
        values = {}
        for name, file in FILES.items():
            values[name] = {'entry': [{'unicode':'Beyoncé', 'count':2}]} if name != 'artist_aliases' else {'Artist':['Alias']}
            (self.directory/file).write_text(json.dumps(values[name]))
        repo = Repository(self.directory)
        for name, value in values.items(): self.assertEqual(repo.load(name), value)
        self.assertEqual(repo.load('runtime'), {k:v for k,v in original.items() if k != 'plex'})
        with repo.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM state').fetchone()[0], 10)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        for file in ['config.json', *FILES.values()]: self.assertTrue((self.directory/(file+'.pre-sqlite.bak')).exists())
        (self.directory/'mapping.json').write_text('{broken')
        self.assertEqual(Repository(self.directory).load('mapping'), values['mapping'])
        self.assertEqual(json.loads((self.directory/'config.json').read_text()), {'plex':original['plex']})

    def test_failed_import_retry(self):
        (self.directory/'mapping.json').write_text('{broken')
        with self.assertRaises(RuntimeError): Repository(self.directory)
        self.assertEqual((self.directory/'mapping.json').read_text(), '{broken')
        (self.directory/'mapping.json').write_text('{"kept":{}}')
        self.assertEqual(Repository(self.directory).load('mapping'), {'kept':{}})

    def test_health_persists_without_sync_mutations(self):
        c = self.seed()
        before = copy.deepcopy(c._buckets())
        track = {'title':'Song','artist':'Artist','album':'Album','plex_id':'1'}
        plex = Mock()
        plex.search_library.return_value = [track]
        plex.get_playlist_items.return_value = [track]
        source = Mock()
        source.get_playlist_tracks.return_value = ([track], {})
        with patch.object(api, '_health_plex', return_value=plex), patch.object(api,'_source_for_url', return_value=('spotify','url',source)), patch.object(legacy.Syncer,'_get_plex', return_value=plex):
            result = api.playlist_health('spotify:one')
            detail = api.playlist_detail('spotify:one')
        self.assertEqual(detail['tracks'][0]['status'], 'Legacy')
        self.assertEqual(detail['tracks'][0]['match']['plex_id'], '1')
        self.assertEqual(legacy.Config()._buckets(), before)
        self.assertEqual(legacy.Config().repository.load('health')['spotify:one'], result)
        self.assertIn('checked_at', api.list_playlists()[0]['health'])
        self.assertEqual([call[0] for call in plex.method_calls], ['search_library','get_playlist_items','search_library'])

    def test_fix_match_manual_and_selected_occurrences(self):
        c = self.seed()
        for source_id in ['two','three']:
            c.config['playlists'].append({'source':'spotify','source_id':source_id})
            c.missing['spotify:'+source_id] = [{'title':'Song','artist':'Artist','album':'Album'}]
        c.save()
        plex = Mock()
        plex.search_library.return_value = [{'plex_id':'2','title':'Fixed','artist':'Artist','album':'Album'}]
        with patch.object(legacy.Syncer,'_get_plex',return_value=plex), patch.object(legacy.Syncer,'sync_playlist',return_value={'ok':True}) as sync:
            result = api.save_missing_match(api.MissingMatchRequest(title='Song',artist='Artist',album='Album',plex_id='2',replace_playlist_key='spotify:one',playlist_keys=['spotify:two']))
        self.assertEqual(result['synced_playlists'],2)
        self.assertEqual(sync.call_count,2)
        c = legacy.Config()
        for key in ['spotify:one','spotify:two']:
            self.assertEqual(c.mapping[key]['Song|Artist'],'2')
            self.assertEqual(c.match_metadata[key]['Song|Artist']['provenance'],'manual')
        self.assertIn('spotify:three', c.missing)

    def test_health_and_stale_config_saves_do_not_overwrite_each_other(self):
        c = self.seed()
        c.repository.save_health('spotify:one', {'healthy':True})
        c.config['playlists'][0]['favorite'] = True
        c.save()
        self.assertTrue(legacy.Config().repository.load('health')['spotify:one']['healthy'])

if __name__ == '__main__': unittest.main()
