"""Contract checks for reviewed Lidarr writes; all network calls are fakes."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi import FastAPI, HTTPException
from playlist_bridge import lidarr, jobs
from playlist_bridge.storage import Repository

ALBUM = '11111111-1111-4111-8111-111111111111'
ARTIST = '22222222-2222-4222-8222-222222222222'


class FakeClient:
    def __init__(self, existing=False, artist_exists=False):
        self.calls = []
        self.artist = {'foreignArtistId': ARTIST, 'artistName': 'Artist', 'monitored': True}
        if artist_exists:
            self.artist.update(id=4, path='/existing/Artist', qualityProfileId=8, metadataProfileId=9)
        self.album = {'foreignAlbumId': ALBUM, 'title': 'Album', 'artist': self.artist, 'monitored': False}
        self.existing = existing

    def options(self):
        return {'version': 'test', 'roots': [{'id': 1, 'path': '/music'}],
                'qualities': [{'id': 1, 'name': 'Lossless'}], 'metadata': [{'id': 1, 'name': 'Standard'}]}

    def call(self, method, path, **kwargs):
        self.calls.append((method, path, copy.deepcopy(kwargs)))
        if path == 'album/lookup':
            return [copy.deepcopy(self.album)]
        if method == 'GET' and path == 'album':
            return [{**copy.deepcopy(self.album), 'id': 7}] if self.existing else []
        if method == 'POST' and path == 'album':
            self.existing = True
            return {'id': 7}
        if path == 'artist/4' and method == 'GET':
            return {**self.artist, 'tags': [4]}
        return {}


class LidarrTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name))
        self.cfg = lidarr.Settings(enabled=True, url='http://lidarr:8686', api_key='secret-key',
            root_folder='/music', quality_profile_id=1, metadata_profile_id=1).model_dump()
        self.repo.save({'lidarr': {'settings': self.cfg}})
        self.defaults = lidarr.Defaults(**self.cfg).model_dump()
        self.client = FakeClient()
        self.patches = [patch.object(lidarr, 'repository', return_value=self.repo),
                        patch.object(lidarr, 'Client', return_value=self.client)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def preview(self):
        result = lidarr.prepare(self.repo, lidarr.Preview(album_id=ALBUM, **self.defaults))
        return result, lidarr.state_get(self.repo, 'lidarr_previews', result['preview_id'])

    def test_read_only_preview_then_selected_album_add(self):
        preview, payload = self.preview()
        self.assertFalse(preview['album_exists'])
        self.assertTrue(all(c[0] == 'GET' for c in self.client.calls))
        self.assertNotIn('secret-key', str(preview) + str(payload))
        lidarr.execute(payload)
        writes = [c for c in self.client.calls if c[0] != 'GET']
        self.assertEqual(len(writes), 1)
        body = writes[0][2]['json']
        self.assertEqual(body['artist']['addOptions']['albumsToMonitor'], [ALBUM])
        self.assertEqual(body['artist']['addOptions']['monitor'], 'unknown')
        self.assertFalse(body['artist']['addOptions']['searchForMissingAlbums'])
        self.assertFalse(body['addOptions']['searchForNewAlbum'])
        self.assertEqual(body['artist']['monitorNewItems'], 'none')

    def test_existing_album_only_monitors_and_searches_selected(self):
        self.client.existing = True
        self.client.artist.update(id=4)
        self.defaults['search_now'] = True
        _, payload = self.preview()
        lidarr.execute(payload)
        writes = [c for c in self.client.calls if c[0] != 'GET']
        self.assertEqual([(m, p) for m, p, _ in writes], [('PUT', 'album/monitor'), ('POST', 'command')])
        self.assertEqual(writes[0][2]['json']['albumIds'], [7])
        self.assertEqual(writes[1][2]['json']['albumIds'], [7])

    def test_existing_artist_settings_are_preserved(self):
        self.client.artist.update(id=4, path='/existing/Artist', qualityProfileId=8, metadataProfileId=9)
        _, payload = self.preview()
        lidarr.execute(payload)
        body = next(c[2]['json'] for c in self.client.calls if c[:2] == ('POST', 'album'))
        self.assertEqual(body['artist']['qualityProfileId'], 8)
        self.assertEqual(body['artist']['metadataProfileId'], 9)
        self.assertEqual(body['artist']['path'], '/existing/Artist')
        self.assertNotIn('addOptions', body['artist'])

    def test_paused_artist_requires_review_in_lidarr(self):
        self.client.artist.update(id=4, monitored=False)
        with self.assertRaises(HTTPException):
            self.preview()
        self.assertTrue(all(c[0] == 'GET' for c in self.client.calls))

    def test_confirm_is_idempotent_and_settings_changes_block_execution(self):
        preview, payload = self.preview()
        app = FastAPI()
        lidarr.register(app)
        endpoint = next(r.endpoint for r in app.routes if r.path == '/api/lidarr/add')
        with patch('playlist_bridge.api.job_store', return_value=jobs.Store(self.repo)):
            first = endpoint(lidarr.Confirm(preview_id=preview['preview_id']))
            second = endpoint(lidarr.Confirm(preview_id=preview['preview_id']))
        self.assertEqual(first['id'], second['id'])
        self.repo.save({'lidarr': {'settings': {**self.cfg, 'api_key': 'changed'}}})
        with self.assertRaisesRegex(ValueError, 'settings changed'):
            lidarr.execute(payload)
        self.assertTrue(all(c[0] == 'GET' for c in self.client.calls))

    def test_key_stays_server_side_and_is_not_reused_for_changed_url(self):
        self.assertNotIn('api_key', lidarr.public_settings(self.cfg))
        same = lidarr.merged(lidarr.Settings(**{**self.cfg, 'api_key': ''}), self.repo)
        self.assertEqual(same['api_key'], 'secret-key')
        other = lidarr.merged(lidarr.Settings(**{**self.cfg, 'api_key': '', 'url': 'http://other:8686'}), self.repo)
        self.assertEqual(other['api_key'], '')

    def test_existing_artist_tags_are_appended(self):
        self.client.existing = True
        self.client.artist.update(id=4)
        self.defaults.update(tags=[7], tag_existing=True)
        self.client.options = lambda: {'version': 'test', 'roots': [{'id': 1, 'path': '/music'}], 'qualities': [{'id': 1, 'name': 'Lossless'}], 'metadata': [{'id': 1, 'name': 'None'}], 'tags': [{'id': 7, 'label': 'bridge'}]}
        preview, payload = self.preview()
        self.assertEqual(preview['metadata'], 'None')
        lidarr.execute(payload)
        update = next(c[2]['json'] for c in self.client.calls if c[:2] == ('PUT', 'artist/4'))
        self.assertEqual(update['tags'], [4, 7])

    def test_musicbrainz_persistent_cache(self):
        response = Mock()
        response.json.return_value = {'recordings': [{'artist-credit': [{'name': 'Artist'}],
            'releases': [{'release-group': {'id': ALBUM, 'title': 'Album', 'primary-type': 'Album'}}]}]}
        query = lidarr.Lookup(title='Track', artist='Artist', provider='musicbrainz')
        with patch.object(lidarr.requests, 'get', return_value=response) as get:
            result = lidarr.musicbrainz_search(self.repo, self.cfg, query)
            self.assertFalse(result['cached'])
            result = lidarr.musicbrainz_search(Repository(Path(self.tmp.name)), self.cfg, query)
            self.assertTrue(result['cached'])
            self.assertEqual(get.call_count, 1)
        self.assertEqual(result['rows'][0]['album_id'], ALBUM)


if __name__ == '__main__':
    unittest.main()
