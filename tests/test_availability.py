import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import nullcontext
from playlist_bridge.storage import Repository
from playlist_bridge.jobs import Store
from playlist_bridge import availability,library_cache,tasks

class AvailabilityTests(unittest.TestCase):
    @patch('playlist_bridge.inventory.snapshot',return_value={})
    def test_cache_reuse_refresh_and_identity(self,_snapshot):
        library_cache.invalidate()
        client=SimpleNamespace(base_url='plex',music_library_key='1',headers={'token':'a'})
        fetch=Mock(return_value=[{'plex_id':'1'}])
        with library_cache.reuse(15):
            library_cache.load(client,fetch);library_cache.load(client,fetch)
        self.assertEqual(fetch.call_count,1)
        with library_cache.reuse(15,refresh=True):library_cache.load(client,fetch)
        self.assertEqual(fetch.call_count,2)
        client.headers={'token':'b'}
        with library_cache.reuse(15):library_cache.load(client,fetch)
        self.assertEqual(fetch.call_count,3)
        library_cache.load(client,fetch)
        self.assertEqual(fetch.call_count,4) # unrelated/read-only operations bypass cache

    def test_schedule_added_once_to_existing_install(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(Path(directory)/'bridge.sqlite');store=Store(repo)
            tasks.setup(store)
            with repo.connect() as db:db.execute("DELETE FROM schedules WHERE action='plex_scan'")
            tasks.setup(store);tasks.setup(store)
            found=[s for s in store.schedules() if s['action']=='plex_scan']
            self.assertEqual(len(found),1);self.assertEqual(found[0]['cron'],'0 */1 * * *')
            store.save_schedule({'action':'plex_scan','scope':'all','hours':0})
            tasks.setup(store)
            self.assertFalse(next(s for s in store.schedules() if s['action']=='plex_scan')['enabled'])

    def test_scan_deduplicates_preserves_manual_and_scopes_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(Path(directory)/'bridge.sqlite');store=Store(repo)
            track={'title':'Song','artist':'Artist','album':'Album'}
            manual={'title':'Manual','artist':'Artist'};ignored={'title':'Ignored','artist':'Artist'}
            config=SimpleNamespace(config={'playlists':[{'key':'a','auto_sync':True},{'key':'b','auto_sync':False}]},missing={'a':[track,manual,ignored],'b':[track]},mapping={'a':{'Manual|Artist':'gone'}},save=Mock())
            syncer=Mock()
            syncer._find_ignored_track_key.side_effect=lambda key,t:t['title']=='Ignored'
            syncer._get_match_provenance.side_effect=lambda key,s:'manual' if s=='Manual|Artist' else 'automatic'
            syncer._same_missing_identity.side_effect=lambda a,b:a['title']==b['title']
            with patch('playlist_bridge.api.job_store',return_value=store),patch('playlist_bridge.api._config',return_value=config),patch('playlist_bridge.api._playlist_key',side_effect=lambda p:p['key']),patch('playlist_bridge.api._health_plex') as plex,patch('playlist_bridge.legacy.ProcessLock',return_value=nullcontext()),patch('playlist_bridge.legacy.Syncer',return_value=syncer),patch('playlist_bridge.legacy.Matcher.match_track',return_value='7') as match,patch('playlist_bridge.api._record_log'):
                plex.return_value.search_library.return_value=[{'plex_id':'7','title':'Song','artist':'Artist'}]
                result=availability.execute({})
            self.assertEqual(match.call_count,1)
            self.assertEqual(config.mapping['a']['Manual|Artist'],'gone')
            self.assertEqual([t['title'] for t in config.missing['a']],['Manual','Ignored'])
            self.assertTrue(config.config['playlists'][1]['ready_to_sync'])
            queued=store.get(result['sync_job_id'])
            self.assertEqual(queued['payload']['playlist_keys'],['a'])
            self.assertEqual(result['matches_found'],1)

    def test_unchanged_tracks_do_not_write(self):
        from playlist_bridge.legacy import PlexAPI
        client=object.__new__(PlexAPI)
        client.get_playlist_items=Mock(return_value=[{'plex_id':'1'},{'plex_id':'1'},{'plex_id':'2'}])
        with patch('playlist_bridge.legacy.requests.post') as post,patch('playlist_bridge.legacy.requests.put') as put:
            self.assertTrue(client.replace_playlist_tracks('p',['1','1','2']))
            post.assert_not_called();put.assert_not_called()
